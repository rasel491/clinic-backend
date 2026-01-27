# # Backend/apps/clinics/serializers.py

# from rest_framework import serializers
# from django.utils import timezone
# from django.db import transaction
# import logging

# from .models import Branch, Counter
# from apps.accounts.serializers import UserSerializer

# logger = logging.getLogger(__name__)


# class BranchSerializer(serializers.ModelSerializer):
#     """Main serializer for Branch model"""
    
#     # Read-only fields
#     is_eod_locked_display = serializers.SerializerMethodField()
#     eod_locked_by_details = UserSerializer(source='eod_locked_by', read_only=True)
    
#     # Computed fields
#     active_counters = serializers.SerializerMethodField()
#     total_staff = serializers.SerializerMethodField()
#     todays_appointments = serializers.SerializerMethodField()
    
#     class Meta:
#         model = Branch
#         fields = [
#             'id',
#             'name',
#             'code',
#             'address',
#             'phone',
#             'email',
#             'opening_time',
#             'closing_time',
#             'is_active',
#             'is_eod_locked',
#             'is_eod_locked_display',
#             'eod_locked_at',
#             'eod_locked_by',
#             'eod_locked_by_details',
#             'active_counters',
#             'total_staff',
#             'todays_appointments',
#             'created_at',
#             'updated_at',
#             'created_by',
#             'updated_by',
#         ]
#         read_only_fields = [
#             'id', 'created_at', 'updated_at', 'created_by', 'updated_by',
#             'is_eod_locked', 'eod_locked_at', 'eod_locked_by',
#             'active_counters', 'total_staff', 'todays_appointments',
#         ]
    
#     def get_is_eod_locked_display(self, obj):
#         """Get human-readable EOD status"""
#         if obj.is_eod_locked and obj.eod_locked_at:
#             return f"Locked at {obj.eod_locked_at.strftime('%Y-%m-%d %H:%M')}"
#         return "Open"
    
#     def get_active_counters(self, obj):
#         """Get count of active counters"""
#         return obj.counters.filter(is_active=True).count()
    
#     def get_total_staff(self, obj):
#         """Get count of active staff"""
#         try:
#             return obj.user_branches.filter(is_active=True).count()
#         except:
#             return 0
    
#     def get_todays_appointments(self, obj):
#         """Get today's appointment count"""
#         try:
#             from apps.visits.models import Appointment
#             today = timezone.now().date()
#             return Appointment.objects.filter(
#                 branch=obj,
#                 appointment_date=today,
#                 status__in=['scheduled', 'confirmed']
#             ).count()
#         except:
#             return 0
    
#     def validate(self, data):
#         """Validate branch data"""
#         # Ensure opening time is before closing time
#         opening_time = data.get('opening_time')
#         closing_time = data.get('closing_time')
        
#         if opening_time and closing_time:
#             if opening_time >= closing_time:
#                 raise serializers.ValidationError({
#                     'opening_time': 'Opening time must be before closing time',
#                     'closing_time': 'Closing time must be after opening time'
#                 })
        
#         return data
    
#     def create(self, validated_data):
#         """Create branch with validation"""
#         # Ensure unique code
#         code = validated_data.get('code')
#         if Branch.objects.filter(code=code, deleted_at__isnull=True).exists():
#             raise serializers.ValidationError({
#                 'code': 'Branch with this code already exists'
#             })
        
#         with transaction.atomic():
#             branch = super().create(validated_data)
#             logger.info(f"Branch created: {branch.code} by {self.context['request'].user}")
#             return branch
    
#     def update(self, instance, validated_data):
#         """Update branch with validation"""
#         # Prevent updating EOD locked fields
#         if instance.is_eod_locked:
#             # Check if trying to modify operational hours or active status
#             restricted_fields = ['opening_time', 'closing_time', 'is_active']
#             for field in restricted_fields:
#                 if field in validated_data:
#                     raise serializers.ValidationError({
#                         field: f'Cannot modify {field} when EOD is locked'
#                     })
        
#         with transaction.atomic():
#             branch = super().update(instance, validated_data)
#             logger.info(f"Branch updated: {branch.code} by {self.context['request'].user}")
#             return branch


# class BranchCreateSerializer(serializers.ModelSerializer):
#     """Serializer for creating new branches"""
    
#     class Meta:
#         model = Branch
#         fields = [
#             'name',
#             'code',
#             'address',
#             'phone',
#             'email',
#             'opening_time',
#             'closing_time',
#             'is_active',
#         ]
    
#     def validate_code(self, value):
#         """Validate branch code uniqueness"""
#         if Branch.objects.filter(code=value, deleted_at__isnull=True).exists():
#             raise serializers.ValidationError('Branch with this code already exists')
#         return value.upper()


# class BranchUpdateSerializer(serializers.ModelSerializer):
#     """Serializer for updating branches"""
    
#     class Meta:
#         model = Branch
#         fields = [
#             'name',
#             'address',
#             'phone',
#             'email',
#             'opening_time',
#             'closing_time',
#             'is_active',
#         ]
    
#     def validate(self, data):
#         """Validate update data"""
#         instance = self.instance
        
#         # Check EOD lock
#         if instance.is_eod_locked:
#             restricted_fields = ['opening_time', 'closing_time', 'is_active']
#             for field in restricted_fields:
#                 if field in data:
#                     raise serializers.ValidationError({
#                         field: f'Cannot modify {field} when EOD is locked'
#                     })
        
#         return data


# class BranchListSerializer(serializers.ModelSerializer):
#     """Lightweight serializer for branch lists"""
    
#     eod_status = serializers.SerializerMethodField()
#     active_counters = serializers.SerializerMethodField()
    
#     class Meta:
#         model = Branch
#         fields = [
#             'id',
#             'name',
#             'code',
#             'address',
#             'phone',
#             'is_active',
#             'is_eod_locked',
#             'eod_status',
#             'active_counters',
#         ]
    
#     def get_eod_status(self, obj):
#         """Get EOD status with timestamp"""
#         if obj.is_eod_locked and obj.eod_locked_at:
#             return {
#                 'locked': True,
#                 'locked_at': obj.eod_locked_at,
#                 'locked_by': obj.eod_locked_by.email if obj.eod_locked_by else None
#             }
#         return {'locked': False}
    
#     def get_active_counters(self, obj):
#         """Get count of active counters"""
#         return obj.counters.filter(is_active=True).count()


# class BranchEODSerializer(serializers.Serializer):
#     """Serializer for EOD operations"""
    
#     action = serializers.ChoiceField(choices=['lock', 'unlock'])
#     reason = serializers.CharField(required=False, allow_blank=True)
    
#     class Meta:
#         fields = ['action', 'reason']


# class BranchStatsSerializer(serializers.Serializer):
#     """Serializer for branch statistics"""
    
#     branch_id = serializers.UUIDField()
#     branch_name = serializers.CharField()
#     branch_code = serializers.CharField()
    
#     # Counts
#     total_patients = serializers.IntegerField()
#     total_appointments_today = serializers.IntegerField()
#     total_appointments_week = serializers.IntegerField()
#     active_staff = serializers.IntegerField()
#     active_counters = serializers.IntegerField()
    
#     # Financials
#     todays_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
#     weeks_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
#     pending_payments = serializers.DecimalField(max_digits=12, decimal_places=2)
    
#     # EOD Status
#     eod_locked = serializers.BooleanField()
#     eod_locked_at = serializers.DateTimeField(allow_null=True)
#     days_since_last_lock = serializers.IntegerField(allow_null=True)
    
#     # Occupancy
#     current_occupancy = serializers.FloatField(help_text="Current appointments vs capacity")
#     average_daily_appointments = serializers.FloatField()
    
#     class Meta:
#         fields = [
#             'branch_id', 'branch_name', 'branch_code',
#             'total_patients', 'total_appointments_today', 'total_appointments_week',
#             'active_staff', 'active_counters',
#             'todays_revenue', 'weeks_revenue', 'pending_payments',
#             'eod_locked', 'eod_locked_at', 'days_since_last_lock',
#             'current_occupancy', 'average_daily_appointments',
#         ]


# class CounterSerializer(serializers.ModelSerializer):
#     """Serializer for Counter model"""
    
#     branch_details = BranchSerializer(source='branch', read_only=True)
#     current_user = serializers.SerializerMethodField()
    
#     class Meta:
#         model = Counter
#         fields = [
#             'id',
#             'branch',
#             'branch_details',
#             'counter_number',
#             'name',
#             'device_id',
#             'is_active',
#             'current_user',
#             'created_at',
#             'updated_at',
#         ]
#         read_only_fields = ['id', 'created_at', 'updated_at']
    
#     def get_current_user(self, obj):
#         """Get current logged in user at this counter"""
#         try:
#             from apps.accounts.models import UserDevice
#             from django.utils import timezone
            
#             # Find active device sessions at this counter
#             recent_session = UserDevice.objects.filter(
#                 device_id=obj.device_id,
#                 last_seen_at__gte=timezone.now() - timezone.timedelta(minutes=30)
#             ).first()
            
#             if recent_session:
#                 return {
#                     'user_id': recent_session.user.id,
#                     'user_email': recent_session.user.email,
#                     'user_name': recent_session.user.full_name,
#                     'last_seen': recent_session.last_seen_at
#                 }
#         except:
#             pass
        
#         return None
    
#     def validate(self, data):
#         """Validate counter data"""
#         branch = data.get('branch') or self.instance.branch if self.instance else None
        
#         # Ensure unique counter number per branch
#         counter_number = data.get('counter_number')
#         if counter_number and branch:
#             queryset = Counter.objects.filter(
#                 branch=branch,
#                 counter_number=counter_number
#             )
            
#             if self.instance:
#                 queryset = queryset.exclude(id=self.instance.id)
            
#             if queryset.exists():
#                 raise serializers.ValidationError({
#                     'counter_number': f'Counter {counter_number} already exists in this branch'
#                 })
        
#         # Validate device_id uniqueness
#         device_id = data.get('device_id')
#         if device_id:
#             queryset = Counter.objects.filter(device_id=device_id)
#             if self.instance:
#                 queryset = queryset.exclude(id=self.instance.id)
            
#             if queryset.exists():
#                 raise serializers.ValidationError({
#                     'device_id': 'This device is already registered to another counter'
#                 })
        
#         return data


# class CounterCreateSerializer(serializers.ModelSerializer):
#     """Serializer for creating counters"""
    
#     class Meta:
#         model = Counter
#         fields = [
#             'branch',
#             'counter_number',
#             'name',
#             'device_id',
#             'is_active',
#         ]
    
#     def validate_counter_number(self, value):
#         """Validate counter number"""
#         if value < 1:
#             raise serializers.ValidationError('Counter number must be positive')
#         return value


# class CounterListSerializer(serializers.ModelSerializer):
#     """Lightweight serializer for counter lists"""
    
#     branch_name = serializers.CharField(source='branch.name', read_only=True)
#     branch_code = serializers.CharField(source='branch.code', read_only=True)
    
#     class Meta:
#         model = Counter
#         fields = [
#             'id',
#             'counter_number',
#             'name',
#             'device_id',
#             'is_active',
#             'branch_name',
#             'branch_code',
#         ]


# class CounterAssignmentSerializer(serializers.Serializer):
#     """Serializer for assigning device to counter"""
    
#     device_id = serializers.CharField(required=True)
#     force = serializers.BooleanField(default=False, help_text="Force assignment even if device is in use")
    
#     class Meta:
#         fields = ['device_id', 'force']


# class BranchOperationalHoursSerializer(serializers.Serializer):
#     """Serializer for branch operational hours"""
    
#     day = serializers.ChoiceField(choices=[
#         ('monday', 'Monday'),
#         ('tuesday', 'Tuesday'),
#         ('wednesday', 'Wednesday'),
#         ('thursday', 'Thursday'),
#         ('friday', 'Friday'),
#         ('saturday', 'Saturday'),
#         ('sunday', 'Sunday'),
#     ])
    
#     is_open = serializers.BooleanField(default=True)
#     opening_time = serializers.TimeField(required=False)
#     closing_time = serializers.TimeField(required=False)
#     break_start = serializers.TimeField(required=False)
#     break_end = serializers.TimeField(required=False)
    
#     class Meta:
#         fields = ['day', 'is_open', 'opening_time', 'closing_time', 'break_start', 'break_end']


# class BranchConfigurationSerializer(serializers.Serializer):
#     """Serializer for branch configuration"""
    
#     # General
#     allow_online_appointments = serializers.BooleanField(default=True)
#     max_daily_appointments = serializers.IntegerField(default=50, min_value=1)
#     appointment_duration = serializers.IntegerField(default=30, min_value=10, help_text="Minutes")
    
#     # Financial
#     default_tax_rate = serializers.DecimalField(max_digits=5, decimal_places=2, default=18.00)
#     currency = serializers.CharField(default='INR', max_length=3)
#     currency_symbol = serializers.CharField(default='₹', max_length=5)
    
#     # Notifications
#     send_sms_notifications = serializers.BooleanField(default=True)
#     send_email_notifications = serializers.BooleanField(default=True)
#     appointment_reminder_hours = serializers.IntegerField(default=24, min_value=1)
    
#     # Security
#     require_doctor_approval = serializers.BooleanField(default=False, help_text="Require doctor approval for prescriptions")
#     enable_eod_locking = serializers.BooleanField(default=True)
    
#     class Meta:
#         fields = [
#             'allow_online_appointments', 'max_daily_appointments', 'appointment_duration',
#             'default_tax_rate', 'currency', 'currency_symbol',
#             'send_sms_notifications', 'send_email_notifications', 'appointment_reminder_hours',
#             'require_doctor_approval', 'enable_eod_locking',
#         ]


# class BranchImportSerializer(serializers.Serializer):
#     """Serializer for importing branches from CSV/Excel"""
    
#     file = serializers.FileField(required=True)
#     overwrite = serializers.BooleanField(default=False, help_text="Overwrite existing branches")
    
#     class Meta:
#         fields = ['file', 'overwrite']


# class BranchExportSerializer(serializers.Serializer):
#     """Serializer for exporting branches"""
    
#     format = serializers.ChoiceField(choices=['csv', 'excel', 'json'], default='json')
#     include_inactive = serializers.BooleanField(default=False)
#     include_counters = serializers.BooleanField(default=False)
    
#     class Meta:
#         fields = ['format', 'include_inactive', 'include_counters']


# class BranchSearchSerializer(serializers.Serializer):
#     """Serializer for searching branches"""
    
#     q = serializers.CharField(required=False, help_text="Search term")
#     city = serializers.CharField(required=False)
#     state = serializers.CharField(required=False)
#     active_only = serializers.BooleanField(default=True)
#     has_counter = serializers.BooleanField(required=False)
    
#     # Pagination
#     page = serializers.IntegerField(default=1, min_value=1)
#     page_size = serializers.IntegerField(default=20, min_value=1, max_value=100)
    
#     class Meta:
#         fields = ['q', 'city', 'state', 'active_only', 'has_counter', 'page', 'page_size']


# class CounterStatsSerializer(serializers.Serializer):
#     """Serializer for counter statistics"""
    
#     counter_id = serializers.UUIDField() 
#     counter_name = serializers.CharField()
#     branch_name = serializers.CharField()
    
#     # Usage stats
#     todays_transactions = serializers.IntegerField()
#     weeks_transactions = serializers.IntegerField()
#     total_transactions = serializers.IntegerField()
    
#     # User stats
#     current_user = serializers.CharField(allow_null=True)
#     last_user = serializers.CharField(allow_null=True)
#     last_used_at = serializers.DateTimeField(allow_null=True)
    
#     # Performance
#     average_transaction_time = serializers.IntegerField(help_text="Seconds")
#     peak_hour = serializers.CharField(allow_null=True)
    
#     class Meta:
#         fields = [
#             'counter_id', 'counter_name', 'branch_name',
#             'todays_transactions', 'weeks_transactions', 'total_transactions',
#             'current_user', 'last_user', 'last_used_at',
#             'average_transaction_time', 'peak_hour',
#         ]


# class BranchGeoSerializer(serializers.Serializer):
#     """Serializer for branch geographical data"""
    
#     branch_id = serializers.UUIDField()
#     name = serializers.CharField()
#     code = serializers.CharField()
#     address = serializers.CharField()
#     phone = serializers.CharField()
    
#     # Coordinates (if available)
#     latitude = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True)
#     longitude = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True)
    
#     # Status
#     is_active = serializers.BooleanField()
#     is_eod_locked = serializers.BooleanField()
    
#     # Additional info
#     todays_appointments = serializers.IntegerField()
#     active_staff = serializers.IntegerField()
    
#     class Meta:
#         fields = [
#             'branch_id', 'name', 'code', 'address', 'phone',
#             'latitude', 'longitude',
#             'is_active', 'is_eod_locked',
#             'todays_appointments', 'active_staff',
#         ]


# class BranchSyncSerializer(serializers.Serializer):
#     """Serializer for branch data synchronization"""
    
#     last_sync = serializers.DateTimeField(required=False)
#     include = serializers.ListField(
#         child=serializers.ChoiceField(choices=[
#             'branches', 'counters', 'staff', 'schedules'
#         ]),
#         default=['branches']
#     )
    
#     class Meta:
#         fields = ['last_sync', 'include']