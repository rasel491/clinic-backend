# clinic/Backend/apps/patients/views.py
from rest_framework import serializers
from rest_framework import viewsets, status, filters, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, Max, Min
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from datetime import timedelta, datetime
import json
import csv
from io import StringIO, BytesIO
import pandas as pd
import logging

from core.permissions import (
    IsAdminUser, IsManager, IsDoctor, IsReceptionist, IsCashier,
    IsStaff, HasBranchAccess, CanOverride, IsAuthenticatedAndActive,
    IsOwnerOrStaff
)

from .models import Patient
from .serializers import (
    PatientSerializer,
    PatientCreateSerializer,
    PatientUpdateSerializer,
    PatientListSerializer,
    PatientMedicalHistorySerializer,
    PatientSearchSerializer,
    PatientStatsSerializer,
    PatientImportSerializer,
    PatientExportSerializer,
    EmergencyContactSerializer,
)
from apps.accounts.models import User
from apps.audit.services import log_action, attach_audit_context

logger = logging.getLogger(__name__)


# ============================
# Custom Pagination
# ============================

class PatientPagination(PageNumberPagination):
    """Custom pagination for patients"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'current_page': self.page.number,
            'total_pages': self.page.paginator.num_pages,
            'page_size': self.get_page_size(self.request),
            'results': data
        })


# ============================
# Patient ViewSet
# ============================

class PatientViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing patients.
    """
    queryset = Patient.objects.filter(deleted_at__isnull=True)
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated, IsReceptionist]
    pagination_class = PatientPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['gender', 'blood_group', 'is_insurance_verified', 'registered_branch']
    search_fields = [
        'patient_id', 'user__email', 'user__full_name', 
        'user__phone', 'insurance_id'
    ]
    ordering_fields = [
        'patient_id', 'user__full_name', 'date_of_birth', 
        'registered_at', 'created_at'
    ]
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Filter queryset based on user permissions and branch.
        """
        queryset = super().get_queryset()
        
        # Get branch from request
        branch_id = getattr(self.request, 'branch_id', None)
        
        # Filter by branch if specified
        if branch_id:
            queryset = queryset.filter(registered_branch_id=branch_id)
        
        # Patients can only see their own profile
        if self.request.user.role == 'patient':
            return queryset.filter(user=self.request.user)
        
        # Doctors can see patients in their branch
        if self.request.user.role == 'doctor' and branch_id:
            return queryset.filter(registered_branch_id=branch_id)
        
        # Receptionists and above can see all patients in their branches
        return queryset
    
    def get_serializer_class(self):
        """
        Use different serializers based on action.
        """
        if self.action == 'list':
            return PatientListSerializer
        elif self.action == 'create':
            return PatientCreateSerializer
        elif self.action == 'update' or self.action == 'partial_update':
            return PatientUpdateSerializer
        return super().get_serializer_class()
    
    def get_permissions(self):
        """
        Custom permissions for different actions.
        """
        if self.action in ['me', 'my_profile']:
            return [IsAuthenticatedAndActive()]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated, IsReceptionist | IsManager | IsAdminUser]
        elif self.action == 'retrieve':
            return [IsAuthenticated, IsOwnerOrStaff]
        return super().get_permissions()
    
    def perform_create(self, serializer):
        """Create patient with audit logging"""
        with transaction.atomic():
            # Attach audit context
            attach_audit_context(serializer, self.request)
            
            # Set registered branch from request if not provided
            if not serializer.validated_data.get('registered_branch'):
                branch_id = getattr(self.request, 'branch_id', None)
                if branch_id:
                    from apps.clinics.models import Branch
                    try:
                        branch = Branch.objects.get(id=branch_id)
                        serializer.validated_data['registered_branch'] = branch
                    except Branch.DoesNotExist:
                        pass
            
            # Save patient
            patient = serializer.save()
            
            # Log creation
            log_action(
                instance=patient,
                action='CREATE',
                user=self.request.user,
                branch=patient.registered_branch,
                device_id=self.request.META.get('HTTP_X_DEVICE_ID'),
                ip_address=self.request.META.get('REMOTE_ADDR'),
            )
            
            logger.info(f"Patient created: {patient.patient_id} by {self.request.user}")
    
    def perform_update(self, serializer):
        """Update patient with audit logging"""
        with transaction.atomic():
            # Attach audit context
            attach_audit_context(serializer, self.request)
            
            # Save updates
            updated_patient = serializer.save()
            
            # Log update
            log_action(
                instance=updated_patient,
                action='UPDATE',
                user=self.request.user,
                branch=updated_patient.registered_branch,
                device_id=self.request.META.get('HTTP_X_DEVICE_ID'),
                ip_address=self.request.META.get('REMOTE_ADDR'),
            )
            
            logger.info(f"Patient updated: {updated_patient.patient_id} by {self.request.user}")
    
    def perform_destroy(self, instance):
        """Soft delete patient with audit logging"""
        with transaction.atomic():
            # Check if patient has active appointments
            from apps.visits.models import Appointment
            active_appointments = Appointment.objects.filter(
                patient=instance,
                status__in=['scheduled', 'confirmed']
            ).exists()
            
            if active_appointments:
                raise serializers.ValidationError(
                    "Cannot delete patient with active appointments"
                )
            
            # Soft delete
            instance.deleted_at = timezone.now()
            instance.deleted_by = self.request.user
            instance.save()
            
            # Also deactivate user account
            instance.user.is_active = False
            instance.user.save()
            
            # Log deletion
            log_action(
                instance=instance,
                action='DELETE',
                user=self.request.user,
                branch=instance.registered_branch,
                device_id=self.request.META.get('HTTP_X_DEVICE_ID'),
                ip_address=self.request.META.get('REMOTE_ADDR'),
            )
            
            logger.info(f"Patient soft deleted: {instance.patient_id} by {self.request.user}")
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """
        Get current user's patient profile.
        """
        try:
            patient = Patient.objects.get(user=request.user)
            serializer = self.get_serializer(patient)
            return Response(serializer.data)
        except Patient.DoesNotExist:
            return Response(
                {'error': 'Patient profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get', 'put'])
    def medical_history(self, request, pk=None):
        """
        Get or update patient medical history.
        """
        patient = self.get_object()
        
        if request.method == 'GET':
            serializer = PatientMedicalHistorySerializer({
                'allergies': patient.allergies,
                'chronic_conditions': patient.chronic_conditions,
                'current_medications': patient.current_medications,
            })
            return Response(serializer.data)
        
        elif request.method == 'PUT':
            # Only doctors and receptionists can update medical history
            if not (request.user.role in ['doctor', 'receptionist', 'clinic_manager', 'super_admin']):
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = PatientMedicalHistorySerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                # Update medical history
                patient.allergies = serializer.validated_data.get('allergies', patient.allergies)
                patient.chronic_conditions = serializer.validated_data.get('chronic_conditions', patient.chronic_conditions)
                patient.current_medications = serializer.validated_data.get('current_medications', patient.current_medications)
                patient.save()
                
                # Log update
                log_action(
                    instance=patient,
                    action='MEDICAL_HISTORY_UPDATE',
                    user=request.user,
                    branch=patient.registered_branch,
                    device_id=request.META.get('HTTP_X_DEVICE_ID'),
                    ip_address=request.META.get('REMOTE_ADDR'),
                    metadata={'updated_fields': list(serializer.validated_data.keys())}
                )
                
                logger.info(f"Medical history updated for patient {patient.patient_id} by {request.user}")
                
                return Response(serializer.data)
    
    @action(detail=True, methods=['get', 'put'])
    def emergency_contact(self, request, pk=None):
        """
        Get or update emergency contact information.
        """
        patient = self.get_object()
        
        if request.method == 'GET':
            serializer = EmergencyContactSerializer({
                'name': patient.emergency_contact_name,
                'phone': patient.emergency_contact_phone,
                'relation': patient.emergency_contact_relation,
            })
            return Response(serializer.data)
        
        elif request.method == 'PUT':
            serializer = EmergencyContactSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                # Update emergency contact
                patient.emergency_contact_name = serializer.validated_data.get('name', patient.emergency_contact_name)
                patient.emergency_contact_phone = serializer.validated_data.get('phone', patient.emergency_contact_phone)
                patient.emergency_contact_relation = serializer.validated_data.get('relation', patient.emergency_contact_relation)
                patient.save()
                
                # Log update
                log_action(
                    instance=patient,
                    action='EMERGENCY_CONTACT_UPDATE',
                    user=request.user,
                    branch=patient.registered_branch,
                    device_id=request.META.get('HTTP_X_DEVICE_ID'),
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                
                logger.info(f"Emergency contact updated for patient {patient.patient_id} by {request.user}")
                
                return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Advanced search for patients.
        """
        serializer = PatientSearchSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Start with base queryset
            queryset = self.get_queryset()
            
            # Apply filters
            data = serializer.validated_data
            
            if data.get('q'):
                search_term = data['q']
                queryset = queryset.filter(
                    Q(patient_id__icontains=search_term) |
                    Q(user__email__icontains=search_term) |
                    Q(user__full_name__icontains=search_term) |
                    Q(user__phone__icontains=search_term) |
                    Q(insurance_id__icontains=search_term)
                )
            
            if data.get('gender'):
                queryset = queryset.filter(gender=data['gender'])
            
            if data.get('blood_group'):
                queryset = queryset.filter(blood_group=data['blood_group'])
            
            if data.get('has_insurance') is not None:
                if data['has_insurance']:
                    queryset = queryset.filter(is_insurance_verified=True)
                else:
                    queryset = queryset.filter(is_insurance_verified=False)
            
            if data.get('branch_id'):
                queryset = queryset.filter(registered_branch_id=data['branch_id'])
            
            # Date filters
            if data.get('registered_after'):
                queryset = queryset.filter(registered_at__date__gte=data['registered_after'])
            
            if data.get('registered_before'):
                queryset = queryset.filter(registered_at__date__lte=data['registered_before'])
            
            # Age filters (requires date_of_birth)
            if data.get('age_min') or data.get('age_max'):
                today = timezone.now().date()
                
                if data.get('age_max'):
                    min_birth_date = today.replace(year=today.year - data['age_max'] - 1)
                    queryset = queryset.filter(date_of_birth__gte=min_birth_date)
                
                if data.get('age_min'):
                    max_birth_date = today.replace(year=today.year - data['age_min'])
                    queryset = queryset.filter(date_of_birth__lte=max_birth_date)
            
            # Apply pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = PatientListSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            # If no pagination, return all
            serializer = PatientListSerializer(queryset, many=True)
            return Response(serializer.data)
        
        except Exception as e:
            logger.error(f"Error searching patients: {str(e)}")
            return Response(
                {'error': f'Search failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get patient statistics.
        """
        try:
            # Get base queryset
            queryset = self.get_queryset()
            
            today = timezone.now().date()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)
            
            # Basic counts
            total_patients = queryset.count()
            patients_today = queryset.filter(created_at__date=today).count()
            patients_this_week = queryset.filter(created_at__date__gte=week_ago).count()
            patients_this_month = queryset.filter(created_at__date__gte=month_ago).count()
            
            # Gender distribution
            gender_distribution = dict(queryset.values('gender').annotate(
                count=Count('id')
            ).values_list('gender', 'count'))
            
            # Blood group distribution
            blood_group_distribution = dict(queryset.exclude(blood_group='').values('blood_group').annotate(
                count=Count('id')
            ).values_list('blood_group', 'count'))
            
            # Age distribution
            age_groups = {
                '0-18': 0,
                '19-30': 0,
                '31-45': 0,
                '46-60': 0,
                '61+': 0,
            }
            
            for patient in queryset.exclude(date_of_birth__isnull=True):
                age = today.year - patient.date_of_birth.year - (
                    (today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day)
                )
                
                if age <= 18:
                    age_groups['0-18'] += 1
                elif age <= 30:
                    age_groups['19-30'] += 1
                elif age <= 45:
                    age_groups['31-45'] += 1
                elif age <= 60:
                    age_groups['46-60'] += 1
                else:
                    age_groups['61+'] += 1
            
            # Insurance stats
            insurance_stats = {
                'verified': queryset.filter(is_insurance_verified=True).count(),
                'unverified': queryset.filter(is_insurance_verified=False).count(),
                'total_with_insurance': queryset.exclude(insurance_provider='').count(),
            }
            
            # Branch distribution
            branch_distribution = dict(queryset.filter(registered_branch__isnull=False).values(
                'registered_branch__name'
            ).annotate(
                count=Count('id')
            ).values_list('registered_branch__name', 'count'))
            
            # Prepare response
            stats_data = {
                'total_patients': total_patients,
                'patients_today': patients_today,
                'patients_this_week': patients_this_week,
                'patients_this_month': patients_this_month,
                'gender_distribution': gender_distribution,
                'age_distribution': age_groups,
                'blood_group_distribution': blood_group_distribution,
                'insurance_stats': insurance_stats,
                'branch_distribution': branch_distribution,
            }
            
            serializer = PatientStatsSerializer(data=stats_data)
            if serializer.is_valid():
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error getting patient stats: {str(e)}")
            return Response(
                {'error': f'Failed to get statistics: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def import_patients(self, request):
        """
        Import patients from CSV/Excel file.
        """
        if not (request.user.role in ['receptionist', 'clinic_manager', 'super_admin']):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = PatientImportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        file = serializer.validated_data['file']
        branch_id = serializer.validated_data.get('branch_id')
        send_welcome_email = serializer.validated_data['send_welcome_email']
        
        try:
            import pandas as pd
            
            # Read file based on extension
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.name.endswith('.xlsx') or file.name.endswith('.xls'):
                df = pd.read_excel(file)
            else:
                return Response(
                    {'error': 'Unsupported file format. Use CSV or Excel.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate required columns
            required_columns = ['email', 'full_name', 'phone']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return Response(
                    {'error': f'Missing required columns: {missing_columns}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            imported = 0
            updated = 0
            errors = []
            
            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        patient_data = {
                            'email': row['email'],
                            'full_name': row['full_name'],
                            'phone': str(row['phone']),
                            'date_of_birth': row.get('date_of_birth'),
                            'gender': row.get('gender', ''),
                            'blood_group': row.get('blood_group', ''),
                            'allergies': row.get('allergies', ''),
                            'chronic_conditions': row.get('chronic_conditions', ''),
                            'current_medications': row.get('current_medications', ''),
                        }
                        
                        # Check if patient already exists
                        existing_user = User.objects.filter(email=patient_data['email']).first()
                        
                        if existing_user:
                            # Check if user already has patient profile
                            if hasattr(existing_user, 'patient_profile'):
                                # Update existing patient
                                patient = existing_user.patient_profile
                                
                                # Update fields
                                for field in ['date_of_birth', 'gender', 'blood_group', 
                                            'allergies', 'chronic_conditions', 'current_medications']:
                                    if field in row and pd.notna(row[field]):
                                        setattr(patient, field, row[field])
                                
                                patient.save()
                                updated += 1
                            else:
                                # Create patient profile for existing user
                                patient_data.pop('email')
                                patient_data.pop('full_name')
                                patient_data.pop('phone')
                                
                                Patient.objects.create(
                                    user=existing_user,
                                    **patient_data
                                )
                                imported += 1
                        else:
                            # Create new patient with user
                            serializer = PatientCreateSerializer(
                                data=patient_data,
                                context={'request': request}
                            )
                            
                            if serializer.is_valid():
                                patient = serializer.save()
                                
                                # Set branch if provided
                                if branch_id:
                                    from apps.clinics.models import Branch
                                    try:
                                        branch = Branch.objects.get(id=branch_id)
                                        patient.registered_branch = branch
                                        patient.save()
                                    except Branch.DoesNotExist:
                                        pass
                                
                                imported += 1
                            else:
                                errors.append({
                                    'row': index + 2,
                                    'email': patient_data['email'],
                                    'errors': serializer.errors
                                })
                    
                    except Exception as e:
                        errors.append({
                            'row': index + 2,
                            'email': row.get('email', 'unknown'),
                            'error': str(e)
                        })
                        continue
            
            return Response({
                'success': True,
                'imported': imported,
                'updated': updated,
                'total_rows': len(df),
                'errors': errors if errors else None,
                'message': f'Imported {imported} new patients, updated {updated} existing patients'
            })
        
        except Exception as e:
            logger.error(f"Error importing patients: {str(e)}")
            return Response(
                {'error': f'Import failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def export_patients(self, request):
        """
        Export patients to CSV/Excel/JSON.
        """
        if not (request.user.role in ['receptionist', 'clinic_manager', 'super_admin']):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = PatientExportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        export_format = serializer.validated_data['format']
        include_medical_history = serializer.validated_data['include_medical_history']
        include_appointments = serializer.validated_data['include_appointments']
        branch_id = serializer.validated_data.get('branch_id')
        
        try:
            # Get patients
            queryset = self.get_queryset()
            
            if branch_id:
                queryset = queryset.filter(registered_branch_id=branch_id)
            
            # Get appointment data if requested
            appointments_data = {}
            if include_appointments:
                from apps.visits.models import Appointment
                
                for patient in queryset:
                    appointments = Appointment.objects.filter(
                        patient=patient
                    ).values('appointment_date', 'status', 'type')
                    appointments_data[patient.id] = list(appointments)
            
            if export_format == 'csv':
                # Generate CSV
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = 'attachment; filename="patients_export.csv"'
                
                writer = csv.writer(response)
                
                # Write header
                headers = [
                    'Patient ID', 'Full Name', 'Email', 'Phone', 'Date of Birth', 'Age',
                    'Gender', 'Blood Group', 'Registered At', 'Branch', 'Insurance Verified',
                    'Insurance Provider', 'Insurance ID'
                ]
                
                if include_medical_history:
                    headers.extend(['Allergies', 'Chronic Conditions', 'Current Medications'])
                
                writer.writerow(headers)
                
                # Write data
                for patient in queryset:
                    row = [
                        patient.patient_id,
                        patient.user.full_name,
                        patient.user.email,
                        patient.user.phone,
                        patient.date_of_birth,
                        self._calculate_age(patient.date_of_birth),
                        patient.get_gender_display(),
                        patient.blood_group,
                        patient.registered_at,
                        patient.registered_branch.name if patient.registered_branch else '',
                        'Yes' if patient.is_insurance_verified else 'No',
                        patient.insurance_provider,
                        patient.insurance_id,
                    ]
                    
                    if include_medical_history:
                        row.extend([
                            patient.allergies,
                            patient.chronic_conditions,
                            patient.current_medications,
                        ])
                    
                    writer.writerow(row)
                
                return response
            
            elif export_format == 'excel':
                # Generate Excel
                data = []
                for patient in queryset:
                    row = {
                        'Patient ID': patient.patient_id,
                        'Full Name': patient.user.full_name,
                        'Email': patient.user.email,
                        'Phone': patient.user.phone,
                        'Date of Birth': patient.date_of_birth,
                        'Age': self._calculate_age(patient.date_of_birth),
                        'Gender': patient.get_gender_display(),
                        'Blood Group': patient.blood_group,
                        'Registered At': patient.registered_at,
                        'Branch': patient.registered_branch.name if patient.registered_branch else '',
                        'Insurance Verified': 'Yes' if patient.is_insurance_verified else 'No',
                        'Insurance Provider': patient.insurance_provider,
                        'Insurance ID': patient.insurance_id,
                    }
                    
                    if include_medical_history:
                        row.update({
                            'Allergies': patient.allergies,
                            'Chronic Conditions': patient.chronic_conditions,
                            'Current Medications': patient.current_medications,
                        })
                    
                    if include_appointments:
                        row['Appointments'] = json.dumps(appointments_data.get(patient.id, []))
                    
                    data.append(row)
                
                df = pd.DataFrame(data)
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Patients', index=False)
                
                output.seek(0)
                response = HttpResponse(
                    output.read(),
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = 'attachment; filename="patients_export.xlsx"'
                return response
            
            else:  # JSON format (default)
                serializer = PatientListSerializer(queryset, many=True)
                data = serializer.data
                
                if include_medical_history:
                    for patient_data in data:
                        patient = Patient.objects.get(id=patient_data['id'])
                        patient_data['allergies'] = patient.allergies
                        patient_data['chronic_conditions'] = patient.chronic_conditions
                        patient_data['current_medications'] = patient.current_medications
                
                if include_appointments:
                    for patient_data in data:
                        patient_id = patient_data['id']
                        patient_data['appointments'] = appointments_data.get(patient_id, [])
                
                return JsonResponse(data, safe=False)
        
        except Exception as e:
            logger.error(f"Error exporting patients: {str(e)}")
            return Response(
                {'error': f'Export failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _calculate_age(self, date_of_birth):
        """Calculate age from date of birth"""
        if not date_of_birth:
            return None
        
        today = timezone.now().date()
        return today.year - date_of_birth.year - (
            (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
        )


# ============================
# Public Patient Registration
# ============================

class PatientRegistrationView(generics.CreateAPIView):
    """
    Public endpoint for patient self-registration.
    """
    permission_classes = [AllowAny]
    serializer_class = PatientCreateSerializer
    
    def create(self, request, *args, **kwargs):
        """
        Create patient with welcome email.
        """
        response = super().create(request, *args, **kwargs)
        
        # TODO: Send welcome email
        # if response.status_code == status.HTTP_201_CREATED:
        #     send_welcome_email(response.data['user']['email'])
        
        return response


# ============================
# Patient Dashboard View
# ============================

class PatientDashboardView(APIView):
    """
    Patient dashboard with summary data.
    """
    permission_classes = [IsAuthenticatedAndActive]
    
    def get(self, request):
        """
        Get patient dashboard data.
        """
        try:
            patient = Patient.objects.get(user=request.user)
            
            from apps.visits.models import Appointment
            from apps.billing.models import Invoice
            
            today = timezone.now().date()
            
            # Upcoming appointments
            upcoming_appointments = Appointment.objects.filter(
                patient=patient,
                appointment_date__gte=today,
                status__in=['scheduled', 'confirmed']
            ).order_by('appointment_date')[:5]
            
            # Recent invoices
            recent_invoices = Invoice.objects.filter(
                patient=patient
            ).order_by('-created_at')[:5]
            
            # Next appointment
            next_appointment = Appointment.objects.filter(
                patient=patient,
                appointment_date__gte=today,
                status__in=['scheduled', 'confirmed']
            ).order_by('appointment_date').first()
            
            # Treatment summary
            from apps.treatments.models import Treatment
            treatments = Treatment.objects.filter(patient=patient)
            total_treatments = treatments.count()
            active_treatments = treatments.filter(status='in_progress').count()
            completed_treatments = treatments.filter(status='completed').count()
            
            # Payment summary
            total_invoices = Invoice.objects.filter(patient=patient)
            pending_amount = total_invoices.filter(payment_status='pending').aggregate(
                total=Sum('total_amount')
            )['total'] or 0
            
            dashboard_data = {
                'patient': PatientSerializer(patient).data,
                'next_appointment': {
                    'date': next_appointment.appointment_date if next_appointment else None,
                    'time': next_appointment.start_time if next_appointment else None,
                    'doctor': next_appointment.doctor.user.full_name if next_appointment and next_appointment.doctor else None,
                },
                'upcoming_appointments': [
                    {
                        'date': apt.appointment_date,
                        'time': apt.start_time,
                        'doctor': apt.doctor.user.full_name if apt.doctor else None,
                        'type': apt.type,
                    }
                    for apt in upcoming_appointments
                ],
                'recent_invoices': [
                    {
                        'invoice_number': inv.invoice_number,
                        'date': inv.created_at.date(),
                        'amount': inv.total_amount,
                        'status': inv.payment_status,
                    }
                    for inv in recent_invoices
                ],
                'treatment_summary': {
                    'total': total_treatments,
                    'active': active_treatments,
                    'completed': completed_treatments,
                },
                'financial_summary': {
                    'pending_amount': pending_amount,
                    'total_invoices': total_invoices.count(),
                },
            }
            
            return Response(dashboard_data)
        
        except Patient.DoesNotExist:
            return Response(
                {'error': 'Patient profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        except Exception as e:
            logger.error(f"Error getting patient dashboard: {str(e)}")
            return Response(
                {'error': f'Failed to get dashboard: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ============================
# Health Check View
# ============================

class PatientsHealthCheckView(APIView):
    """
    Health check for patients system.
    """
    permission_classes = [IsAuthenticated, IsReceptionist]
    
    def get(self, request):
        """
        Check patients system health.
        """
        try:
            # Check database connections
            total_patients = Patient.objects.filter(
                deleted_at__isnull=True
            ).count()
            
            active_patients = Patient.objects.filter(
                user__is_active=True,
                deleted_at__isnull=True
            ).count()
            
            # Check for patients without user
            patients_without_user = Patient.objects.filter(
                user__isnull=True,
                deleted_at__isnull=True
            ).count()
            
            # Check for duplicate patient IDs
            duplicate_ids = Patient.objects.values('patient_id').annotate(
                count=Count('id')
            ).filter(count__gt=1).count()
            
            health_data = {
                'status': 'healthy',
                'database': 'connected',
                'statistics': {
                    'total_patients': total_patients,
                    'active_patients': active_patients,
                    'patients_without_user': patients_without_user,
                    'duplicate_patient_ids': duplicate_ids,
                },
                'checks': {
                    'database_connection': True,
                    'user_integrity': patients_without_user == 0,
                    'id_integrity': duplicate_ids == 0,
                },
                'timestamp': timezone.now()
            }
            
            return Response(health_data)
        
        except Exception as e:
            logger.error(f"Patients health check failed: {str(e)}")
            return Response(
                {
                    'status': 'unhealthy',
                    'error': str(e),
                    'timestamp': timezone.now()
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )