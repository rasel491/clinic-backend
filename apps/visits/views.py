# apps/visits/views.py
from django.utils import timezone
from datetime import datetime, timedelta, date
from django.db.models import Q, Count, Avg, DurationField, ExpressionWrapper, F, Sum
from django.db import transaction
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from rest_framework import viewsets, mixins, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
import pandas as pd
import json

from core.mixins.audit_fields import AuditFieldsMixin
from core.permissions import *
from core.constants import VisitStatus, UserRoles
from core.utils.excel_export import export_to_excel
from ..notifications.services import NotificationService

from .models import (
    Visit, Appointment, Queue, VisitDocument, VisitVitalSign
)
from .serializers import (
    VisitSerializer, VisitStatusUpdateSerializer,
    AppointmentSerializer, AppointmentStatusUpdateSerializer,
    QueueSerializer, QueueStatusUpdateSerializer,
    VisitVitalSignSerializer, VisitDocumentSerializer,
    VisitDashboardSerializer, DoctorScheduleSerializer
)
from apps.doctors.models import Doctor
from apps.patients.models import Patient
from apps.clinics.models import Branch


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


class VisitFilter(django_filters.FilterSet):
    """Filter for visits"""
    
    date_from = django_filters.DateFilter(field_name='scheduled_date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='scheduled_date', lookup_expr='lte')
    patient_name = django_filters.CharFilter(method='filter_patient_name')
    doctor_name = django_filters.CharFilter(method='filter_doctor_name')
    branch_name = django_filters.CharFilter(method='filter_branch_name')
    
    class Meta:
        model = Visit
        fields = [
            'status', 'appointment_source', 'visit_type',
            'priority', 'doctor', 'branch', 'patient',
            'is_follow_up', 'insurance_verified'
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
    
    def filter_branch_name(self, queryset, name, value):
        return queryset.filter(branch__name__icontains=value)


class AppointmentFilter(django_filters.FilterSet):
    """Filter for appointments"""
    
    date_from = django_filters.DateFilter(field_name='appointment_date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='appointment_date', lookup_expr='lte')
    upcoming = django_filters.BooleanFilter(method='filter_upcoming')
    today = django_filters.BooleanFilter(method='filter_today')
    patient_name = django_filters.CharFilter(method='filter_patient_name')
    
    class Meta:
        model = Appointment
        fields = [
            'status', 'visit_type', 'doctor', 'branch', 'patient',
            'is_waiting_list', 'is_recurring'
        ]
    
    def filter_upcoming(self, queryset, name, value):
        if value:
            return queryset.filter(
                appointment_date__gte=timezone.now().date(),
                status__in=['SCHEDULED', 'CONFIRMED']
            )
        return queryset
    
    def filter_today(self, queryset, name, value):
        if value:
            return queryset.filter(
                appointment_date=timezone.now().date(),
                status__in=['SCHEDULED', 'CONFIRMED']
            )
        return queryset
    
    def filter_patient_name(self, queryset, name, value):
        return queryset.filter(
            Q(patient__user__first_name__icontains=value) |
            Q(patient__user__last_name__icontains=value) |
            Q(patient__user__full_name__icontains=value)
        )


# ===========================================
# VIEWSETS
# ===========================================
class VisitViewSet(viewsets.ModelViewSet):
    """ViewSet for Visit model"""
    
    queryset = Visit.objects.select_related(
        'patient', 'patient__user',
        'doctor', 'doctor__user',
        'branch', 'assigned_counter'
    ).prefetch_related(
        'vital_signs', 'documents', 'follow_ups'
    ).all()
    
    serializer_class = VisitSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = VisitFilter
    search_fields = ['visit_id', 'chief_complaint', 'symptoms']
    ordering_fields = ['scheduled_date', 'scheduled_time', 'created_at', 'queue_number']
    ordering = ['-scheduled_date', '-scheduled_time']
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated & (IsStaff | HasBranchAccess)]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated & (IsReceptionist | IsDoctor | IsManager)]
        elif self.action in ['check_in', 'checkout', 'complete_consultation']:
            permission_classes = [IsAuthenticated & (IsDoctor | IsManager)]
        elif self.action in ['cancel', 'mark_no_show']:
            permission_classes = [IsAuthenticated & (IsReceptionist | IsManager)]
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
            # If user has branch access, filter by accessible branches
            if hasattr(user, 'user_branches'):
                branch_ids = user.user_branches.filter(
                    is_active=True
                ).values_list('branch_id', flat=True)
                return queryset.filter(branch_id__in=branch_ids)
            return queryset
        
        # Doctors can see their own visits
        if user.role == UserRoles.DOCTOR:
            try:
                doctor = user.doctor_profile
                return queryset.filter(doctor=doctor)
            except:
                return queryset.none()
        
        # Receptionists can see visits in their branch
        if user.role == UserRoles.RECEPTIONIST:
            if hasattr(user, 'user_branches'):
                branch_ids = user.user_branches.filter(
                    is_active=True
                ).values_list('branch_id', flat=True)
                return queryset.filter(branch_id__in=branch_ids)
        
        # Cashiers can see visits for billing
        if user.role == UserRoles.CASHIER:
            return queryset.filter(status__in=[
                VisitStatus.READY_FOR_BILLING,
                VisitStatus.PAID,
                VisitStatus.COMPLETED
            ])
        
        return queryset.none()
    
    def perform_create(self, serializer):
        """Create visit with audit fields"""
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user
        )
    
    def perform_update(self, serializer):
        """Update visit with audit fields"""
        serializer.save(updated_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def check_in(self, request, pk=None):
        """Mark visit as checked in"""
        visit = self.get_object()
        
        if visit.status != VisitStatus.REGISTERED:
            return Response({
                'error': f'Cannot check in. Current status: {visit.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                visit.mark_checked_in()
                
                # Update queue if exists
                if hasattr(visit, 'queue_entry'):
                    visit.queue_entry.mark_called()
                
                # Send notification
                NotificationService.send_queue_update(visit.queue_entry)
                
                return Response({
                    'message': 'Patient checked in successfully',
                    'status': visit.status,
                    'checkin_time': visit.actual_checkin
                })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def start_consultation(self, request, pk=None):
        """Start consultation"""
        visit = self.get_object()
        
        if visit.status != VisitStatus.REGISTERED:
            return Response({
                'error': f'Cannot start consultation. Current status: {visit.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                doctor_id = request.data.get('doctor_id')
                if doctor_id:
                    doctor = Doctor.objects.get(id=doctor_id)
                    visit.doctor = doctor
                
                visit.status = VisitStatus.IN_CONSULTATION
                visit.actual_checkin = timezone.now()
                visit.save()
                
                return Response({
                    'message': 'Consultation started',
                    'status': visit.status,
                    'doctor': visit.doctor.user.get_full_name() if visit.doctor else None
                })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def complete_consultation(self, request, pk=None):
        """Complete consultation with notes"""
        visit = self.get_object()
        
        if visit.status != VisitStatus.IN_CONSULTATION:
            return Response({
                'error': f'Cannot complete consultation. Current status: {visit.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = VisitStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                data = serializer.validated_data
                visit.mark_consultation_complete(
                    diagnosis=data.get('diagnosis', ''),
                    clinical_notes=data.get('clinical_notes', ''),
                    recommendations=data.get('recommendations', '')
                )
                
                # Update queue
                if hasattr(visit, 'queue_entry'):
                    visit.queue_entry.mark_completed()
                
                return Response({
                    'message': 'Consultation completed successfully',
                    'status': visit.status,
                    'checkout_time': visit.actual_checkout
                })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel visit"""
        visit = self.get_object()
        
        if visit.status in [VisitStatus.COMPLETED, VisitStatus.CANCELLED, VisitStatus.PAID]:
            return Response({
                'error': f'Cannot cancel. Current status: {visit.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = VisitStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                visit.status = VisitStatus.CANCELLED
                visit.save()
                
                # Cancel associated queue
                if hasattr(visit, 'queue_entry'):
                    visit.queue_entry.status = 'CANCELLED'
                    visit.queue_entry.save()
                
                # Cancel associated appointment if exists
                if hasattr(visit, 'appointment'):
                    appointment = visit.appointment
                    appointment.status = 'CANCELLED'
                    appointment.cancellation_reason = serializer.validated_data.get('notes', '')
                    appointment.cancelled_at = timezone.now()
                    appointment.cancelled_by = request.user
                    appointment.save()
                
                return Response({
                    'message': 'Visit cancelled successfully',
                    'status': visit.status
                })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def mark_no_show(self, request, pk=None):
        """Mark visit as no show"""
        visit = self.get_object()
        
        if visit.status not in [VisitStatus.REGISTERED]:
            return Response({
                'error': f'Cannot mark as no show. Current status: {visit.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                visit.status = VisitStatus.NO_SHOW
                visit.save()
                
                # Update associated appointment if exists
                if hasattr(visit, 'appointment'):
                    appointment = visit.appointment
                    appointment.status = 'NO_SHOW'
                    appointment.save()
                
                return Response({
                    'message': 'Marked as no show',
                    'status': visit.status
                })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def todays_visits(self, request):
        """Get today's visits"""
        today = timezone.now().date()
        queryset = self.get_queryset().filter(scheduled_date=today)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def active_visits(self, request):
        """Get active visits (not completed/cancelled)"""
        queryset = self.get_queryset().filter(
            status__in=[VisitStatus.REGISTERED, VisitStatus.IN_CONSULTATION]
        )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get visit statistics"""
        branch_id = request.query_params.get('branch_id')
        date_from = request.query_params.get('date_from', timezone.now().date() - timedelta(days=30))
        date_to = request.query_params.get('date_to', timezone.now().date())
        
        queryset = self.get_queryset().filter(
            scheduled_date__range=[date_from, date_to]
        )
        
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        
        total = queryset.count()
        by_status = queryset.values('status').annotate(count=Count('id')).order_by('-count')
        by_source = queryset.values('appointment_source').annotate(count=Count('id')).order_by('-count')
        by_doctor = queryset.values('doctor__user__full_name').annotate(
            count=Count('id'),
            avg_duration=Avg(ExpressionWrapper(
                F('actual_checkout') - F('actual_checkin'),
                output_field=DurationField()
            ))
        ).order_by('-count')
        
        # Calculate average wait time
        avg_wait = queryset.filter(wait_duration__isnull=False).aggregate(
            avg_wait=Avg('wait_duration')
        )['avg_wait']
        
        # Calculate average consultation time
        avg_consultation = queryset.filter(consultation_duration__isnull=False).aggregate(
            avg_consultation=Avg('consultation_duration')
        )['avg_consultation']
        
        return Response({
            'total': total,
            'by_status': list(by_status),
            'by_source': list(by_source),
            'by_doctor': list(by_doctor),
            'avg_wait_time': avg_wait.total_seconds() / 60 if avg_wait else 0,  # in minutes
            'avg_consultation_time': avg_consultation.total_seconds() / 60 if avg_consultation else 0,
            'period': {'from': date_from, 'to': date_to}
        })
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export visits to Excel"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Prepare data
        data = []
        for visit in queryset:
            data.append({
                'Visit ID': visit.visit_id,
                'Patient': visit.patient.user.get_full_name(),
                'Doctor': visit.doctor.user.get_full_name() if visit.doctor else '',
                'Branch': visit.branch.name,
                'Date': visit.scheduled_date,
                'Time': visit.scheduled_time,
                'Status': visit.get_status_display(),
                'Type': visit.get_visit_type_display(),
                'Chief Complaint': visit.chief_complaint,
                'Check-in': visit.actual_checkin,
                'Check-out': visit.actual_checkout,
                'Wait Time (min)': visit.wait_duration.total_seconds() / 60 if visit.wait_duration else 0,
                'Consultation Time (min)': visit.consultation_duration.total_seconds() / 60 if visit.consultation_duration else 0,
            })
        
        # Export to Excel
        df = pd.DataFrame(data)
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=visits_export.xlsx'
        
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Visits', index=False)
        
        return response


class AppointmentViewSet(viewsets.ModelViewSet):
    """ViewSet for Appointment model"""
    
    queryset = Appointment.objects.select_related(
        'patient', 'patient__user',
        'doctor', 'doctor__user',
        'branch', 'visit', 'cancelled_by'
    ).all()
    
    serializer_class = AppointmentSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = AppointmentFilter
    search_fields = ['appointment_id', 'purpose', 'notes']
    ordering_fields = ['appointment_date', 'start_time', 'created_at']
    ordering = ['appointment_date', 'start_time']
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve', 'available_slots']:
            permission_classes = [IsAuthenticated & (IsStaff | HasBranchAccess)]
        elif self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated & (IsReceptionist | IsDoctor | IsManager)]
        elif self.action in ['cancel', 'confirm', 'send_reminder']:
            permission_classes = [IsAuthenticated & (IsReceptionist | IsManager)]
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
        
        # Doctors can see their own appointments
        if user.role == UserRoles.DOCTOR:
            try:
                doctor = user.doctor_profile
                return queryset.filter(doctor=doctor)
            except:
                return queryset.none()
        
        # Receptionists can see appointments in their branch
        if user.role == UserRoles.RECEPTIONIST:
            if hasattr(user, 'user_branches'):
                branch_ids = user.user_branches.filter(
                    is_active=True
                ).values_list('branch_id', flat=True)
                return queryset.filter(branch_id__in=branch_ids)
        
        return queryset.none()
    
    def perform_create(self, serializer):
        """Create appointment with audit fields"""
        appointment = serializer.save()
        
        # Send confirmation notification
        NotificationService.send_appointment_reminder(appointment)
    
    def perform_update(self, serializer):
        """Update appointment with audit fields"""
        serializer.save()
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm appointment"""
        appointment = self.get_object()
        
        if appointment.status != 'SCHEDULED':
            return Response({
                'error': f'Cannot confirm. Current status: {appointment.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        appointment.status = 'CONFIRMED'
        appointment.save()
        
        # Send confirmation notification
        NotificationService.send_appointment_reminder(appointment)
        
        return Response({
            'message': 'Appointment confirmed',
            'status': appointment.status
        })
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel appointment"""
        appointment = self.get_object()
        
        if appointment.status in ['CANCELLED', 'COMPLETED', 'NO_SHOW']:
            return Response({
                'error': f'Cannot cancel. Current status: {appointment.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = AppointmentStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        appointment.status = 'CANCELLED'
        appointment.cancellation_reason = data.get('cancellation_reason', '')
        appointment.cancelled_at = timezone.now()
        appointment.cancelled_by = request.user
        appointment.save()
        
        return Response({
            'message': 'Appointment cancelled',
            'status': appointment.status
        })
    
    @action(detail=True, methods=['post'])
    def convert_to_visit(self, request, pk=None):
        """Convert appointment to visit"""
        appointment = self.get_object()
        
        if appointment.status not in ['SCHEDULED', 'CONFIRMED']:
            return Response({
                'error': f'Cannot convert. Current status: {appointment.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                visit = appointment.convert_to_visit()
                
                # Send visit confirmation
                NotificationService.send_visit_confirmation(visit)
                
                return Response({
                    'message': 'Appointment converted to visit',
                    'visit_id': visit.visit_id,
                    'visit_status': visit.status
                })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def send_reminder(self, request, pk=None):
        """Send appointment reminder"""
        appointment = self.get_object()
        
        if appointment.status not in ['SCHEDULED', 'CONFIRMED']:
            return Response({
                'error': f'Cannot send reminder. Current status: {appointment.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        success = NotificationService.send_appointment_reminder(appointment)
        
        if success:
            appointment.reminder_sent = True
            appointment.reminder_sent_at = timezone.now()
            appointment.save()
            
            return Response({
                'message': 'Reminder sent successfully',
                'sent_at': appointment.reminder_sent_at
            })
        else:
            return Response({
                'error': 'Failed to send reminder'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming appointments"""
        queryset = self.get_queryset().filter(
            appointment_date__gte=timezone.now().date(),
            status__in=['SCHEDULED', 'CONFIRMED']
        ).order_by('appointment_date', 'start_time')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def todays(self, request):
        """Get today's appointments"""
        today = timezone.now().date()
        queryset = self.get_queryset().filter(
            appointment_date=today,
            status__in=['SCHEDULED', 'CONFIRMED']
        ).order_by('start_time')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def available_slots(self, request):
        """Get available appointment slots for a doctor"""
        doctor_id = request.query_params.get('doctor_id')
        branch_id = request.query_params.get('branch_id')
        date = request.query_params.get('date', timezone.now().date())
        
        if not doctor_id:
            return Response({'error': 'doctor_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            doctor = Doctor.objects.get(id=doctor_id)
            date_obj = datetime.strptime(date, '%Y-%m-%d').date() if isinstance(date, str) else date
            
            # Get doctor's schedule for that day
            slots = doctor.get_available_slots(date_obj, branch_id)
            
            # Get existing appointments for that day
            existing_appointments = Appointment.objects.filter(
                doctor=doctor,
                appointment_date=date_obj,
                status__in=['SCHEDULED', 'CONFIRMED']
            )
            
            # Mark slots as booked
            available_slots = []
            for slot in slots:
                slot_start = datetime.combine(date_obj, slot['start_time'])
                slot_end = datetime.combine(date_obj, slot['end_time'])
                
                # Check if slot is booked
                is_booked = False
                for appointment in existing_appointments:
                    appt_start = datetime.combine(date_obj, appointment.start_time)
                    appt_end = datetime.combine(date_obj, appointment.end_time)
                    
                    if not (slot_end <= appt_start or slot_start >= appt_end):
                        is_booked = True
                        break
                
                if not is_booked:
                    available_slots.append({
                        'start_time': slot['start_time'],
                        'end_time': slot['end_time'],
                        'duration': slot['duration'],
                        'is_available': True
                    })
            
            return Response({
                'doctor': doctor.user.get_full_name(),
                'date': date_obj,
                'available_slots': available_slots,
                'total_slots': len(available_slots)
            })
            
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class QueueViewSet(viewsets.ModelViewSet):
    """ViewSet for Queue model"""
    
    queryset = Queue.objects.select_related(
        'branch', 'doctor', 'doctor__user',
        'visit', 'visit__patient', 'visit__patient__user',
        'counter'
    ).all()
    
    serializer_class = QueueSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['branch', 'doctor', 'status', 'counter']
    ordering_fields = ['queue_number', 'joined_at']
    ordering = ['queue_number']
    
    def get_permissions(self):
        """Set permissions based on action"""
        permission_classes = [IsAuthenticated & (IsReceptionist | IsDoctor | IsManager)]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter queryset based on user role and branch"""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Get branch from request or user's branches
        branch_id = self.request.query_params.get('branch')
        if not branch_id and hasattr(user, 'user_branches'):
            branch_ids = user.user_branches.filter(
                is_active=True
            ).values_list('branch_id', flat=True)
            queryset = queryset.filter(branch_id__in=branch_ids)
        elif branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        else:
            # Default to active queues
            queryset = queryset.filter(status__in=['WAITING', 'IN_PROGRESS'])
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def call_patient(self, request, pk=None):
        """Call patient from queue"""
        queue = self.get_object()
        
        if queue.status != 'WAITING':
            return Response({
                'error': f'Cannot call patient. Current status: {queue.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():
                queue.mark_called()
                
                # Update visit status if needed
                visit = queue.visit
                if visit.status == VisitStatus.REGISTERED:
                    visit.mark_checked_in(queue.doctor)
                
                # Send notification
                NotificationService.send_queue_update(queue)
                
                return Response({
                    'message': f'Patient #{queue.queue_number} called',
                    'called_at': queue.called_at,
                    'status': queue.status
                })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def start_consultation(self, request, pk=None):
        """Start consultation for queue entry"""
        queue = self.get_object()
        
        if queue.status != 'IN_PROGRESS':
            return Response({
                'error': f'Cannot start consultation. Current status: {queue.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        queue.started_at = timezone.now()
        queue.save()
        
        return Response({
            'message': 'Consultation started',
            'started_at': queue.started_at
        })
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete queue entry"""
        queue = self.get_object()
        
        if queue.status not in ['IN_PROGRESS', 'WAITING']:
            return Response({
                'error': f'Cannot complete. Current status: {queue.get_status_display()}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        queue.mark_completed()
        
        # Update visit status if needed
        visit = queue.visit
        if visit.status == VisitStatus.IN_CONSULTATION:
            visit.status = VisitStatus.READY_FOR_BILLING
            visit.save()
        
        return Response({
            'message': 'Queue entry completed',
            'completed_at': queue.completed_at,
            'status': queue.status
        })
    
    @action(detail=True, methods=['post'])
    def skip(self, request, pk=None):
        """Skip patient in queue"""
        queue = self.get_object()
        
        serializer = QueueStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        queue.skip()
        queue.notes = serializer.validated_data.get('notes', '')
        queue.save()
        
        return Response({
            'message': 'Patient skipped in queue',
            'status': queue.status
        })
    
    @action(detail=False, methods=['get'])
    def current_queue(self, request):
        """Get current queue for branch"""
        branch_id = request.query_params.get('branch')
        if not branch_id:
            return Response({'error': 'branch is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        waiting = self.get_queryset().filter(
            branch_id=branch_id,
            status='WAITING'
        ).order_by('queue_number')
        
        in_progress = self.get_queryset().filter(
            branch_id=branch_id,
            status='IN_PROGRESS'
        ).order_by('called_at')
        
        waiting_serializer = self.get_serializer(waiting, many=True)
        in_progress_serializer = self.get_serializer(in_progress, many=True)
        
        return Response({
            'waiting': waiting_serializer.data,
            'in_progress': in_progress_serializer.data,
            'total_waiting': waiting.count(),
            'total_in_progress': in_progress.count()
        })
    
    @action(detail=False, methods=['post'])
    def reset_daily_queue(self, request):
        """Reset daily queue numbers"""
        branch_id = request.data.get('branch_id')
        if not branch_id:
            return Response({'error': 'branch_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not IsManager().has_permission(request, self):
            return Response({'error': 'Only managers can reset queue'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            # Archive today's completed queues
            today = timezone.now().date()
            Queue.objects.filter(
                branch_id=branch_id,
                status='COMPLETED',
                created_at__date=today
            ).update(status='ARCHIVED')
            
            return Response({'message': 'Daily queue reset completed'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class VisitVitalSignViewSet(viewsets.ModelViewSet):
    """ViewSet for VisitVitalSign model"""
    
    queryset = VisitVitalSign.objects.select_related(
        'visit', 'recorded_by'
    ).all()
    
    serializer_class = VisitVitalSignSerializer
    pagination_class = StandardPagination
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve']:
            permission_classes = [IsAuthenticated & (IsStaff | HasBranchAccess)]
        else:
            permission_classes = [IsAuthenticated & (IsDoctor | IsManager)]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter queryset based on visit access"""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Filter by visit access
        visit_id = self.request.query_params.get('visit')
        if visit_id:
            queryset = queryset.filter(visit_id=visit_id)
        
        # Doctors can only see vitals for their visits
        if user.role == UserRoles.DOCTOR:
            try:
                doctor = user.doctor_profile
                queryset = queryset.filter(visit__doctor=doctor)
            except:
                return queryset.none()
        
        return queryset
    
    def perform_create(self, serializer):
        """Create vital sign with recorded_by"""
        serializer.save(recorded_by=self.request.user)


class VisitDocumentViewSet(viewsets.ModelViewSet):
    """ViewSet for VisitDocument model"""
    
    queryset = VisitDocument.objects.select_related(
        'visit', 'uploaded_by'
    ).all()
    
    serializer_class = VisitDocumentSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['visit', 'document_type']
    search_fields = ['title', 'description']
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve', 'download']:
            permission_classes = [IsAuthenticated & (IsStaff | HasBranchAccess)]
        else:
            permission_classes = [IsAuthenticated & (IsDoctor | IsManager)]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter queryset based on visit access"""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Filter by visit access
        visit_id = self.request.query_params.get('visit')
        if visit_id:
            queryset = queryset.filter(visit_id=visit_id)
        
        # Doctors can only see documents for their visits
        if user.role == UserRoles.DOCTOR:
            try:
                doctor = user.doctor_profile
                queryset = queryset.filter(visit__doctor=doctor)
            except:
                return queryset.none()
        
        return queryset
    
    def perform_create(self, serializer):
        """Create document with uploaded_by"""
        serializer.save(uploaded_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download document file"""
        document = self.get_object()
        
        if not document.file:
            return Response({'error': 'No file attached'}, status=status.HTTP_404_NOT_FOUND)
        
        response = HttpResponse(document.file, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{document.title}.{document.file.name.split(".")[-1]}"'
        return response


# ===========================================
# CUSTOM VIEWS
# ===========================================
class DashboardView(APIView):
    """Dashboard view for visits"""
    
    permission_classes = [IsAuthenticated & IsStaff]
    
    def get(self, request):
        """Get dashboard data"""
        user = request.user
        branch_id = request.query_params.get('branch_id')
        
        # Get accessible branches for user
        if hasattr(user, 'user_branches'):
            accessible_branches = user.user_branches.filter(
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
        
        # Today's statistics
        today_visits = Visit.objects.filter(
            scheduled_date=today,
            **branch_filter
        )
        
        today_stats = {
            'total': today_visits.count(),
            'registered': today_visits.filter(status=VisitStatus.REGISTERED).count(),
            'in_consultation': today_visits.filter(status=VisitStatus.IN_CONSULTATION).count(),
            'ready_for_billing': today_visits.filter(status=VisitStatus.READY_FOR_BILLING).count(),
            'completed': today_visits.filter(status=VisitStatus.COMPLETED).count(),
            'cancelled': today_visits.filter(status=VisitStatus.CANCELLED).count(),
            'walk_ins': today_visits.filter(appointment_source='WALK_IN').count(),
            'appointments': today_visits.exclude(appointment_source='WALK_IN').count(),
        }
        
        # Upcoming appointments (next 7 days)
        upcoming_appointments = Appointment.objects.filter(
            appointment_date__range=[today, today + timedelta(days=7)],
            status__in=['SCHEDULED', 'CONFIRMED'],
            **branch_filter
        ).order_by('appointment_date', 'start_time')[:10]
        
        # Active visits
        active_visits = Visit.objects.filter(
            status__in=[VisitStatus.REGISTERED, VisitStatus.IN_CONSULTATION],
            **branch_filter
        ).order_by('scheduled_date', 'scheduled_time')[:10]
        
        # Queue status
        queue_status = Queue.objects.filter(
            status__in=['WAITING', 'IN_PROGRESS'],
            **branch_filter
        ).order_by('queue_number')[:20]
        
        # Recent visits (last 10)
        recent_visits = Visit.objects.filter(
            **branch_filter
        ).order_by('-created_at')[:10]
        
        data = {
            'today_stats': today_stats,
            'upcoming_appointments': AppointmentSerializer(upcoming_appointments, many=True).data,
            'active_visits': VisitSerializer(active_visits, many=True).data,
            'queue_status': QueueSerializer(queue_status, many=True).data,
            'recent_visits': VisitSerializer(recent_visits, many=True).data,
        }
        
        serializer = VisitDashboardSerializer(data)
        return Response(serializer.data)


class DoctorScheduleView(APIView):
    """Doctor's schedule view"""
    
    permission_classes = [IsAuthenticated & (IsStaff | HasBranchAccess)]
    
    def get(self, request):
        """Get doctor's schedule for a date"""
        doctor_id = request.query_params.get('doctor_id')
        branch_id = request.query_params.get('branch_id')
        date_str = request.query_params.get('date', timezone.now().date().isoformat())
        
        if not doctor_id:
            return Response({'error': 'doctor_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            doctor = Doctor.objects.get(id=doctor_id)
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Get doctor's available slots
            slots = doctor.get_available_slots(date, branch_id)
            
            # Get appointments for that day
            appointments = Appointment.objects.filter(
                doctor=doctor,
                appointment_date=date,
                status__in=['SCHEDULED', 'CONFIRMED']
            ).order_by('start_time')
            
            # Get visits for that day
            visits = Visit.objects.filter(
                doctor=doctor,
                scheduled_date=date,
                status__in=[VisitStatus.REGISTERED, VisitStatus.IN_CONSULTATION]
            ).order_by('scheduled_time')
            
            data = {
                'doctor': {
                    'id': doctor.id,
                    'name': doctor.user.get_full_name(),
                    'specialization': doctor.specialization.name if doctor.specialization else None,
                },
                'date': date,
                'slots': slots,
                'appointments': AppointmentSerializer(appointments, many=True).data,
                'visits': VisitSerializer(visits, many=True).data,
            }
            
            serializer = DoctorScheduleSerializer(data)
            return Response(serializer.data)
            
        except Doctor.DoesNotExist:
            return Response({'error': 'Doctor not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PublicAppointmentView(APIView):
    """Public API for appointment booking (for patients)"""
    
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Create appointment (public access)"""
        # Validate request data
        required_fields = ['patient_id', 'doctor_id', 'branch_id', 'appointment_date', 'start_time']
        for field in required_fields:
            if field not in request.data:
                return Response(
                    {'error': f'{field} is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        try:
            # Verify patient exists
            patient = Patient.objects.get(id=request.data['patient_id'])
            
            # Check if patient is active
            if not patient.user.is_active:
                return Response(
                    {'error': 'Patient account is not active'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create appointment
            appointment_data = {
                'patient': patient.id,
                'doctor': request.data['doctor_id'],
                'branch': request.data['branch_id'],
                'appointment_date': request.data['appointment_date'],
                'start_time': request.data['start_time'],
                'purpose': request.data.get('purpose', ''),
                'visit_type': request.data.get('visit_type', 'CONSULTATION'),
                'status': 'SCHEDULED',
            }
            
            serializer = AppointmentSerializer(data=appointment_data, context={'request': request})
            if serializer.is_valid():
                appointment = serializer.save()
                
                # Send confirmation
                NotificationService.send_appointment_reminder(appointment)
                
                return Response({
                    'message': 'Appointment scheduled successfully',
                    'appointment_id': appointment.appointment_id,
                    'confirmation_number': appointment.appointment_id,
                    'date': appointment.appointment_date,
                    'time': appointment.start_time,
                }, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Patient.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def get(self, request):
        """Get available slots for doctors (public access)"""
        branch_id = request.query_params.get('branch_id')
        date = request.query_params.get('date', timezone.now().date().isoformat())
        
        if not branch_id:
            return Response({'error': 'branch_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d').date() if isinstance(date, str) else date
            
            # Get doctors available at the branch on that date
            doctors = Doctor.objects.filter(
                doctor_branches__branch_id=branch_id,
                doctor_branches__is_active=True,
                is_active=True
            ).select_related('user', 'specialization')
            
            available_slots = []
            for doctor in doctors:
                slots = doctor.get_available_slots(date_obj, branch_id)
                
                # Get existing appointments
                existing_appointments = Appointment.objects.filter(
                    doctor=doctor,
                    appointment_date=date_obj,
                    status__in=['SCHEDULED', 'CONFIRMED']
                )
                
                # Filter available slots
                doctor_slots = []
                for slot in slots:
                    slot_start = datetime.combine(date_obj, slot['start_time'])
                    slot_end = datetime.combine(date_obj, slot['end_time'])
                    
                    is_available = True
                    for appointment in existing_appointments:
                        appt_start = datetime.combine(date_obj, appointment.start_time)
                        appt_end = datetime.combine(date_obj, appointment.end_time)
                        
                        if not (slot_end <= appt_start or slot_start >= appt_end):
                            is_available = False
                            break
                    
                    if is_available:
                        doctor_slots.append({
                            'start_time': slot['start_time'].strftime('%H:%M'),
                            'end_time': slot['end_time'].strftime('%H:%M'),
                            'duration': slot['duration']
                        })
                
                if doctor_slots:
                    available_slots.append({
                        'doctor_id': doctor.id,
                        'doctor_name': doctor.user.get_full_name(),
                        'specialization': doctor.specialization.name if doctor.specialization else 'General',
                        'slots': doctor_slots
                    })
            
            return Response({
                'date': date_obj,
                'branch_id': branch_id,
                'available_doctors': available_slots
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)