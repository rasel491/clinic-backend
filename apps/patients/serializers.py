# clinic/Backend/apps/patients/serializers.py
from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
import logging

from .models import Patient
from apps.accounts.serializers import UserSerializer

logger = logging.getLogger(__name__)


class PatientSerializer(serializers.ModelSerializer):
    """Main serializer for Patient model"""
    
    # Nested serializers
    user_details = UserSerializer(source='user', read_only=True)
    registered_branch_name = serializers.CharField(source='registered_branch.name', read_only=True)
    
    # Computed fields
    age = serializers.SerializerMethodField()
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    phone = serializers.CharField(source='user.phone', read_only=True)
    
    class Meta:
        model = Patient
        fields = [
            'id',
            'user',
            'user_details',
            'patient_id',
            'date_of_birth',
            'age',
            'gender',
            'blood_group',
            'full_name',
            'email',
            'phone',
            'emergency_contact_name',
            'emergency_contact_phone',
            'emergency_contact_relation',
            'allergies',
            'chronic_conditions',
            'current_medications',
            'registered_at',
            'registered_branch',
            'registered_branch_name',
            'is_insurance_verified',
            'insurance_provider',
            'insurance_id',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'patient_id', 'registered_at', 
            'created_at', 'updated_at', 'age',
            'full_name', 'email', 'phone', 'user_details',
            'registered_branch_name'
        ]
    
    def get_age(self, obj):
        """Calculate age from date of birth"""
        if not obj.date_of_birth:
            return None
        
        today = timezone.now().date()
        return today.year - obj.date_of_birth.year - (
            (today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day)
        )
    
    def validate_date_of_birth(self, value):
        """Validate date of birth"""
        if value:
            if value > timezone.now().date():
                raise serializers.ValidationError("Date of birth cannot be in the future")
            
            # Check if patient is at least 1 year old
            age = timezone.now().date().year - value.year
            if age > 120:
                raise serializers.ValidationError("Please verify the date of birth")
        
        return value
    
    def validate_emergency_contact_phone(self, value):
        """Validate emergency contact phone"""
        if value and len(value) < 10:
            raise serializers.ValidationError("Emergency contact phone must be at least 10 digits")
        return value


class PatientCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new patients"""
    
    # User fields that can be created along with patient
    email = serializers.EmailField(write_only=True)
    full_name = serializers.CharField(max_length=255, write_only=True)
    phone = serializers.CharField(max_length=15, write_only=True)
    password = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = Patient
        fields = [
            'email',
            'full_name',
            'phone',
            'password',
            'date_of_birth',
            'gender',
            'blood_group',
            'emergency_contact_name',
            'emergency_contact_phone',
            'emergency_contact_relation',
            'allergies',
            'chronic_conditions',
            'current_medications',
            'registered_branch',
            'insurance_provider',
            'insurance_id',
        ]
    
    def validate(self, data):
        """Validate patient creation data"""
        # Check if user already exists
        from apps.accounts.models import User
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({
                'email': 'User with this email already exists'
            })
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """Create patient with user account"""
        from apps.accounts.models import User
        from core.constants import UserRoles
        
        # Extract user data
        user_data = {
            'email': validated_data.pop('email'),
            'full_name': validated_data.pop('full_name'),
            'phone': validated_data.pop('phone'),
            'role': UserRoles.PATIENT,
        }
        
        password = validated_data.pop('password', None)
        
        # Create user
        user = User.objects.create(**user_data)
        if password:
            user.set_password(password)
        else:
            # Generate random password if not provided
            import secrets
            password = secrets.token_urlsafe(12)
            user.set_password(password)
        
        user.save()
        
        # Create patient
        patient = Patient.objects.create(user=user, **validated_data)
        
        logger.info(f"Patient created: {patient.patient_id} by {self.context['request'].user}")
        
        return patient


class PatientUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating patient information"""
    
    class Meta:
        model = Patient
        fields = [
            'date_of_birth',
            'gender',
            'blood_group',
            'emergency_contact_name',
            'emergency_contact_phone',
            'emergency_contact_relation',
            'allergies',
            'chronic_conditions',
            'current_medications',
            'is_insurance_verified',
            'insurance_provider',
            'insurance_id',
        ]
    
    def validate(self, data):
        """Validate update data"""
        # Add any update-specific validation here
        return data


class PatientListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for patient lists"""
    
    full_name = serializers.CharField(source='user.full_name')
    email = serializers.CharField(source='user.email')
    phone = serializers.CharField(source='user.phone')
    age = serializers.SerializerMethodField()
    registered_branch_name = serializers.CharField(source='registered_branch.name', read_only=True)
    
    class Meta:
        model = Patient
        fields = [
            'id',
            'patient_id',
            'full_name',
            'email',
            'phone',
            'date_of_birth',
            'age',
            'gender',
            'blood_group',
            'registered_branch',
            'registered_branch_name',
            'is_insurance_verified',
            'created_at',
        ]
    
    def get_age(self, obj):
        """Calculate age from date of birth"""
        if not obj.date_of_birth:
            return None
        
        today = timezone.now().date()
        return today.year - obj.date_of_birth.year - (
            (today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day)
        )


class PatientMedicalHistorySerializer(serializers.Serializer):
    """Serializer for patient medical history"""
    
    allergies = serializers.CharField(allow_blank=True)
    chronic_conditions = serializers.CharField(allow_blank=True)
    current_medications = serializers.CharField(allow_blank=True)
    
    class Meta:
        fields = ['allergies', 'chronic_conditions', 'current_medications']


class PatientSearchSerializer(serializers.Serializer):
    """Serializer for searching patients"""
    
    q = serializers.CharField(required=False, help_text="Search term (name, email, phone, patient_id)")
    gender = serializers.ChoiceField(choices=Patient.GENDER_CHOICES, required=False)
    blood_group = serializers.CharField(required=False)
    has_insurance = serializers.BooleanField(required=False)
    branch_id = serializers.UUIDField(required=False)
    
    # Date filters
    registered_after = serializers.DateField(required=False)
    registered_before = serializers.DateField(required=False)
    age_min = serializers.IntegerField(min_value=0, max_value=120, required=False)
    age_max = serializers.IntegerField(min_value=0, max_value=120, required=False)
    
    # Pagination
    page = serializers.IntegerField(default=1, min_value=1)
    page_size = serializers.IntegerField(default=20, min_value=1, max_value=100)
    
    class Meta:
        fields = [
            'q', 'gender', 'blood_group', 'has_insurance', 'branch_id',
            'registered_after', 'registered_before', 'age_min', 'age_max',
            'page', 'page_size'
        ]

class PatientMinimalSerializer(serializers.ModelSerializer):
    """Minimal patient serializer for nested relationships"""
    
    full_name = serializers.CharField(source='user.full_name')
    
    class Meta:
        model = Patient
        fields = ['id', 'patient_id', 'full_name', 'date_of_birth', 'gender']
        read_only_fields = fields
        
class PatientStatsSerializer(serializers.Serializer):
    """Serializer for patient statistics"""
    
    total_patients = serializers.IntegerField()
    patients_today = serializers.IntegerField()
    patients_this_week = serializers.IntegerField()
    patients_this_month = serializers.IntegerField()
    
    gender_distribution = serializers.DictField()
    age_distribution = serializers.DictField()
    blood_group_distribution = serializers.DictField()
    
    insurance_stats = serializers.DictField()
    branch_distribution = serializers.DictField()
    
    class Meta:
        fields = [
            'total_patients', 'patients_today', 'patients_this_week', 'patients_this_month',
            'gender_distribution', 'age_distribution', 'blood_group_distribution',
            'insurance_stats', 'branch_distribution'
        ]


class PatientImportSerializer(serializers.Serializer):
    """Serializer for importing patients from CSV/Excel"""
    
    file = serializers.FileField(required=True)
    branch_id = serializers.UUIDField(required=False)
    send_welcome_email = serializers.BooleanField(default=False)
    
    class Meta:
        fields = ['file', 'branch_id', 'send_welcome_email']


class PatientExportSerializer(serializers.Serializer):
    """Serializer for exporting patients"""
    
    format = serializers.ChoiceField(choices=['csv', 'excel', 'json'], default='json')
    include_medical_history = serializers.BooleanField(default=False)
    include_appointments = serializers.BooleanField(default=False)
    branch_id = serializers.UUIDField(required=False)
    
    class Meta:
        fields = ['format', 'include_medical_history', 'include_appointments', 'branch_id']


class EmergencyContactSerializer(serializers.Serializer):
    """Serializer for emergency contact information"""
    
    name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=15)
    relation = serializers.CharField(max_length=50)
    
    class Meta:
        fields = ['name', 'phone', 'relation']


