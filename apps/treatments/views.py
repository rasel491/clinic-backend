# apps/treatments/views.py

# apps/treatments/views.py
from django.utils import timezone
from datetime import datetime, timedelta, date
from django.db.models import Q, Count, Sum, Avg, Min, Max
from django.db import transaction
from django.http import HttpResponse
from rest_framework import viewsets, mixins, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
import pandas as pd
import json

from core.permissions import *
from core.constants import UserRoles
from core.utils.excel_export import export_to_excel
from .models import (
    TreatmentCategory, Treatment, ToothChart,
    TreatmentPlan, TreatmentPlanItem, TreatmentNote,
    TreatmentTemplate, TemplateTreatment
)
from .serializers import (
    TreatmentCategorySerializer, TreatmentSerializer, ToothChartSerializer,
    TreatmentPlanSerializer, TreatmentPlanItemSerializer, TreatmentNoteSerializer,
    TreatmentTemplateSerializer, TemplateTreatmentSerializer,
    TreatmentPlanCreateSerializer, TreatmentPlanStatusUpdateSerializer,
    TreatmentPlanItemStatusUpdateSerializer, ApplyTemplateSerializer
)


# ===========================================
# PAGINATION CLASSES
# ===========================================
class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class LargePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


# ===========================================
# FILTER SETS
# ===========================================
from django_filters import rest_framework as django_filters


class TreatmentFilter(django_filters.FilterSet):
    """Filter for treatments"""
    
    price_min = django_filters.NumberFilter(field_name='base_price', lookup_expr='gte')
    price_max = django_filters.NumberFilter(field_name='base_price', lookup_expr='lte')
    category_name = django_filters.CharFilter(field_name='category__name', lookup_expr='icontains')
    requires_lab = django_filters.BooleanFilter()
    
    class Meta:
        model = Treatment
        fields = [
            'category', 'difficulty', 'is_active', 'is_popular',
            'requires_lab', 'suitable_for_age', 'suitable_for_gender'
        ]


class TreatmentPlanFilter(django_filters.FilterSet):
    """Filter for treatment plans"""
    
    date_from = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    date_to = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')
    patient_name = django_filters.CharFilter(method='filter_patient_name')
    doctor_name = django_filters.CharFilter(method='filter_doctor_name')
    amount_min = django_filters.NumberFilter(field_name='final_amount', lookup_expr='gte')
    amount_max = django_filters.NumberFilter(field_name='final_amount', lookup_expr='lte')
    
    class Meta:
        model = TreatmentPlan
        fields = [
            'status', 'priority', 'patient', 'doctor', 'branch',
            'insurance_approved', 'consent_form_signed'
        ]
    
    def filter_patient_name(self, queryset, name, value):
        return queryset.filter(
            Q(patient__user__first_name__icontains=value) |
            Q(patient__user__last_name__icontains=value) |
            Q(patient__user__full_name__icontains=value)
        )
    
    def filter_doctor_name(self, queryset, name, value):
        return queryset.filter(
            Q(doctor__user__first_name__icontains=value) |
            Q(doctor__user__last_name__icontains=value) |
            Q(doctor__user__full_name__icontains=value)
        )


# ===========================================
# VIEWSETS
# ===========================================
class TreatmentCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for TreatmentCategory"""
    
    queryset = TreatmentCategory.objects.filter(deleted_at__isnull=True)
    serializer_class = TreatmentCategorySerializer
    pagination_class = StandardPagination
    permission_classes = [IsAuthenticated & (IsManager | IsDoctor)]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'display_in_portal']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'order', 'created_at']
    ordering = ['order', 'name']
    
    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user
        )
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def with_treatments(self, request):
        """Get categories with treatment counts"""
        categories = self.get_queryset().annotate(
            treatment_count=Count('treatments', filter=Q(treatments__is_active=True))
        ).filter(treatment_count__gt=0)
        
        serializer = self.get_serializer(categories, many=True)
        return Response(serializer.data)


class TreatmentViewSet(viewsets.ModelViewSet):
    """ViewSet for Treatment"""
    
    queryset = Treatment.objects.filter(
        deleted_at__isnull=True,
        is_active=True
    ).select_related('category', 'last_updated_by')
    
    serializer_class = TreatmentSerializer
    pagination_class = StandardPagination
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TreatmentFilter
    search_fields = ['code', 'name', 'display_name', 'description']
    ordering_fields = ['name', 'base_price', 'popularity_score', 'order']
    ordering = ['category', 'order', 'name']
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve', 'catalog', 'suggest']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated & (IsManager | IsDoctor)]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        queryset = super().get_queryset()
        
        # For patients, only show treatments visible in portal
        if self.request.user.role == UserRoles.PATIENT:
            queryset = queryset.filter(display_in_portal=True)
        
        # Filter by branch-specific treatments if needed
        branch_id = self.request.query_params.get('branch_id')
        if branch_id:
            # You can add branch-specific logic here
            pass
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user,
            last_updated_by=self.request.user
        )
    
    def perform_update(self, serializer):
        serializer.save(
            updated_by=self.request.user,
            last_updated_by=self.request.user
        )
    
    @action(detail=False, methods=['get'])
    def catalog(self, request):
        """Get treatment catalog grouped by category"""
        categories = TreatmentCategory.objects.filter(
            is_active=True,
            display_in_portal=True
        ).annotate(
            treatment_count=Count('treatments', filter=Q(treatments__is_active=True))
        ).filter(treatment_count__gt=0)
        
        result = []
        for category in categories:
            treatments = Treatment.objects.filter(
                category=category,
                is_active=True,
                display_in_portal=True
            ).order_by('order', 'name')
            
            result.append({
                'category': TreatmentCategorySerializer(category).data,
                'treatments': TreatmentSerializer(treatments, many=True).data
            })
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get popular treatments"""
        treatments = self.get_queryset().filter(
            is_popular=True
        ).order_by('-popularity_score', 'name')[:10]
        
        serializer = self.get_serializer(treatments, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def suggest(self, request):
        """Suggest treatments based on patient profile"""
        patient_id = request.query_params.get('patient_id')
        age = request.query_params.get('age')
        gender = request.query_params.get('gender')
        condition = request.query_params.get('condition')
        
        queryset = self.get_queryset()
        
        # Filter by age group
        if age:
            try:
                age_int = int(age)
                if age_int <= 12:
                    queryset = queryset.filter(
                        Q(suitable_for_age='CHILD') | Q(suitable_for_age='ALL')
                    )
                elif age_int <= 19:
                    queryset = queryset.filter(
                        Q(suitable_for_age='TEEN') | Q(suitable_for_age='ALL')
                    )
                elif age_int <= 59:
                    queryset = queryset.filter(
                        Q(suitable_for_age='ADULT') | Q(suitable_for_age='ALL')
                    )
                else:
                    queryset = queryset.filter(
                        Q(suitable_for_age='SENIOR') | Q(suitable_for_age='ALL')
                    )
            except ValueError:
                pass
        
        # Filter by gender
        if gender:
            queryset = queryset.filter(
                Q(suitable_for_gender=gender.upper()) | Q(suitable_for_gender='ALL')
            )
        
        # Filter by medical condition
        if condition:
            # This is simplified - you'd need more complex logic
            queryset = queryset.exclude(
                medical_conditions__contains=[condition]
            )
        
        serializer = self.get_serializer(queryset[:20], many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def increment_popularity(self, request, pk=None):
        """Increment treatment popularity score"""
        treatment = self.get_object()
        treatment.popularity_score += 1
        treatment.save()
        
        return Response({
            'message': 'Popularity score updated',
            'popularity_score': treatment.popularity_score
        })


class ToothChartViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for ToothChart"""
    
    queryset = ToothChart.objects.filter(is_active=True)
    serializer_class = ToothChartSerializer
    pagination_class = None  # No pagination for tooth chart
    permission_classes = [IsAuthenticated & (IsStaff | HasBranchAccess)]
    
    @action(detail=False, methods=['get'])
    def by_quadrant(self, request):
        """Get teeth grouped by quadrant"""
        quadrants = {
            1: {'name': 'Upper Right', 'teeth': []},
            2: {'name': 'Upper Left', 'teeth': []},
            3: {'name': 'Lower Left', 'teeth': []},
            4: {'name': 'Lower Right', 'teeth': []},
        }
        
        teeth = self.get_queryset().order_by('tooth_number')
        for tooth in teeth:
            quadrant_data = quadrants.get(tooth.quadrant)
            if quadrant_data:
                quadrant_data['teeth'].append(ToothChartSerializer(tooth).data)
        
        return Response(quadrants)


class TreatmentPlanViewSet(viewsets.ModelViewSet):
    """ViewSet for TreatmentPlan"""
    
    queryset = TreatmentPlan.objects.select_related(
        'patient', 'patient__user',
        'doctor', 'doctor__user',
        'branch', 'referred_by', 'referred_by__user',
        'parent_plan'
    ).prefetch_related(
        'plan_items', 'clinical_notes', 'revisions'
    ).filter(deleted_at__isnull=True)
    
    serializer_class = TreatmentPlanSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TreatmentPlanFilter
    search_fields = ['plan_id', 'name', 'diagnosis']
    ordering_fields = ['created_at', 'final_amount', 'estimated_start_date']
    ordering = ['-created_at']
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve', 'stats', 'export']:
            permission_classes = [IsAuthenticated & (IsStaff | HasBranchAccess)]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated & (IsDoctor | IsManager)]
        elif self.action in ['update_status', 'create_revision']:
            permission_classes = [IsAuthenticated & (IsDoctor | IsManager)]
        else:
            permission_classes = [IsAuthenticated & IsStaff]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Super admin can see all
        if user.role == UserRoles.SUPER_ADMIN:
            return queryset
        
        # Clinic manager can see all in their branches
        if user.role == UserRoles.CLINIC_MANAGER:
            if hasattr(user, 'user_branches'):
                branch_ids = user.user_branches.filter(
                    is_active=True
                ).values_list('branch_id', flat=True)
                return queryset.filter(branch_id__in=branch_ids)
            return queryset
        
        # Doctors can see their own plans
        if user.role == UserRoles.DOCTOR:
            try:
                doctor = user.doctor_profile
                return queryset.filter(doctor=doctor)
            except:
                return queryset.none()
        
        # Patients can see their own plans
        if user.role == UserRoles.PATIENT:
            try:
                patient = user.patient_profile
                return queryset.filter(patient=patient)
            except:
                return queryset.none()
        
        # Receptionists can see plans in their branch
        if user.role == UserRoles.RECEPTIONIST:
            if hasattr(user, 'user_branches'):
                branch_ids = user.user_branches.filter(
                    is_active=True
                ).values_list('branch_id', flat=True)
                return queryset.filter(branch_id__in=branch_ids)
        
        return queryset.none()
    
    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user
        )
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    @action(detail=False, methods=['post'])
    def create_with_items(self, request):
        """Create treatment plan with items in one request"""
        serializer = TreatmentPlanCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                # Create plan
                plan_data = {
                    'patient_id': serializer.validated_data['patient_id'],
                    'doctor_id': serializer.validated_data['doctor_id'],
                    'branch_id': serializer.validated_data['branch_id'],
                    'name': serializer.validated_data['name'],
                    'diagnosis': serializer.validated_data.get('diagnosis', ''),
                    'total_estimated_amount': serializer.validated_data['total_estimated_amount'],
                    'status': 'DRAFT',
                    'created_by': request.user,
                    'updated_by': request.user,
                }
                
                plan_serializer = TreatmentPlanSerializer(
                    data=plan_data,
                    context={'request': request}
                )
                if not plan_serializer.is_valid():
                    return Response(plan_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
                plan = plan_serializer.save()
                
                # Create plan items
                for i, item_data in enumerate(serializer.validated_data['items']):
                    TreatmentPlanItem.objects.create(
                        treatment_plan=plan,
                        treatment_id=item_data['treatment_id'],
                        visit_number=item_data.get('visit_number', i + 1),
                        order=item_data.get('order', i),
                        tooth_number=item_data.get('tooth_number', ''),
                        surface=item_data.get('surface', ''),
                        notes=item_data.get('notes', ''),
                        created_by=request.user,
                        updated_by=request.user,
                    )
                
                # Recalculate plan amounts
                plan.save()
                
                return Response(
                    TreatmentPlanSerializer(plan, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
                
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update treatment plan status"""
        plan = self.get_object()
        
        serializer = TreatmentPlanStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                new_status = serializer.validated_data['status']
                notes = serializer.validated_data.get('notes', '')
                
                # Update plan status
                plan.status = new_status
                plan.updated_by = request.user
                
                # Set dates based on status
                if new_status == 'IN_PROGRESS' and not plan.actual_start_date:
                    plan.actual_start_date = timezone.now().date()
                elif new_status == 'COMPLETED' and not plan.actual_end_date:
                    plan.actual_end_date = timezone.now().date()
                
                plan.save()
                
                # Add note if provided
                if notes:
                    TreatmentNote.objects.create(
                        treatment_plan_item=None,  # General plan note
                        note_type='GENERAL',
                        content=f"Status changed to {new_status}: {notes}",
                        created_by=request.user,
                        updated_by=request.user,
                    )
                
                return Response({
                    'message': 'Status updated successfully',
                    'status': plan.status,
                    'updated_at': plan.updated_at
                })
                
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def create_revision(self, request, pk=None):
        """Create a revised version of the plan"""
        plan = self.get_object()
        
        try:
            with transaction.atomic():
                new_plan = plan.create_revision()
                
                # Update audit fields
                new_plan.created_by = request.user
                new_plan.updated_by = request.user
                new_plan.save()
                
                # Mark old plan as revised
                plan.status = 'REVISED'
                plan.save()
                
                return Response(
                    TreatmentPlanSerializer(new_plan, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
                
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def active_plans(self, request):
        """Get active treatment plans"""
        queryset = self.get_queryset().filter(
            status__in=['IN_PROGRESS', 'ACCEPTED', 'CONTRACT_SIGNED']
        ).order_by('estimated_start_date')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def todays_plans(self, request):
        """Get plans with items scheduled for today"""
        today = timezone.now().date()
        
        # Get plans with items scheduled for today
        plan_ids = TreatmentPlanItem.objects.filter(
            scheduled_date=today,
            status__in=['SCHEDULED', 'IN_PROGRESS']
        ).values_list('treatment_plan_id', flat=True).distinct()
        
        queryset = self.get_queryset().filter(id__in=plan_ids)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get treatment plan statistics"""
        queryset = self.get_queryset()
        
        # Basic stats
        total = queryset.count()
        by_status = queryset.values('status').annotate(
            count=Count('id'),
            total_amount=Sum('final_amount'),
            avg_amount=Avg('final_amount')
        ).order_by('-count')
        
        by_doctor = queryset.values('doctor__user__full_name').annotate(
            count=Count('id'),
            total_amount=Sum('final_amount')
        ).order_by('-count')[:10]
        
        by_month = queryset.filter(
            created_at__year=timezone.now().year
        ).extra(
            {'month': "EXTRACT(month FROM created_at)"}
        ).values('month').annotate(
            count=Count('id'),
            total_amount=Sum('final_amount')
        ).order_by('month')
        
        # Financial stats
        financial = queryset.aggregate(
            total_revenue=Sum('final_amount'),
            total_paid=Sum('paid_amount'),
            total_balance=Sum('final_amount') - Sum('paid_amount'),
            avg_plan_amount=Avg('final_amount'),
            max_plan_amount=Max('final_amount'),
            min_plan_amount=Min('final_amount')
        )
        
        return Response({
            'total': total,
            'by_status': list(by_status),
            'by_doctor': list(by_doctor),
            'by_month': list(by_month),
            'financial': financial,
        })
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export treatment plans to Excel"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Prepare data
        data = []
        for plan in queryset:
            data.append({
                'Plan ID': plan.plan_id,
                'Patient': plan.patient.user.get_full_name(),
                'Doctor': plan.doctor.user.get_full_name(),
                'Branch': plan.branch.name,
                'Status': plan.get_status_display(),
                'Created Date': plan.created_at.date(),
                'Estimated Start': plan.estimated_start_date,
                'Estimated End': plan.estimated_end_date,
                'Total Amount': plan.total_estimated_amount,
                'Discount': plan.discount_amount,
                'Final Amount': plan.final_amount,
                'Paid Amount': plan.paid_amount,
                'Balance': plan.balance_amount,
                'Progress': f"{plan.progress_percentage}%",
                'Items Count': plan.plan_items.count(),
            })
        
        # Export to Excel
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=treatment_plans_export.xlsx'
        
        df = pd.DataFrame(data)
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Treatment Plans', index=False)
            
            # Add plan items sheet
            items_data = []
            for plan in queryset:
                for item in plan.plan_items.all():
                    items_data.append({
                        'Plan ID': plan.plan_id,
                        'Visit Number': item.visit_number,
                        'Treatment': item.treatment.name,
                        'Status': item.get_status_display(),
                        'Scheduled Date': item.scheduled_date,
                        'Tooth': item.tooth_number,
                        'Surface': item.surface,
                        'Amount': item.actual_amount,
                        'Is Paid': 'Yes' if item.is_paid else 'No',
                        'Completed Date': item.completed_date,
                    })
            
            if items_data:
                items_df = pd.DataFrame(items_data)
                items_df.to_excel(writer, sheet_name='Plan Items', index=False)
        
        return response


class TreatmentPlanItemViewSet(viewsets.ModelViewSet):
    """ViewSet for TreatmentPlanItem"""
    
    queryset = TreatmentPlanItem.objects.select_related(
        'treatment_plan', 'treatment', 'scheduled_visit',
        'performed_by', 'performed_by__user', 'assistant'
    ).prefetch_related('clinical_notes')
    
    serializer_class = TreatmentPlanItemSerializer
    pagination_class = StandardPagination
    permission_classes = [IsAuthenticated & (IsStaff | HasBranchAccess)]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'is_paid', 'phase', 'quadrant']
    search_fields = ['treatment__name', 'tooth_number', 'procedure_notes']
    ordering_fields = ['visit_number', 'scheduled_date', 'completed_date']
    ordering = ['treatment_plan', 'visit_number', 'order']
    
    def get_queryset(self):
        """Filter queryset based on parent plan access"""
        queryset = super().get_queryset()
        
        # Filter by plan if specified
        plan_id = self.request.query_params.get('plan_id')
        if plan_id:
            queryset = queryset.filter(treatment_plan_id=plan_id)
        
        # Filter by scheduled date
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(scheduled_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(scheduled_date__lte=date_to)
        
        # Filter by upcoming items
        upcoming = self.request.query_params.get('upcoming')
        if upcoming:
            today = timezone.now().date()
            queryset = queryset.filter(
                scheduled_date__gte=today,
                status__in=['PENDING', 'SCHEDULED']
            )
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update plan item status"""
        item = self.get_object()
        
        serializer = TreatmentPlanItemStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                new_status = serializer.validated_data['status']
                notes = serializer.validated_data.get('notes', '')
                completed_date = serializer.validated_data.get('completed_date')
                
                # Update item status
                item.status = new_status
                item.updated_by = request.user
                
                # Set completed date if provided or if status is COMPLETED
                if completed_date:
                    item.completed_date = completed_date
                elif new_status == 'COMPLETED' and not item.completed_date:
                    item.completed_date = timezone.now().date()
                    item.end_time = timezone.now()
                
                # Set start time if starting
                if new_status == 'IN_PROGRESS' and not item.start_time:
                    item.start_time = timezone.now()
                
                item.save()
                
                # Update parent plan progress
                plan = item.treatment_plan
                plan.save()  # This will recalculate progress
                
                # Add clinical note if provided
                if notes:
                    TreatmentNote.objects.create(
                        treatment_plan_item=item,
                        note_type='GENERAL',
                        content=f"Status changed to {new_status}: {notes}",
                        created_by=request.user,
                        updated_by=request.user,
                    )
                
                return Response({
                    'message': 'Status updated successfully',
                    'status': item.status,
                    'progress_percentage': plan.progress_percentage
                })
                
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def schedule_visit(self, request, pk=None):
        """Schedule a visit for this item"""
        item = self.get_object()
        visit_id = request.data.get('visit_id')
        
        if not visit_id:
            return Response(
                {'error': 'visit_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            visit = Visit.objects.get(id=visit_id)
            
            # Validate visit belongs to same patient
            if visit.patient != item.treatment_plan.patient:
                return Response(
                    {'error': 'Visit must belong to the same patient'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            item.scheduled_visit = visit
            item.scheduled_date = visit.scheduled_date
            item.status = 'SCHEDULED'
            item.save()
            
            return Response({
                'message': 'Visit scheduled successfully',
                'scheduled_date': item.scheduled_date,
                'visit_id': visit.id
            })
            
        except Visit.DoesNotExist:
            return Response(
                {'error': 'Visit not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['get'])
    def todays_items(self, request):
        """Get items scheduled for today"""
        today = timezone.now().date()
        
        queryset = self.get_queryset().filter(
            scheduled_date=today,
            status__in=['SCHEDULED', 'IN_PROGRESS']
        ).order_by('scheduled_visit__scheduled_time')
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class TreatmentNoteViewSet(viewsets.ModelViewSet):
    """ViewSet for TreatmentNote"""
    
    queryset = TreatmentNote.objects.select_related(
        'treatment_plan_item',
        'treatment_plan_item__treatment_plan',
        'created_by',
        'updated_by'
    )
    
    serializer_class = TreatmentNoteSerializer
    pagination_class = StandardPagination
    permission_classes = [IsAuthenticated & (IsDoctor | IsManager)]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['note_type', 'is_critical']
    search_fields = ['content']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset based on plan item"""
        queryset = super().get_queryset()
        
        # Filter by plan item
        item_id = self.request.query_params.get('item_id')
        if item_id:
            queryset = queryset.filter(treatment_plan_item_id=item_id)
        
        # Filter by plan
        plan_id = self.request.query_params.get('plan_id')
        if plan_id:
            queryset = queryset.filter(
                treatment_plan_item__treatment_plan_id=plan_id
            )
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user
        )
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class TreatmentTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for TreatmentTemplate"""
    
    queryset = TreatmentTemplate.objects.filter(
        deleted_at__isnull=True,
        is_active=True
    ).select_related('category').prefetch_related('treatments')
    
    serializer_class = TreatmentTemplateSerializer
    pagination_class = StandardPagination
    permission_classes = [IsAuthenticated & (IsDoctor | IsManager)]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'is_active']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'total_price']
    ordering = ['name']
    
    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user
        )
    
    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def apply_to_patient(self, request, pk=None):
        """Apply template to create a treatment plan"""
        template = self.get_object()
        
        serializer = ApplyTemplateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                # Create treatment plan
                plan = TreatmentPlan.objects.create(
                    patient=serializer.validated_data['patient'],
                    doctor=serializer.validated_data['doctor'],
                    branch=serializer.validated_data['branch'],
                    name=f"{template.name} - {serializer.validated_data['patient'].user.get_full_name()}",
                    status='DRAFT',
                    created_by=request.user,
                    updated_by=request.user,
                )
                
                # Add template treatments to plan
                total_amount = Decimal('0.00')
                template_treatments = template.templatetreatment_set.select_related('treatment').order_by('order')
                
                for i, template_treatment in enumerate(template_treatments):
                    TreatmentPlanItem.objects.create(
                        treatment_plan=plan,
                        treatment=template_treatment.treatment,
                        visit_number=template_treatment.visit_number or (i + 1),
                        order=template_treatment.order or i,
                        created_by=request.user,
                        updated_by=request.user,
                    )
                    total_amount += template_treatment.treatment.total_price
                
                # Update plan amounts
                plan.total_estimated_amount = total_amount
                plan.save()
                
                return Response(
                    TreatmentPlanSerializer(plan, context={'request': request}).data,
                    status=status.HTTP_201_CREATED
                )
                
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===========================================
# CUSTOM VIEWS
# ===========================================
class TreatmentDashboardView(APIView):
    """Dashboard view for treatments"""
    
    permission_classes = [IsAuthenticated & IsStaff]
    
    def get(self, request):
        """Get treatment dashboard data"""
        branch_id = request.query_params.get('branch_id')
        
        # Get accessible branches for user
        if hasattr(request.user, 'user_branches'):
            accessible_branches = request.user.user_branches.filter(
                is_active=True
            ).values_list('branch_id', flat=True)
        else:
            accessible_branches = []
        
        # Filter by branch if specified and accessible
        if branch_id and branch_id in accessible_branches:
            branch_filter = {'branch_id': branch_id}
        elif accessible_branches:
            branch_filter = {'branch_id__in': accessible_branches}
        else:
            branch_filter = {}
        
        today = timezone.now().date()
        
        # Treatment statistics
        treatments = Treatment.objects.filter(is_active=True)
        treatment_stats = {
            'total': treatments.count(),
            'by_category': list(
                treatments.values('category__name').annotate(
                    count=Count('id')
                ).order_by('-count')
            ),
            'popular': list(
                treatments.filter(is_popular=True).order_by('-popularity_score')[:5]
                .values('name', 'code', 'base_price', 'popularity_score')
            ),
        }
        
        # Treatment plan statistics
        plans = TreatmentPlan.objects.filter(**branch_filter)
        plan_stats = {
            'total': plans.count(),
            'active': plans.filter(status='IN_PROGRESS').count(),
            'completed_today': plans.filter(
                actual_end_date=today
            ).count(),
            'revenue_today': plans.filter(
                created_at__date=today
            ).aggregate(total=Sum('final_amount'))['total'] or 0,
            'by_status': list(
                plans.values('status').annotate(
                    count=Count('id')
                ).order_by('-count')
            ),
        }
        
        # Today's scheduled items
        todays_items = TreatmentPlanItem.objects.filter(
            scheduled_date=today,
            status__in=['SCHEDULED', 'IN_PROGRESS'],
            treatment_plan__branch_id__in=(
                [branch_id] if branch_id else accessible_branches
            )
        ).select_related(
            'treatment_plan', 'treatment_plan__patient', 
            'treatment_plan__patient__user', 'treatment'
        ).order_by('scheduled_visit__scheduled_time')[:10]
        
        # Upcoming items (next 7 days)
        upcoming_date = today + timedelta(days=7)
        upcoming_items = TreatmentPlanItem.objects.filter(
            scheduled_date__range=[today, upcoming_date],
            status='SCHEDULED',
            treatment_plan__branch_id__in=(
                [branch_id] if branch_id else accessible_branches
            )
        ).select_related('treatment_plan', 'treatment').order_by('scheduled_date')[:10]
        
        return Response({
            'treatment_stats': treatment_stats,
            'plan_stats': plan_stats,
            'todays_items': TreatmentPlanItemSerializer(todays_items, many=True).data,
            'upcoming_items': TreatmentPlanItemSerializer(upcoming_items, many=True).data,
            'date': today,
        })