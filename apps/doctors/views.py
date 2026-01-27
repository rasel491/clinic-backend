# apps/doctors/views.py

from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters import rest_framework as filters
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from datetime import datetime, timedelta, date
import json
from core.constants import UserRoles

from core.permissions import (
    IsSuperAdmin, IsClinicManager, IsDoctor, 
    IsReceptionist, IsCashier
)
from .models import Doctor, DoctorSchedule, DoctorLeave
from .serializers import (
    DoctorListSerializer, DoctorDetailSerializer, DoctorCreateSerializer,
    DoctorScheduleSerializer, DoctorLeaveSerializer, DoctorMinimalSerializer,
    DoctorAvailabilitySerializer, DoctorAvailabilityResponseSerializer,
    DoctorStatisticsSerializer, DoctorExportSerializer,
    DoctorLeaveApprovalSerializer
)
from .filters import DoctorFilter, DoctorScheduleFilter, DoctorLeaveFilter
from .permissions import DoctorPermissions, DoctorSchedulePermissions, DoctorLeavePermissions


class DoctorViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Doctor CRUD operations
    """
    queryset = Doctor.objects.select_related(
        'user', 'primary_branch'
    ).prefetch_related(
        'secondary_branches'
    ).filter(deleted_at__isnull=True)  # Changed from is_deleted to deleted_at
    
    serializer_class = DoctorDetailSerializer
    permission_classes = [IsAuthenticated, DoctorPermissions]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = DoctorFilter
    
    def get_serializer_class(self):
        """Return appropriate serializer class based on action"""
        if self.action == 'list':
            return DoctorListSerializer
        elif self.action == 'create':
            return DoctorCreateSerializer
        elif self.action in ['export', 'export_csv', 'export_excel', 'export_json']:
            return DoctorExportSerializer
        return DoctorDetailSerializer
    
    def get_queryset(self):
        """Filter queryset based on user role and branch"""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Apply branch scope middleware filter
        # (Assuming branch scope is applied via middleware)
        
        # Doctors can only see themselves
        if user.role == UserRoles.DOCTOR:  # Use constant from core.constants
            queryset = queryset.filter(user=user)
        
        # Receptionists can see all active doctors
        elif user.role == UserRoles.RECEPTIONIST:
            queryset = queryset.filter(is_active=True)
        
        return queryset
    
    def perform_create(self, serializer):
        """Set created_by and updated_by on creation"""
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user
        )
    
    def perform_update(self, serializer):
        """Set updated_by on update"""
        serializer.save(updated_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def set_active(self, request, pk=None):
        """Activate a doctor"""
        doctor = self.get_object()
        doctor.is_active = True
        doctor.save(update_fields=['is_active', 'updated_by', 'updated_at'])
        return Response({'status': 'Doctor activated'})
    
    @action(detail=True, methods=['post'])
    def set_inactive(self, request, pk=None):
        """Deactivate a doctor"""
        doctor = self.get_object()
        doctor.is_active = False
        doctor.save(update_fields=['is_active', 'updated_by', 'updated_at'])
        return Response({'status': 'Doctor deactivated'})
    
    @action(detail=False, methods=['get'])
    def available(self, request):
        """Get available doctors for appointment booking"""
        date_str = request.query_params.get('date')
        branch_id = request.query_params.get('branch')
        
        if not date_str:
            return Response(
                {'error': 'Date parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.get_queryset().filter(
            is_active=True,
            is_accepting_new_patients=True,
            deleted_at__isnull=True  # Only non-deleted doctors
        )
        
        if branch_id:
            queryset = queryset.filter(
                Q(primary_branch_id=branch_id) |
                Q(secondary_branches__id=branch_id)
            ).distinct()
        
        # Filter doctors available on target date
        available_doctors = []
        for doctor in queryset:
            if self._is_doctor_available(doctor, target_date):
                available_doctors.append(doctor)
        
        serializer = DoctorMinimalSerializer(available_doctors, many=True)
        return Response(serializer.data)
    
    def _is_doctor_available(self, doctor, target_date):
        """Check if doctor is available on specific date"""
        # Check if doctor has schedule on this weekday
        weekday = target_date.weekday()
        has_schedule = doctor.schedules.filter(
            day_of_week=weekday,
            is_active=True
        ).exists()
        
        if not has_schedule:
            return False
        
        # Check if doctor is on leave
        is_on_leave = doctor.leaves.filter(
            start_date__lte=target_date,
            end_date__gte=target_date,
            status='APPROVED'
        ).exists()
        
        return not is_on_leave
    
    @action(detail=True, methods=['get'])
    def availability(self, request, pk=None):
        """Get doctor's availability for a date range"""
        serializer = DoctorAvailabilitySerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        doctor = self.get_object()
        target_date = serializer.validated_data['date']
        start_time = serializer.validated_data.get('start_time')
        end_time = serializer.validated_data.get('end_time')
        
        # Check availability
        is_available, reason, schedule, available_slots = self._check_availability(
            doctor, target_date, start_time, end_time
        )
        
        response_data = {
            'doctor_id': doctor.doctor_id,
            'doctor_name': doctor.full_name,
            'date': target_date,
            'is_available': is_available,
            'reason': reason,
            'available_slots': available_slots
        }
        
        if schedule:
            response_data['schedule'] = DoctorScheduleSerializer(schedule).data
        
        response_serializer = DoctorAvailabilityResponseSerializer(response_data)
        return Response(response_serializer.data)
    
    def _check_availability(self, doctor, target_date, start_time=None, end_time=None):
        """Check doctor's availability for specific date/time"""
        weekday = target_date.weekday()
        
        # Check schedule
        schedules = doctor.schedules.filter(
            day_of_week=weekday,
            is_active=True
        )
        
        if not schedules.exists():
            return False, 'No schedule for this day', None, []
        
        schedule = schedules.first()
        
        # Check leaves
        leaves = doctor.leaves.filter(
            start_date__lte=target_date,
            end_date__gte=target_date,
            status='APPROVED'
        )
        
        if leaves.exists():
            leave = leaves.first()
            if leave.is_full_day:
                return False, 'Doctor is on leave', schedule, []
            
            # Check half-day leave timing
            if start_time and end_time:
                if leave.start_time <= start_time <= leave.end_time or \
                   leave.start_time <= end_time <= leave.end_time:
                    return False, 'Doctor is on half-day leave during this time', schedule, []
        
        # Generate available slots
        available_slots = self._generate_available_slots(schedule, target_date)
        
        # If specific time requested, check if available
        if start_time and end_time:
            for slot in available_slots:
                if slot['start_time'] <= start_time and slot['end_time'] >= end_time:
                    return True, 'Available', schedule, available_slots
        
        return True, 'Available', schedule, available_slots
    
    def _generate_available_slots(self, schedule, target_date):
        """Generate available time slots for a doctor"""
        from datetime import datetime, timedelta
        
        slots = []
        
        # Check for appointments (would need visits app integration)
        # For now, return all slots as available
        current_time = datetime.combine(target_date, schedule.start_time)
        end_time = datetime.combine(target_date, schedule.end_time)
        
        # Adjust for break time
        if schedule.break_start and schedule.break_end:
            break_start = datetime.combine(target_date, schedule.break_start)
            break_end = datetime.combine(target_date, schedule.break_end)
        
        while current_time + timedelta(minutes=schedule.slot_duration) <= end_time:
            slot_end = current_time + timedelta(minutes=schedule.slot_duration)
            
            # Skip if during break
            if schedule.break_start and schedule.break_end:
                if current_time < break_end and slot_end > break_start:
                    current_time = break_end
                    continue
            
            slots.append({
                'start_time': current_time.time(),
                'end_time': slot_end.time(),
                'datetime': current_time,
                'available': True
            })
            
            current_time = slot_end
        
        return slots
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get doctor statistics"""
        doctor = self.get_object()
        
        # Calculate statistics
        stats = self._calculate_statistics(doctor)
        
        serializer = DoctorStatisticsSerializer(stats)
        return Response(serializer.data)
    
    def _calculate_statistics(self, doctor):
        """Calculate doctor statistics"""
        # These would be populated from other apps (visits, billing, etc.)
        # For now, return placeholder data
        
        return {
            'doctor_id': doctor.doctor_id,
            'doctor_name': doctor.full_name,
            'total_appointments': 0,  # From visits app
            'completed_appointments': 0,
            'upcoming_appointments': 0,
            'cancelled_appointments': 0,
            'total_patients': 0,  # From visits app
            'new_patients_this_month': 0,
            'total_revenue': 0,  # From billing app
            'revenue_this_month': 0,
            'working_days_per_week': doctor.schedules.filter(is_active=True).count(),
            'average_patients_per_day': 0,
            'leaves_taken_this_year': doctor.leaves.filter(
                status='APPROVED',
                start_date__year=timezone.now().year
            ).count(),
            'upcoming_leaves': doctor.leaves.filter(
                status='APPROVED',
                start_date__gt=timezone.now().date()
            ).count(),
            'average_consultation_duration': 0,
            'patient_satisfaction_score': 0
        }
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export doctors data"""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def specializations(self, request):
        """Get list of specializations with counts"""
        from .models import Doctor  # Import here to avoid circular import
        
        specializations = Doctor.objects.filter(
            is_active=True, deleted_at__isnull=True  # Use deleted_at instead of is_deleted
        ).values('specialization').annotate(
            count=Count('id')
        )
        
        # Add display names
        specialization_map = dict(Doctor.SPECIALIZATION_CHOICES)
        result = []
        for spec in specializations:
            result.append({
                'specialization': spec['specialization'],
                'display': specialization_map.get(spec['specialization'], spec['specialization']),
                'count': spec['count']
            })
        
        return Response(result)
    
    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Get dashboard statistics for doctors"""
        total_doctors = self.get_queryset().count()
        active_doctors = self.get_queryset().filter(is_active=True).count()
        doctors_accepting_new = self.get_queryset().filter(
            is_active=True, is_accepting_new_patients=True
        ).count()
        
        # Check license expiry
        thirty_days_later = timezone.now().date() + timedelta(days=30)
        expiring_soon = self.get_queryset().filter(
            license_expiry__lte=thirty_days_later,
            license_expiry__gte=timezone.now().date()
        ).count()
        
        expired_licenses = self.get_queryset().filter(
            license_expiry__lt=timezone.now().date()
        ).count()
        
        # Specialization distribution
        specialization_stats = self.get_queryset().values(
            'specialization'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
        
        return Response({
            'total_doctors': total_doctors,
            'active_doctors': active_doctors,
            'doctors_accepting_new_patients': doctors_accepting_new,
            'licenses_expiring_soon': expiring_soon,
            'expired_licenses': expired_licenses,
            'specialization_distribution': specialization_stats
        })


class DoctorScheduleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Doctor Schedule CRUD operations
    """
    queryset = DoctorSchedule.objects.select_related(
        'doctor', 'doctor__user', 'branch'
    ).filter(deleted_at__isnull=True)  # Changed from is_deleted to deleted_at
    
    serializer_class = DoctorScheduleSerializer
    permission_classes = [IsAuthenticated, DoctorSchedulePermissions]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = DoctorScheduleFilter
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Apply branch scope middleware filter
        
        # Doctors can only see their own schedules
        if user.role == UserRoles.DOCTOR:  # Use constant from core.constants
            queryset = queryset.filter(doctor__user=user)
        
        return queryset
    
    def perform_create(self, serializer):
        """Set created_by and updated_by on creation"""
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user
        )
    
    def perform_update(self, serializer):
        """Set updated_by on update"""
        serializer.save(updated_by=self.request.user)
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create multiple schedules at once"""
        schedules_data = request.data.get('schedules', [])
        
        if not schedules_data:
            return Response(
                {'error': 'No schedules provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        created_schedules = []
        errors = []
        
        for schedule_data in schedules_data:
            serializer = self.get_serializer(data=schedule_data)
            if serializer.is_valid():
                schedule = serializer.save(
                    created_by=request.user,
                    updated_by=request.user
                )
                created_schedules.append(schedule)
            else:
                errors.append({
                    'data': schedule_data,
                    'errors': serializer.errors
                })
        
        if errors:
            return Response({
                'created': len(created_schedules),
                'errors': errors,
                'schedules': DoctorScheduleSerializer(created_schedules, many=True).data
            }, status=status.HTTP_207_MULTI_STATUS)
        
        return Response(
            DoctorScheduleSerializer(created_schedules, many=True).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['get'])
    def slots(self, request, pk=None):
        """Get available slots for a schedule"""
        schedule = self.get_object()
        date_str = request.query_params.get('date')
        
        if not date_str:
            return Response(
                {'error': 'Date parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if doctor is on leave
        is_on_leave = schedule.doctor.leaves.filter(
            start_date__lte=target_date,
            end_date__gte=target_date,
            status='APPROVED'
        ).exists()
        
        if is_on_leave:
            return Response({
                'date': target_date,
                'available': False,
                'reason': 'Doctor is on leave',
                'slots': []
            })
        
        # Generate slots
        slots = self._generate_slots(schedule, target_date)
        
        return Response({
            'date': target_date,
            'available': len(slots) > 0,
            'slots': slots
        })
    
    def _generate_slots(self, schedule, target_date):
        """Generate time slots for a schedule"""
        from datetime import datetime, timedelta
        
        slots = []
        current_time = datetime.combine(target_date, schedule.start_time)
        end_time = datetime.combine(target_date, schedule.end_time)
        
        # Adjust for break time
        if schedule.break_start and schedule.break_end:
            break_start = datetime.combine(target_date, schedule.break_start)
            break_end = datetime.combine(target_date, schedule.break_end)
        
        while current_time + timedelta(minutes=schedule.slot_duration) <= end_time:
            slot_end = current_time + timedelta(minutes=schedule.slot_duration)
            
            # Skip if during break
            if schedule.break_start and schedule.break_end:
                if current_time < break_end and slot_end > break_start:
                    current_time = break_end
                    continue
            
            slot_data = {
                'start_time': current_time.time(),
                'end_time': slot_end.time(),
                'datetime': current_time.isoformat(),
                'available': True
            }
            
            # Check if slot is booked (would need visits app integration)
            # For now, mark all as available
            
            slots.append(slot_data)
            current_time = slot_end
        
        return slots


class DoctorLeaveViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Doctor Leave CRUD operations
    """
    queryset = DoctorLeave.objects.select_related(
        'doctor', 'doctor__user', 'approved_by', 'covering_doctor'
    ).filter(deleted_at__isnull=True)  # Changed from is_deleted to deleted_at
    
    serializer_class = DoctorLeaveSerializer
    permission_classes = [IsAuthenticated, DoctorLeavePermissions]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = DoctorLeaveFilter
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Apply branch scope middleware filter
        
        # Doctors can only see their own leaves
        if user.role == UserRoles.DOCTOR:  # Use constant from core.constants
            queryset = queryset.filter(doctor__user=user)
        
        return queryset
    
    def perform_create(self, serializer):
        """Set created_by and updated_by on creation"""
        user = self.request.user
        
        # If doctor is creating leave, set doctor to themselves
        if user.role == UserRoles.DOCTOR:
            try:
                doctor = user.doctor_profile
                serializer.save(
                    doctor=doctor,
                    created_by=user,
                    updated_by=user
                )
            except Doctor.DoesNotExist:
                return Response(
                    {'error': 'Doctor profile not found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            serializer.save(
                created_by=user,
                updated_by=user
            )
    
    def perform_update(self, serializer):
        """Set updated_by on update"""
        serializer.save(updated_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a leave request"""
        from core.constants import UserRoles
        
        leave = self.get_object()
        serializer = DoctorLeaveApprovalSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        action = serializer.validated_data['action']
        reason = serializer.validated_data.get('reason', '')
        covering_doctor = serializer.validated_data.get('covering_doctor')
        
        # Only clinic managers and super admins can approve/reject
        if request.user.role not in [UserRoles.SUPER_ADMIN, UserRoles.CLINIC_MANAGER]:
            return Response(
                {'error': 'Only clinic managers and super admins can approve leaves'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if action == 'approve':
            leave.status = 'APPROVED'
            leave.approved_by = request.user
            leave.approved_at = timezone.now()
            if covering_doctor:
                leave.covering_doctor = covering_doctor
            leave.save()
            
            return Response({'status': 'Leave approved'})
        
        elif action == 'reject':
            leave.status = 'REJECTED'
            leave.approved_by = request.user
            leave.approved_at = timezone.now()
            leave.rejection_reason = reason
            leave.save()
            
            return Response({'status': 'Leave rejected'})
        
        elif action == 'cancel':
            leave.status = 'CANCELLED'
            leave.save()
            
            return Response({'status': 'Leave cancelled'})
    
    @action(detail=False, methods=['get'])
    def calendar(self, request):
        """Get leaves for calendar view"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        doctor_id = request.query_params.get('doctor_id')
        
        queryset = self.get_queryset()
        
        if start_date and end_date:
            try:
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                queryset = queryset.filter(
                    start_date__lte=end,
                    end_date__gte=start
                )
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if doctor_id:
            queryset = queryset.filter(doctor_id=doctor_id)
        
        # Format for calendar
        calendar_data = []
        for leave in queryset:
            calendar_data.append({
                'id': leave.id,
                'title': f"{leave.doctor.full_name} - {leave.get_leave_type_display()}",
                'start': leave.start_date.isoformat(),
                'end': (leave.end_date + timedelta(days=1)).isoformat(),  # Calendar exclusive end
                'allDay': leave.is_full_day,
                'color': self._get_leave_color(leave),
                'extendedProps': {
                    'doctor': leave.doctor.full_name,
                    'leave_type': leave.leave_type,
                    'status': leave.status,
                    'reason': leave.reason
                }
            })
        
        return Response(calendar_data)
    
    def _get_leave_color(self, leave):
        """Get color for calendar event based on leave type and status"""
        color_map = {
            'VACATION': '#3b82f6',  # Blue
            'SICK': '#ef4444',      # Red
            'PERSONAL': '#8b5cf6',  # Purple
            'EMERGENCY': '#f59e0b', # Amber
            'TRAINING': '#10b981',  # Emerald
            'OTHER': '#6b7280',     # Gray
        }
        
        if leave.status == 'PENDING':
            return '#fbbf24'  # Yellow for pending
        elif leave.status == 'REJECTED':
            return '#dc2626'  # Dark red for rejected
        elif leave.status == 'CANCELLED':
            return '#9ca3af'  # Light gray for cancelled
        
        return color_map.get(leave.leave_type, '#6b7280')
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming approved leaves"""
        queryset = self.get_queryset().filter(
            status='APPROVED',
            start_date__gte=timezone.now().date()
        ).order_by('start_date')[:10]  # Next 10 upcoming leaves
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get leave summary by doctor"""
        doctor_id = request.query_params.get('doctor_id')
        
        if doctor_id:
            queryset = self.get_queryset().filter(doctor_id=doctor_id)
        else:
            queryset = self.get_queryset()
        
        # We need to calculate total_days for each leave first
        summary = []
        for leave in queryset:
            summary.append({
                'doctor_id': leave.doctor_id,
                'doctor_name': leave.doctor.full_name,
                'leave_type': leave.leave_type,
                'status': leave.status,
                'total_days': leave.total_days,
                'start_date': leave.start_date,
                'end_date': leave.end_date
            })
        
        return Response(summary)