# apps/visits/serializers.py
from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from core.mixins.audit_fields import AuditFieldsMixin
from .models import (
    Visit, Appointment, Queue, VisitDocument, VisitVitalSign
)
from apps.patients.models import Patient
from apps.doctors.models import Doctor
from apps.clinics.models import Branch, Counter
from core.constants import VisitStatus, UserRoles
from core.permissions import IsDoctor, IsReceptionist, IsClinicManager

User = get_user_model()


class VisitVitalSignSerializer(serializers.ModelSerializer):
    """Serializer for vital signs"""
    
    recorded_by = serializers.StringRelatedField(read_only=True)
    bmi = serializers.ReadOnlyField()
    blood_pressure = serializers.ReadOnlyField()
    
    class Meta:
        model = VisitVitalSign
        fields = [
            'id', 'blood_pressure_systolic', 'blood_pressure_diastolic',
            'heart_rate', 'temperature', 'weight', 'height',
            'oxygen_saturation', 'respiratory_rate',
            'recorded_by', 'recorded_at', 'notes', 'bmi', 'blood_pressure'
        ]
        read_only_fields = ['recorded_by', 'recorded_at']
    
    def validate(self, data):
        """Validate vital signs data"""
        # Validate blood pressure
        if 'blood_pressure_systolic' in data and 'blood_pressure_diastolic' in data:
            systolic = data['blood_pressure_systolic']
            diastolic = data['blood_pressure_diastolic']
            
            if systolic and diastolic:
                if systolic <= diastolic:
                    raise serializers.ValidationError({
                        'blood_pressure': 'Systolic must be greater than diastolic'
                    })
                if systolic < 50 or systolic > 300:
                    raise serializers.ValidationError({
                        'blood_pressure_systolic': 'Systolic must be between 50 and 300'
                    })
                if diastolic < 30 or diastolic > 200:
                    raise serializers.ValidationError({
                        'blood_pressure_diastolic': 'Diastolic must be between 30 and 200'
                    })
        
        # Validate heart rate
        if 'heart_rate' in data and data['heart_rate']:
            if data['heart_rate'] < 30 or data['heart_rate'] > 250:
                raise serializers.ValidationError({
                    'heart_rate': 'Heart rate must be between 30 and 250 bpm'
                })
        
        # Validate temperature
        if 'temperature' in data and data['temperature']:
            if data['temperature'] < 30 or data['temperature'] > 45:
                raise serializers.ValidationError({
                    'temperature': 'Temperature must be between 30°C and 45°C'
                })
        
        # Validate oxygen saturation
        if 'oxygen_saturation' in data and data['oxygen_saturation']:
            if data['oxygen_saturation'] < 70 or data['oxygen_saturation'] > 100:
                raise serializers.ValidationError({
                    'oxygen_saturation': 'Oxygen saturation must be between 70% and 100%'
                })
        
        return data


class VisitDocumentSerializer(serializers.ModelSerializer):
    """Serializer for visit documents"""
    
    uploaded_by = serializers.StringRelatedField(read_only=True)
    document_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    
    class Meta:
        model = VisitDocument
        fields = [
            'id', 'visit', 'document_type', 'title', 'description',
            'file', 'thumbnail', 'uploaded_by', 'uploaded_at',
            'doctor_notes', 'document_url', 'thumbnail_url', 'file_size'
        ]
        read_only_fields = ['uploaded_by', 'uploaded_at']
    
    def get_document_url(self, obj):
        """Get absolute URL for document"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
        return None
    
    def get_thumbnail_url(self, obj):
        """Get absolute URL for thumbnail"""
        if obj.thumbnail:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
        return None
    
    def get_file_size(self, obj):
        """Get file size in human readable format"""
        if obj.file:
            size = obj.file.size
            for unit in ['bytes', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
        return None
    
    def validate_file(self, value):
        """Validate uploaded file"""
        # Check file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if value.size > max_size:
            raise serializers.ValidationError(
                f'File size must be less than 10MB. Current size: {value.size / (1024*1024):.1f}MB'
            )
        
        # Check file extensions
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.tiff', '.bmp', '.txt', '.doc', '.docx']
        if not any(value.name.lower().endswith(ext) for ext in allowed_extensions):
            raise serializers.ValidationError(
                f'File type not allowed. Allowed types: {", ".join(allowed_extensions)}'
            )
        
        return value


class MinimalPatientSerializer(serializers.ModelSerializer):
    """Minimal patient serializer for visit list views"""
    
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    phone = serializers.CharField(source='user.phone', read_only=True)
    age = serializers.ReadOnlyField()
    
    class Meta:
        model = Patient
        fields = ['id', 'patient_id', 'full_name', 'phone', 'age', 'gender']


class MinimalDoctorSerializer(serializers.ModelSerializer):
    """Minimal doctor serializer for visit list views"""
    
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    specialization = serializers.StringRelatedField()
    
    class Meta:
        model = Doctor
        fields = ['id', 'doctor_id', 'full_name', 'specialization', 'qualification']


class MinimalBranchSerializer(serializers.ModelSerializer):
    """Minimal branch serializer"""
    
    class Meta:
        model = Branch
        fields = ['id', 'name', 'code', 'address', 'phone']


class VisitSerializer(serializers.ModelSerializer):
    """Main serializer for Visit model"""
    
    patient = MinimalPatientSerializer(read_only=True)
    patient_id = serializers.PrimaryKeyRelatedField(
        queryset=Patient.objects.all(),
        write_only=True,
        source='patient'
    )
    
    doctor = MinimalDoctorSerializer(read_only=True)
    doctor_id = serializers.PrimaryKeyRelatedField(
        queryset=Doctor.objects.all(),
        write_only=True,
        source='doctor',
        required=False,
        allow_null=True
    )
    
    branch = MinimalBranchSerializer(read_only=True)
    branch_id = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
        write_only=True,
        source='branch'
    )
    
    # Related fields
    vital_signs = VisitVitalSignSerializer(many=True, read_only=True)
    documents = VisitDocumentSerializer(many=True, read_only=True)
    follow_ups = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    
    # Computed fields
    total_duration = serializers.DurationField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    can_checkout = serializers.BooleanField(read_only=True)
    current_status_info = serializers.CharField(read_only=True)
    has_invoice = serializers.BooleanField(read_only=True)
    
    # Counter
    assigned_counter = serializers.PrimaryKeyRelatedField(
        queryset=Counter.objects.all(),
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = Visit
        fields = [
            'id', 'visit_id', 'patient', 'patient_id', 'doctor', 'doctor_id',
            'branch', 'branch_id', 'status', 'appointment_source', 'visit_type',
            'priority', 'scheduled_date', 'scheduled_time', 'actual_checkin',
            'actual_checkout', 'wait_duration', 'consultation_duration',
            'chief_complaint', 'symptoms', 'dental_issues', 'blood_pressure',
            'heart_rate', 'temperature', 'weight', 'height', 'is_follow_up',
            'follow_up_of', 'next_follow_up_date', 'follow_up_instructions',
            'diagnosis', 'clinical_notes', 'recommendations', 'treatment_plan',
            'queue_number', 'estimated_wait_time', 'insurance_verified',
            'insurance_notes', 'referred_by', 'referral_reason',
            'assigned_counter', 'vital_signs', 'documents', 'follow_ups',
            'total_duration', 'is_active', 'can_checkout', 'current_status_info',
            'has_invoice', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'visit_id', 'status', 'queue_number', 'actual_checkin',
            'actual_checkout', 'wait_duration', 'consultation_duration',
            'created_at', 'updated_at'
        ]
    
    def validate(self, data):
        """Validate visit data"""
        request = self.context.get('request')
        
        # Check if user has access to the branch
        branch = data.get('branch')
        if branch and request and not request.user.can_access_branch(branch):
            raise serializers.ValidationError({
                'branch': 'You do not have access to this branch'
            })
        
        # Validate scheduled date is not in the past for new visits
        if self.instance is None:  # Creating new visit
            scheduled_date = data.get('scheduled_date')
            scheduled_time = data.get('scheduled_time')
            
            if scheduled_date and scheduled_time:
                scheduled_datetime = timezone.make_aware(
                    datetime.combine(scheduled_date, scheduled_time)
                )
                if scheduled_datetime < timezone.now():
                    raise serializers.ValidationError({
                        'scheduled_datetime': 'Cannot schedule visits in the past'
                    })
        
        # Validate doctor availability
        doctor = data.get('doctor')
        scheduled_date = data.get('scheduled_date')
        scheduled_time = data.get('scheduled_time')
        
        if doctor and scheduled_date and scheduled_time:
            # Check if doctor is available at that time
            if not doctor.is_available(scheduled_date, scheduled_time):
                raise serializers.ValidationError({
                    'doctor': 'Doctor is not available at the scheduled time'
                })
            
            # Check for overlapping visits for the same doctor
            overlapping_visits = Visit.objects.filter(
                doctor=doctor,
                scheduled_date=scheduled_date,
                scheduled_time=scheduled_time,
                status__in=[VisitStatus.REGISTERED, VisitStatus.IN_CONSULTATION]
            )
            
            if self.instance:
                overlapping_visits = overlapping_visits.exclude(id=self.instance.id)
            
            if overlapping_visits.exists():
                raise serializers.ValidationError({
                    'doctor': 'Doctor already has a visit scheduled at this time'
                })
        
        # Validate follow-up dates
        if data.get('is_follow_up') and data.get('next_follow_up_date'):
            next_date = data.get('next_follow_up_date')
            if next_date < timezone.now().date():
                raise serializers.ValidationError({
                    'next_follow_up_date': 'Follow-up date cannot be in the past'
                })
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """Create a new visit with queue management"""
        request = self.context.get('request')
        
        # Set created_by/updated_by if not set
        if request and request.user:
            if 'created_by' not in validated_data:
                validated_data['created_by'] = request.user
            if 'updated_by' not in validated_data:
                validated_data['updated_by'] = request.user
        
        # For walk-ins, generate queue number
        if validated_data.get('appointment_source') == 'WALK_IN':
            validated_data['queue_number'] = Visit._get_next_queue_number(validated_data['branch'])
        
        visit = super().create(validated_data)
        
        # Create queue entry for active visits
        if visit.status in [VisitStatus.REGISTERED, VisitStatus.IN_CONSULTATION]:
            Queue.objects.create(
                visit=visit,
                branch=visit.branch,
                doctor=visit.doctor,
                queue_number=visit.queue_number or 0,
                status='WAITING'
            )
        
        return visit
    
    def update(self, instance, validated_data):
        """Update visit with status transition checks"""
        request = self.context.get('request')
        
        # Handle status transitions
        new_status = validated_data.get('status')
        if new_status and new_status != instance.status:
            self._validate_status_transition(instance.status, new_status, request.user)
        
        # Update updated_by
        if request and request.user:
            validated_data['updated_by'] = request.user
        
        return super().update(instance, validated_data)
    
    def _validate_status_transition(self, old_status, new_status, user):
        """Validate if status transition is allowed"""
        allowed_transitions = {
            VisitStatus.REGISTERED: [VisitStatus.IN_CONSULTATION, VisitStatus.CANCELLED, VisitStatus.NO_SHOW],
            VisitStatus.IN_CONSULTATION: [VisitStatus.READY_FOR_BILLING, VisitStatus.TREATMENT_COMPLETED, VisitStatus.CANCELLED],
            VisitStatus.READY_FOR_BILLING: [VisitStatus.PAID, VisitStatus.CANCELLED],
            VisitStatus.TREATMENT_COMPLETED: [VisitStatus.PAID, VisitStatus.CANCELLED],
            VisitStatus.PAID: [VisitStatus.COMPLETED],
            VisitStatus.COMPLETED: [],
            VisitStatus.CANCELLED: [],
            VisitStatus.NO_SHOW: [],
        }
        
        if new_status not in allowed_transitions.get(old_status, []):
            raise serializers.ValidationError({
                'status': f'Cannot transition from {old_status} to {new_status}'
            })
        
        # Check permissions for specific transitions
        if new_status == VisitStatus.CANCELLED:
            if not (user.role in [UserRoles.RECEPTIONIST, UserRoles.CLINIC_MANAGER, UserRoles.SUPER_ADMIN]):
                raise serializers.ValidationError({
                    'status': 'Only receptionists and managers can cancel visits'
                })


class VisitStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating visit status"""
    
    status = serializers.ChoiceField(choices=VisitStatus.choices)
    notes = serializers.CharField(required=False, allow_blank=True)
    diagnosis = serializers.CharField(required=False, allow_blank=True)
    clinical_notes = serializers.CharField(required=False, allow_blank=True)
    recommendations = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        request = self.context.get('request')
        view = self.context.get('view')
        
        if not request or not view:
            return data
        
        # Get visit instance
        visit = view.get_object()
        
        # Check permissions based on status transition
        new_status = data.get('status')
        
        if new_status == VisitStatus.IN_CONSULTATION:
            if not IsDoctor().has_permission(request, view):
                raise serializers.ValidationError({
                    'status': 'Only doctors can start consultation'
                })
        
        elif new_status == VisitStatus.READY_FOR_BILLING:
            if not IsDoctor().has_permission(request, view):
                raise serializers.ValidationError({
                    'status': 'Only doctors can mark consultation complete'
                })
        
        elif new_status == VisitStatus.CANCELLED:
            if not (IsReceptionist().has_permission(request, view) or 
                    IsClinicManager().has_permission(request, view)):
                raise serializers.ValidationError({
                    'status': 'Only receptionists and managers can cancel visits'
                })
        
        return data


class AppointmentSerializer(serializers.ModelSerializer):
    """Serializer for Appointment model"""
    
    patient = MinimalPatientSerializer(read_only=True)
    patient_id = serializers.PrimaryKeyRelatedField(
        queryset=Patient.objects.all(),
        write_only=True,
        source='patient'
    )
    
    doctor = MinimalDoctorSerializer(read_only=True)
    doctor_id = serializers.PrimaryKeyRelatedField(
        queryset=Doctor.objects.all(),
        write_only=True,
        source='doctor'
    )
    
    branch = MinimalBranchSerializer(read_only=True)
    branch_id = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
        write_only=True,
        source='branch'
    )
    
    # Computed fields
    is_upcoming = serializers.BooleanField(read_only=True)
    is_today = serializers.BooleanField(read_only=True)
    is_past_due = serializers.BooleanField(read_only=True)
    
    # Visit link
    visit = VisitSerializer(read_only=True)
    
    class Meta:
        model = Appointment
        fields = [
            'id', 'appointment_id', 'patient', 'patient_id', 'doctor', 'doctor_id',
            'branch', 'branch_id', 'status', 'visit_type', 'appointment_date',
            'start_time', 'end_time', 'duration', 'purpose', 'notes',
            'expected_procedures', 'reminder_sent', 'reminder_sent_at',
            'cancelled_at', 'cancellation_reason', 'cancelled_by',
            'visit', 'is_recurring', 'recurrence_pattern', 'recurrence_end_date',
            'parent_appointment', 'is_waiting_list', 'preferred_times',
            'is_upcoming', 'is_today', 'is_past_due', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'appointment_id', 'reminder_sent', 'reminder_sent_at',
            'cancelled_at', 'cancelled_by', 'created_at', 'updated_at'
        ]
    
    def validate(self, data):
        """Validate appointment data"""
        # Validate appointment date is not in the past
        appointment_date = data.get('appointment_date')
        if appointment_date and appointment_date < timezone.now().date():
            raise serializers.ValidationError({
                'appointment_date': 'Cannot schedule appointments in the past'
            })
        
        # Validate time slots
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        duration = data.get('duration', 30)
        
        if start_time and end_time:
            start_dt = datetime.combine(appointment_date or timezone.now().date(), start_time)
            end_dt = datetime.combine(appointment_date or timezone.now().date(), end_time)
            
            if end_dt <= start_dt:
                raise serializers.ValidationError({
                    'end_time': 'End time must be after start time'
                })
            
            # Check if appointment exceeds maximum duration (4 hours)
            max_duration = timedelta(hours=4)
            actual_duration = end_dt - start_dt
            if actual_duration > max_duration:
                raise serializers.ValidationError({
                    'duration': f'Appointment cannot exceed {max_duration} hours'
                })
        
        # Validate doctor availability
        doctor = data.get('doctor')
        if doctor and appointment_date and start_time:
            # Check if doctor works at the branch on that day
            branch = data.get('branch')
            if branch and not doctor.branches.filter(id=branch.id).exists():
                raise serializers.ValidationError({
                    'doctor': f'Doctor {doctor} is not assigned to branch {branch}'
                })
            
            # Check doctor schedule
            if not doctor.is_available(appointment_date, start_time):
                raise serializers.ValidationError({
                    'doctor': 'Doctor is not available at the scheduled time'
                })
            
            # Check for overlapping appointments
            overlapping = Appointment.objects.filter(
                doctor=doctor,
                appointment_date=appointment_date,
                start_time__lt=end_time or (start_time + timedelta(minutes=duration)),
                end_time__gt=start_time,
                status__in=['SCHEDULED', 'CONFIRMED']
            )
            
            if self.instance:
                overlapping = overlapping.exclude(id=self.instance.id)
            
            if overlapping.exists():
                raise serializers.ValidationError({
                    'time_slot': 'Doctor already has an appointment scheduled at this time'
                })
        
        # Validate recurrence pattern
        recurrence_pattern = data.get('recurrence_pattern')
        recurrence_end_date = data.get('recurrence_end_date')
        
        if recurrence_pattern and not recurrence_end_date:
            raise serializers.ValidationError({
                'recurrence_end_date': 'Recurrence end date is required for recurring appointments'
            })
        
        if recurrence_end_date and recurrence_end_date <= appointment_date:
            raise serializers.ValidationError({
                'recurrence_end_date': 'Recurrence end date must be after appointment date'
            })
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """Create appointment with optional recurrence"""
        request = self.context.get('request')
        
        # Set cancelled_by if not set
        if request and request.user:
            if 'cancelled_by' not in validated_data:
                validated_data['cancelled_by'] = request.user
        
        appointment = super().create(validated_data)
        
        # Create recurring appointments if needed
        if appointment.is_recurring and appointment.recurrence_pattern:
            self._create_recurring_appointments(appointment)
        
        return appointment
    
    def _create_recurring_appointments(self, parent_appointment):
        """Create recurring appointments based on pattern"""
        pattern = parent_appointment.recurrence_pattern
        end_date = parent_appointment.recurrence_end_date
        
        next_date = parent_appointment.appointment_date
        while next_date <= end_date:
            # Skip the original appointment date
            if next_date == parent_appointment.appointment_date:
                if pattern == 'WEEKLY':
                    next_date += timedelta(days=7)
                elif pattern == 'BIWEEKLY':
                    next_date += timedelta(days=14)
                elif pattern == 'MONTHLY':
                    next_date = self._add_months(next_date, 1)
                continue
            
            # Create child appointment
            child_data = {
                'patient': parent_appointment.patient,
                'doctor': parent_appointment.doctor,
                'branch': parent_appointment.branch,
                'status': 'SCHEDULED',
                'visit_type': parent_appointment.visit_type,
                'appointment_date': next_date,
                'start_time': parent_appointment.start_time,
                'end_time': parent_appointment.end_time,
                'duration': parent_appointment.duration,
                'purpose': parent_appointment.purpose,
                'notes': parent_appointment.notes,
                'is_recurring': False,
                'parent_appointment': parent_appointment
            }
            
            Appointment.objects.create(**child_data)
            
            # Calculate next date
            if pattern == 'WEEKLY':
                next_date += timedelta(days=7)
            elif pattern == 'BIWEEKLY':
                next_date += timedelta(days=14)
            elif pattern == 'MONTHLY':
                next_date = self._add_months(next_date, 1)
    
    def _add_months(self, source_date, months):
        """Add months to a date, handling month overflow"""
        month = source_date.month - 1 + months
        year = source_date.year + month // 12
        month = month % 12 + 1
        day = min(source_date.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
        return source_date.replace(year=year, month=month, day=day)


class AppointmentStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating appointment status"""
    
    status = serializers.ChoiceField(choices=Appointment.STATUS_CHOICES)
    cancellation_reason = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        status = data.get('status')
        cancellation_reason = data.get('cancellation_reason')
        
        if status == 'CANCELLED' and not cancellation_reason:
            raise serializers.ValidationError({
                'cancellation_reason': 'Cancellation reason is required when cancelling an appointment'
            })
        
        return data


class QueueSerializer(serializers.ModelSerializer):
    """Serializer for Queue model"""
    
    visit = VisitSerializer(read_only=True)
    visit_id = serializers.PrimaryKeyRelatedField(
        queryset=Visit.objects.all(),
        write_only=True,
        source='visit'
    )
    
    branch = MinimalBranchSerializer(read_only=True)
    branch_id = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(),
        write_only=True,
        source='branch'
    )
    
    doctor = MinimalDoctorSerializer(read_only=True)
    doctor_id = serializers.PrimaryKeyRelatedField(
        queryset=Doctor.objects.all(),
        write_only=True,
        source='doctor',
        required=False,
        allow_null=True
    )
    
    patient_info = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    patient_phone = serializers.SerializerMethodField()
    wait_time = serializers.DurationField(read_only=True)
    
    class Meta:
        model = Queue
        fields = [
            'id', 'branch', 'branch_id', 'doctor', 'doctor_id', 'visit', 'visit_id',
            'queue_number', 'status', 'joined_at', 'called_at', 'started_at',
            'completed_at', 'counter', 'estimated_wait_minutes', 'notes',
            'patient_info', 'patient_name', 'patient_phone', 'wait_time',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'joined_at', 'called_at', 'started_at', 'completed_at',
            'created_at', 'updated_at', 'wait_time'
        ]
    
    def get_patient_info(self, obj):
        """Get patient information"""
        if obj.visit and obj.visit.patient:
            return {
                'id': obj.visit.patient.id,
                'patient_id': obj.visit.patient.patient_id,
                'full_name': obj.visit.patient.user.get_full_name(),
                'age': obj.visit.patient.age,
                'gender': obj.visit.patient.gender
            }
        return None
    
    def get_patient_name(self, obj):
        """Get patient name for display"""
        if obj.visit and obj.visit.patient:
            return obj.visit.patient.user.get_full_name()
        return None
    
    def get_patient_phone(self, obj):
        """Get patient phone"""
        if obj.visit and obj.visit.patient and obj.visit.patient.user:
            return obj.visit.patient.user.phone
        return None
    
    def validate(self, data):
        """Validate queue data"""
        visit = data.get('visit')
        branch = data.get('branch')
        
        if visit and branch and visit.branch != branch:
            raise serializers.ValidationError({
                'branch': 'Visit does not belong to the specified branch'
            })
        
        # Check for duplicate queue number in same branch
        queue_number = data.get('queue_number')
        if queue_number and branch:
            existing = Queue.objects.filter(
                branch=branch,
                queue_number=queue_number,
                status__in=['WAITING', 'IN_PROGRESS']
            )
            
            if self.instance:
                existing = existing.exclude(id=self.instance.id)
            
            if existing.exists():
                raise serializers.ValidationError({
                    'queue_number': f'Queue number {queue_number} is already in use at this branch'
                })
        
        return data


class QueueStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating queue status"""
    
    action = serializers.ChoiceField(choices=[
        ('call', 'Call Patient'),
        ('start', 'Start Consultation'),
        ('complete', 'Complete'),
        ('skip', 'Skip'),
        ('cancel', 'Cancel')
    ])
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        action = data.get('action')
        
        if action in ['skip', 'cancel'] and not data.get('notes'):
            raise serializers.ValidationError({
                'notes': 'Notes are required when skipping or cancelling a queue entry'
            })
        
        return data


class VisitDashboardSerializer(serializers.Serializer):
    """Serializer for visit dashboard data"""
    
    today_stats = serializers.DictField()
    upcoming_appointments = AppointmentSerializer(many=True)
    active_visits = VisitSerializer(many=True)
    queue_status = QueueSerializer(many=True)
    recent_visits = VisitSerializer(many=True)


class DoctorScheduleSerializer(serializers.Serializer):
    """Serializer for doctor's schedule view"""
    
    doctor = MinimalDoctorSerializer()
    date = serializers.DateField()
    slots = serializers.ListField(child=serializers.DictField())
    appointments = AppointmentSerializer(many=True)
    visits = VisitSerializer(many=True)