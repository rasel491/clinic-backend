# apps/doctors/serializers.py

# Base Serializers
from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta
import re

from core.constants import UserRoles
from .models import Doctor, DoctorSchedule, DoctorLeave


class DoctorMinimalSerializer(serializers.ModelSerializer):
    """Minimal doctor serializer for dropdowns and basic info"""
    
    full_name = serializers.SerializerMethodField()
    specialization_display = serializers.CharField(source='get_specialization_display', read_only=True)
    
    class Meta:
        model = Doctor
        fields = [
            'id', 'doctor_id', 'full_name', 'specialization', 
            'specialization_display', 'primary_branch', 'is_active',
            'consultation_fee', 'years_of_experience'
        ]
        read_only_fields = ['doctor_id', 'full_name']
    
    def get_full_name(self, obj):
        return obj.full_name


class DoctorListSerializer(DoctorMinimalSerializer):
    """Doctor list serializer for listing doctors"""
    
    primary_branch_name = serializers.CharField(source='primary_branch.name', read_only=True)
    secondary_branches_count = serializers.SerializerMethodField()
    license_status = serializers.SerializerMethodField()
    
    class Meta(DoctorMinimalSerializer.Meta):
        fields = DoctorMinimalSerializer.Meta.fields + [
            'license_number', 'license_expiry', 'license_status',
            'is_accepting_new_patients', 'primary_branch_name',
            'secondary_branches_count', 'created_at'
        ]
    
    def get_secondary_branches_count(self, obj):
        return obj.secondary_branches.count()
    
    def get_license_status(self, obj):
        if obj.is_license_valid:
            days_left = (obj.license_expiry - timezone.now().date()).days
            if days_left > 30:
                return 'VALID'
            elif days_left > 0:
                return f'EXPIRING ({days_left} days)'
            else:
                return 'EXPIRED'
        return 'EXPIRED'


class DoctorDetailSerializer(serializers.ModelSerializer):
    """Complete doctor detail serializer"""
    
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    phone = serializers.CharField(source='user.phone', read_only=True)
    full_name = serializers.SerializerMethodField()
    specialization_display = serializers.CharField(source='get_specialization_display', read_only=True)
    preferred_contact_method_display = serializers.CharField(source='get_preferred_contact_method_display', read_only=True)
    
    primary_branch_name = serializers.CharField(source='primary_branch.name', read_only=True)
    primary_branch_address = serializers.CharField(source='primary_branch.address', read_only=True)
    
    secondary_branches_info = serializers.SerializerMethodField()
    all_branches_info = serializers.SerializerMethodField()
    
    license_status = serializers.SerializerMethodField()
    license_days_left = serializers.SerializerMethodField()
    
    # Statistics (to be populated in view)
    total_appointments = serializers.IntegerField(read_only=True, default=0)
    upcoming_appointments = serializers.IntegerField(read_only=True, default=0)
    total_patients = serializers.IntegerField(read_only=True, default=0)
    
    class Meta:
        model = Doctor
        fields = [
            # Basic Info
            'id', 'doctor_id', 'user_id', 'email', 'phone', 'full_name',
            'title', 'specialization', 'specialization_display',
            
            # Professional Details
            'qualification', 'education', 'certifications', 
            'years_of_experience', 'bio', 'awards',
            'languages_spoken',
            
            # License & Registration
            'license_number', 'license_expiry', 'license_issuing_authority',
            'registration_number', 'npi_number',
            'license_status', 'license_days_left',
            
            # Branch Info
            'primary_branch', 'primary_branch_name', 'primary_branch_address',
            'secondary_branches', 'secondary_branches_info', 'all_branches_info',
            
            # Availability & Fees
            'is_active', 'is_accepting_new_patients',
            'consultation_fee', 'follow_up_fee',
            'preferred_contact_method', 'preferred_contact_method_display',
            
            # Contact Info
            'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relation',
            
            # Signature
            'signature_image', 'signature_image_url',
            
            # Statistics
            'total_appointments', 'upcoming_appointments', 'total_patients',
            
            # Audit
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'doctor_id', 'license_status', 'license_days_left',
            'primary_branch_name', 'primary_branch_address',
            'secondary_branches_info', 'all_branches_info',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def get_full_name(self, obj):
        return obj.full_name
    
    def get_secondary_branches_info(self, obj):
        """Get info about secondary branches"""
        return [
            {
                'id': branch.id,
                'name': branch.name,
                'code': branch.code
            }
            for branch in obj.secondary_branches.all()
        ]
    
    def get_all_branches_info(self, obj):
        """Get info about all branches where doctor works"""
        branches = []
        
        # Primary branch
        if obj.primary_branch:
            branches.append({
                'id': obj.primary_branch.id,
                'name': obj.primary_branch.name,
                'code': obj.primary_branch.code,
                'is_primary': True
            })
        
        # Secondary branches
        for branch in obj.secondary_branches.all():
            branches.append({
                'id': branch.id,
                'name': branch.name,
                'code': branch.code,
                'is_primary': False
            })
        
        return branches
    
    def get_license_status(self, obj):
        return 'VALID' if obj.is_license_valid else 'EXPIRED'
    
    def get_license_days_left(self, obj):
        if obj.license_expiry:
            delta = obj.license_expiry - timezone.now().date()
            return delta.days
        return None
    
    def validate_license_number(self, value):
        """Validate license number format"""
        if not value:
            raise serializers.ValidationError("License number is required")
        
        # Basic format validation (alphanumeric with optional dashes)
        if not re.match(r'^[A-Za-z0-9\-]+$', value):
            raise serializers.ValidationError(
                "License number can only contain letters, numbers, and hyphens"
            )
        
        # Check uniqueness
        if Doctor.objects.filter(license_number=value).exists():
            instance = self.instance
            if not instance or instance.license_number != value:
                raise serializers.ValidationError("License number already exists")
        
        return value
    
    def validate_license_expiry(self, value):
        """Validate license expiry date"""
        if value < timezone.now().date():
            raise serializers.ValidationError("License expiry date cannot be in the past")
        
        # Warn if expiring soon (but still allow)
        days_left = (value - timezone.now().date()).days
        if days_left < 30:
            self.context['warnings'] = self.context.get('warnings', [])
            self.context['warnings'].append(
                f"License is expiring in {days_left} days"
            )
        
        return value
    
    def validate_years_of_experience(self, value):
        """Validate years of experience"""
        if value > 100:
            raise serializers.ValidationError("Years of experience cannot exceed 100")
        return value
    
    def validate_consultation_fee(self, value):
        """Validate consultation fee"""
        if value < 0:
            raise serializers.ValidationError("Consultation fee cannot be negative")
        return value
    
    def validate(self, attrs):
        """Additional validation"""
        user = self.context['request'].user
        
        # Check if user has doctor role when creating
        if self.instance is None:  # Creating new doctor
            user_obj = attrs.get('user')
            if user_obj and user_obj.role != UserRoles.DOCTOR:
                raise serializers.ValidationError({
                    'user': 'Selected user must have DOCTOR role'
                })
        
        # Ensure primary branch is not in secondary branches
        secondary_branches = attrs.get('secondary_branches', [])
        primary_branch = attrs.get('primary_branch')
        
        if primary_branch and primary_branch in secondary_branches:
            raise serializers.ValidationError({
                'secondary_branches': 'Primary branch cannot be in secondary branches list'
            })
        
        return attrs
    
    def create(self, validated_data):
        """Create doctor with transaction"""
        secondary_branches = validated_data.pop('secondary_branches', [])
        
        with transaction.atomic():
            doctor = Doctor.objects.create(**validated_data)
            doctor.secondary_branches.set(secondary_branches)
        
        return doctor
    
    def update(self, instance, validated_data):
        """Update doctor with transaction"""
        secondary_branches = validated_data.pop('secondary_branches', None)
        
        with transaction.atomic():
            doctor = super().update(instance, validated_data)
            
            if secondary_branches is not None:
                doctor.secondary_branches.set(secondary_branches)
        
        return doctor


class DoctorCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating doctors (simplified)"""
    
    email = serializers.EmailField(write_only=True)
    phone = serializers.CharField(write_only=True, max_length=20)
    first_name = serializers.CharField(write_only=True, max_length=50)
    last_name = serializers.CharField(write_only=True, max_length=50)
    password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
    
    class Meta:
        model = Doctor
        fields = [
            'email', 'phone', 'first_name', 'last_name', 'password',
            'specialization', 'qualification', 'license_number', 'license_expiry',
            'primary_branch', 'consultation_fee', 'years_of_experience', 'bio'
        ]
    
    def validate_email(self, value):
        """Check if user with email already exists"""
        from accounts.models import User
        
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists")
        return value
    
    def create(self, validated_data):
        """Create user and doctor profile"""
        from accounts.models import User
        
        # Extract user data
        user_data = {
            'email': validated_data.pop('email'),
            'phone': validated_data.pop('phone'),
            'first_name': validated_data.pop('first_name'),
            'last_name': validated_data.pop('last_name'),
            'password': validated_data.pop('password'),
            'role': UserRoles.DOCTOR
        }
        
        with transaction.atomic():
            # Create user
            user = User.objects.create_user(**user_data)
            
            # Create doctor profile
            doctor = Doctor.objects.create(user=user, **validated_data)
            
            # Generate doctor_id
            doctor.save()  # This will trigger doctor_id generation
        
        return doctor
    

# Schedule Serializers
# apps/doctors/serializers.py (continued)

class DoctorScheduleSerializer(serializers.ModelSerializer):
    """Serializer for doctor schedules"""
    
    doctor_info = DoctorMinimalSerializer(source='doctor', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    day_of_week_display = serializers.CharField(source='get_day_of_week_display', read_only=True)
    
    # Calculated fields
    working_hours = serializers.FloatField(read_only=True)
    total_slots = serializers.IntegerField(read_only=True)
    available_slots = serializers.SerializerMethodField()
    
    class Meta:
        model = DoctorSchedule
        fields = [
            'id', 'doctor', 'doctor_info', 'branch', 'branch_name',
            'day_of_week', 'day_of_week_display',
            'start_time', 'end_time', 'break_start', 'break_end',
            'slot_duration', 'max_patients_per_slot',
            'room_number', 'chair_number', 'is_active',
            'working_hours', 'total_slots', 'available_slots',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'working_hours', 'total_slots', 'available_slots',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def get_available_slots(self, obj):
        """Get available slots for the next 7 days"""
        # This will be populated in the view
        return self.context.get('available_slots', [])
    
    def validate(self, attrs):
        """Validate schedule data"""
        doctor = attrs.get('doctor') or self.instance.doctor if self.instance else None
        branch = attrs.get('branch') or self.instance.branch if self.instance else None
        day_of_week = attrs.get('day_of_week') or self.instance.day_of_week if self.instance else None
        
        # Check if doctor works at this branch
        if doctor and branch:
            if branch not in doctor.all_branches:
                raise serializers.ValidationError({
                    'branch': f"Doctor does not work at {branch.name}"
                })
        
        # Check for duplicate schedule (same doctor, branch, day)
        if doctor and branch and day_of_week is not None:
            qs = DoctorSchedule.objects.filter(
                doctor=doctor,
                branch=branch,
                day_of_week=day_of_week
            )
            if self.instance:
                qs = qs.exclude(id=self.instance.id)
            
            if qs.exists():
                raise serializers.ValidationError({
                    'day_of_week': f"Schedule already exists for {doctor} on {DoctorSchedule(day_of_week=day_of_week).get_day_of_week_display()}"
                })
        
        # Validate time ranges
        start_time = attrs.get('start_time') or self.instance.start_time if self.instance else None
        end_time = attrs.get('end_time') or self.instance.end_time if self.instance else None
        break_start = attrs.get('break_start') or self.instance.break_start if self.instance else None
        break_end = attrs.get('break_end') or self.instance.break_end if self.instance else None
        
        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError({
                'end_time': 'End time must be after start time'
            })
        
        if break_start and break_end:
            if break_end <= break_start:
                raise serializers.ValidationError({
                    'break_end': 'Break end time must be after break start time'
                })
            
            if start_time and (break_start < start_time or break_end > end_time):
                raise serializers.ValidationError({
                    'break_start': 'Break time must be within working hours'
                })
        
        # Validate slot duration
        slot_duration = attrs.get('slot_duration') or self.instance.slot_duration if self.instance else None
        if slot_duration and slot_duration < 5:
            raise serializers.ValidationError({
                'slot_duration': 'Slot duration must be at least 5 minutes'
            })
        
        return attrs
    
    def to_representation(self, instance):
        """Add calculated fields to representation"""
        data = super().to_representation(instance)
        
        # Add time slots for the next 7 days
        if self.context.get('include_slots', False):
            data['time_slots'] = self._generate_time_slots(instance)
        
        return data
    
    def _generate_time_slots(self, schedule):
        """Generate available time slots for the next 7 days"""
        from datetime import datetime, timedelta
        
        slots = []
        today = timezone.now().date()
        
        for i in range(7):
            target_date = today + timedelta(days=i)
            
            # Check if this is the correct day of week
            if target_date.weekday() != schedule.day_of_week:
                continue
            
            # Generate slots for this day
            day_slots = self._generate_day_slots(schedule, target_date)
            if day_slots:
                slots.append({
                    'date': target_date,
                    'slots': day_slots
                })
        
        return slots
    
    def _generate_day_slots(self, schedule, date):
        """Generate slots for a specific day"""
        slots = []
        
        # Check for leaves on this day
        leaves = schedule.doctor.leaves.filter(
            start_date__lte=date,
            end_date__gte=date,
            status='APPROVED'
        )
        
        if leaves.exists():
            return slots  # No slots if doctor is on leave
        
        current_time = datetime.combine(date, schedule.start_time)
        end_time = datetime.combine(date, schedule.end_time)
        
        # Adjust for break time
        break_start = schedule.break_start
        break_end = schedule.break_end
        
        if break_start and break_end:
            break_start_dt = datetime.combine(date, break_start)
            break_end_dt = datetime.combine(date, break_end)
        
        while current_time + timedelta(minutes=schedule.slot_duration) <= end_time:
            slot_end = current_time + timedelta(minutes=schedule.slot_duration)
            
            # Skip if during break
            if break_start and break_end:
                if current_time < break_end_dt and slot_end > break_start_dt:
                    current_time = break_end_dt
                    continue
            
            slots.append({
                'start_time': current_time.time(),
                'end_time': slot_end.time(),
                'datetime': current_time,
                'available': True  # Would need to check appointments
            })
            
            current_time = slot_end
        
        return slots


class DoctorScheduleBulkSerializer(serializers.Serializer):
    """Serializer for bulk schedule creation/update"""
    
    schedules = DoctorScheduleSerializer(many=True)
    
    def create(self, validated_data):
        """Create multiple schedules"""
        schedules_data = validated_data['schedules']
        
        with transaction.atomic():
            schedules = []
            for schedule_data in schedules_data:
                schedule = DoctorSchedule.objects.create(**schedule_data)
                schedules.append(schedule)
            
            return {'schedules': schedules}
    
    def update(self, instance, validated_data):
        """Update multiple schedules"""
        # This would handle bulk updates
        pass
    
  # Leave Serializers
  # apps/doctors/serializers.py (continued)

class DoctorLeaveSerializer(serializers.ModelSerializer):
    """Serializer for doctor leaves"""
    
    doctor_info = DoctorMinimalSerializer(source='doctor', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.full_name', read_only=True)
    leave_type_display = serializers.CharField(source='get_leave_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    covering_doctor_info = DoctorMinimalSerializer(source='covering_doctor', read_only=True)
    
    # Calculated fields
    total_days = serializers.FloatField(read_only=True)
    is_current = serializers.SerializerMethodField()
    
    class Meta:
        model = DoctorLeave
        fields = [
            'id', 'doctor', 'doctor_info', 'leave_type', 'leave_type_display',
            'start_date', 'end_date', 'reason', 'is_full_day',
            'start_time', 'end_time', 'status', 'status_display',
            'approved_by', 'approved_by_name', 'approved_at',
            'rejection_reason', 'covering_doctor', 'covering_doctor_info',
            'total_days', 'is_current',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'total_days', 'is_current', 'approved_at',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def get_is_current(self, obj):
        """Check if leave is currently active"""
        today = timezone.now().date()
        return obj.start_date <= today <= obj.end_date
    
    def validate(self, attrs):
        """Validate leave data"""
        doctor = attrs.get('doctor') or self.instance.doctor if self.instance else None
        start_date = attrs.get('start_date') or self.instance.start_date if self.instance else None
        end_date = attrs.get('end_date') or self.instance.end_date if self.instance else None
        
        # Validate date range
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                'end_date': 'End date must be after start date'
            })
        
        # Check for overlapping leaves
        if doctor and start_date and end_date:
            qs = DoctorLeave.objects.filter(
                doctor=doctor,
                status='APPROVED'
            ).filter(
                start_date__lte=end_date,
                end_date__gte=start_date
            )
            
            if self.instance:
                qs = qs.exclude(id=self.instance.id)
            
            if qs.exists():
                raise serializers.ValidationError({
                    'start_date': 'Leave overlaps with existing approved leave'
                })
        
        # Validate covering doctor
        covering_doctor = attrs.get('covering_doctor')
        if covering_doctor and covering_doctor == doctor:
            raise serializers.ValidationError({
                'covering_doctor': 'Doctor cannot cover their own leave'
            })
        
        # Validate half-day timing
        is_full_day = attrs.get('is_full_day', True)
        if not is_full_day:
            start_time = attrs.get('start_time')
            end_time = attrs.get('end_time')
            
            if not start_time or not end_time:
                raise serializers.ValidationError({
                    'start_time': 'Start time and end time are required for half-day leaves'
                })
            
            if end_time <= start_time:
                raise serializers.ValidationError({
                    'end_time': 'End time must be after start time for half-day leaves'
                })
        
        return attrs
    
    def create(self, validated_data):
        """Create leave with default status based on user role"""
        request = self.context.get('request')
        
        if request and request.user.role == UserRoles.DOCTOR:
            # Doctors can only create leaves for themselves
            doctor = validated_data.get('doctor')
            if doctor and doctor.user != request.user:
                raise serializers.ValidationError({
                    'doctor': 'Doctors can only create leaves for themselves'
                })
        
        return super().create(validated_data)


class DoctorLeaveApprovalSerializer(serializers.Serializer):
    """Serializer for approving/rejecting leaves"""
    
    action = serializers.ChoiceField(choices=['approve', 'reject', 'cancel'])
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
    covering_doctor_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate(self, attrs):
        """Validate approval action"""
        action = attrs['action']
        reason = attrs.get('reason', '')
        covering_doctor_id = attrs.get('covering_doctor_id')
        
        if action == 'reject' and not reason:
            raise serializers.ValidationError({
                'reason': 'Reason is required when rejecting a leave'
            })
        
        if action == 'approve' and covering_doctor_id:
            # Validate covering doctor
            try:
                from .models import Doctor
                covering_doctor = Doctor.objects.get(id=covering_doctor_id)
                attrs['covering_doctor'] = covering_doctor
            except Doctor.DoesNotExist:
                raise serializers.ValidationError({
                    'covering_doctor_id': 'Invalid doctor ID'
                })
        
        return attrs


class DoctorAvailabilitySerializer(serializers.Serializer):
    """Serializer for checking doctor availability"""
    
    date = serializers.DateField()
    start_time = serializers.TimeField(required=False)
    end_time = serializers.TimeField(required=False)
    
    def validate(self, attrs):
        """Validate availability check"""
        date = attrs['date']
        
        if date < timezone.now().date():
            raise serializers.ValidationError({
                'date': 'Cannot check availability for past dates'
            })
        
        return attrs


class DoctorAvailabilityResponseSerializer(serializers.Serializer):
    """Serializer for doctor availability response"""
    
    is_available = serializers.BooleanField()
    reason = serializers.CharField(required=False)
    schedule = DoctorScheduleSerializer(required=False)
    available_slots = serializers.ListField(
        child=serializers.DictField(),
        required=False
    )

# Statistics Serializers
# apps/doctors/serializers.py (continued)

class DoctorStatisticsSerializer(serializers.Serializer):
    """Serializer for doctor statistics"""
    
    doctor_id = serializers.CharField()
    doctor_name = serializers.CharField()
    
    # Appointment statistics
    total_appointments = serializers.IntegerField(default=0)
    completed_appointments = serializers.IntegerField(default=0)
    upcoming_appointments = serializers.IntegerField(default=0)
    cancelled_appointments = serializers.IntegerField(default=0)
    
    # Patient statistics
    total_patients = serializers.IntegerField(default=0)
    new_patients_this_month = serializers.IntegerField(default=0)
    
    # Revenue statistics
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)
    revenue_this_month = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Schedule statistics
    working_days_per_week = serializers.IntegerField(default=0)
    average_patients_per_day = serializers.FloatField(default=0)
    
    # Leave statistics
    leaves_taken_this_year = serializers.IntegerField(default=0)
    upcoming_leaves = serializers.IntegerField(default=0)
    
    # Efficiency metrics
    average_consultation_duration = serializers.FloatField(default=0)
    patient_satisfaction_score = serializers.FloatField(default=0, max_value=5, min_value=0)


class DoctorAppointmentTrendSerializer(serializers.Serializer):
    """Serializer for appointment trends"""
    
    period = serializers.CharField()  # day, week, month
    data = serializers.ListField(
        child=serializers.DictField()
    )


class DoctorRevenueTrendSerializer(serializers.Serializer):
    """Serializer for revenue trends"""
    
    period = serializers.CharField()  # day, week, month, year
    data = serializers.ListField(
        child=serializers.DictField()
    )


# Export Serializers
class DoctorExportSerializer(serializers.ModelSerializer):
    """Serializer for doctor data export"""
    
    user_email = serializers.EmailField(source='user.email')
    user_phone = serializers.CharField(source='user.phone')
    full_name = serializers.SerializerMethodField()
    primary_branch_name = serializers.CharField(source='primary_branch.name')
    secondary_branches = serializers.SerializerMethodField()
    license_status = serializers.SerializerMethodField()
    
    class Meta:
        model = Doctor
        fields = [
            'doctor_id', 'full_name', 'user_email', 'user_phone',
            'title', 'specialization', 'qualification', 'education',
            'license_number', 'license_expiry', 'license_status',
            'registration_number', 'npi_number',
            'primary_branch_name', 'secondary_branches',
            'years_of_experience', 'consultation_fee', 'follow_up_fee',
            'is_active', 'is_accepting_new_patients',
            'created_at', 'updated_at'
        ]
    
    def get_full_name(self, obj):
        return obj.full_name
    
    def get_secondary_branches(self, obj):
        return ', '.join([branch.name for branch in obj.secondary_branches.all()])
    
    def get_license_status(self, obj):
        return 'Valid' if obj.is_license_valid else 'Expired'


# Nested serializers for other apps
class DoctorNestedSerializer(serializers.ModelSerializer):
    """Nested doctor serializer for use in other apps"""
    
    full_name = serializers.SerializerMethodField()
    specialization_display = serializers.CharField(source='get_specialization_display', read_only=True)
    
    class Meta:
        model = Doctor
        fields = [
            'id', 'doctor_id', 'full_name', 'specialization', 
            'specialization_display', 'consultation_fee'
        ]
        read_only_fields = fields
    
    def get_full_name(self, obj):
        return obj.full_name
    
