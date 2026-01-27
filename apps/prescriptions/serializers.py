# apps/prescriptions/serializers.py

from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import re

from .models import (
    Prescription, Medication, PrescriptionItem,
    PrescriptionTemplate, TemplateMedication
)
from apps.doctors.serializers import DoctorMinimalSerializer
from apps.patients.serializers import PatientMinimalSerializer

# Import from patients app
# try:
#     from apps.patients.serializers import PatientMinimalSerializer
# except ImportError:
#     # Fallback or create inline
#     class PatientMinimalSerializer(serializers.Serializer):
#         id = serializers.IntegerField()
#         patient_id = serializers.CharField()
#         full_name = serializers.CharField()

# # Import from doctors app
# try:
#     from apps.doctors.serializers import DoctorMinimalSerializer
# except ImportError:
#     # Fallback or create inline
#     class DoctorMinimalSerializer(serializers.Serializer):
#         id = serializers.IntegerField()
#         doctor_id = serializers.CharField()
#         full_name = serializers.CharField()
#         specialization = serializers.CharField()
class MedicationSerializer(serializers.ModelSerializer):
    """Serializer for Medication model"""
    
    stock_status = serializers.CharField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    needs_restocking = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Medication
        fields = [
            'id', 'medicine_id', 'name', 'generic_name', 'brand',
            'category', 'form', 'strength', 'unit',
            'in_stock', 'current_stock', 'min_stock_level', 'max_stock_level',
            'stock_status', 'needs_restocking',
            'unit_price', 'cost_price',
            'indications', 'contraindications', 'side_effects',
            'dosage_instructions', 'storage_instructions',
            'requires_prescription', 'schedule',
            'mfg_date', 'expiry_date', 'batch_number', 'is_expired',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'stock_status', 'is_expired', 'needs_restocking',
            'created_at', 'updated_at'
        ]
    
    def validate_medicine_id(self, value):
        """Validate medicine ID format"""
        if not value:
            raise serializers.ValidationError("Medicine ID is required")
        
        if Medication.objects.filter(medicine_id=value).exists():
            instance = self.instance
            if not instance or instance.medicine_id != value:
                raise serializers.ValidationError("Medicine ID already exists")
        
        return value
    
    def validate(self, attrs):
        """Additional validation"""
        expiry_date = attrs.get('expiry_date')
        mfg_date = attrs.get('mfg_date')
        
        if expiry_date and mfg_date and expiry_date <= mfg_date:
            raise serializers.ValidationError({
                'expiry_date': 'Expiry date must be after manufacturing date'
            })
        
        if attrs.get('current_stock', 0) < 0:
            raise serializers.ValidationError({
                'current_stock': 'Stock cannot be negative'
            })
        
        return attrs


class PrescriptionItemSerializer(serializers.ModelSerializer):
    """Serializer for PrescriptionItem model"""
    
    medication_info = MedicationSerializer(source='medication', read_only=True)
    remaining_quantity = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_fully_dispensed = serializers.BooleanField(read_only=True)
    total_duration_days = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = PrescriptionItem
        fields = [
            'id', 'prescription', 'medication', 'medication_info',
            'dosage', 'frequency', 'duration', 'duration_unit',
            'quantity', 'instructions',
            'unit_price', 'total_price',
            'is_dispensed', 'dispensed_quantity', 'remaining_quantity',
            'dispensed_at', 'dispensed_by', 'is_fully_dispensed',
            'total_duration_days',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'remaining_quantity', 'is_fully_dispensed', 'total_duration_days',
            'total_price', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def validate(self, attrs):
        """Validate prescription item"""
        medication = attrs.get('medication') or self.instance.medication if self.instance else None
        
        if medication and medication.requires_prescription and not medication.is_active:
            raise serializers.ValidationError({
                'medication': 'Medication is not active'
            })
        
        if medication and medication.is_expired:
            raise serializers.ValidationError({
                'medication': 'Medication has expired'
            })
        
        if attrs.get('quantity', 0) <= 0:
            raise serializers.ValidationError({
                'quantity': 'Quantity must be greater than 0'
            })
        
        return attrs


class PrescriptionSerializer(serializers.ModelSerializer):
    """Serializer for Prescription model"""
    
    patient_info = PatientMinimalSerializer(source='patient', read_only=True)
    doctor_info = DoctorMinimalSerializer(source='doctor', read_only=True)
    
    items = PrescriptionItemSerializer(many=True, read_only=True)
    items_count = serializers.IntegerField(read_only=True)
    total_quantity = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    is_valid = serializers.BooleanField(read_only=True)
    can_be_dispensed = serializers.BooleanField(read_only=True)
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    prescription_type_display = serializers.CharField(source='get_prescription_type_display', read_only=True)
    
    # For creating/updating items
    medication_items = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Prescription
        fields = [
            'id', 'prescription_id', 'prescription_type', 'prescription_type_display',
            'patient', 'patient_info', 'doctor', 'doctor_info', 'visit',
            'diagnosis', 'notes', 'instructions',
            'status', 'status_display', 'issue_date', 'valid_until',
            'is_refillable', 'max_refills', 'refills_remaining', 'last_refill_date',
            'is_signed', 'signed_at',
            'dispensing_pharmacy', 'dispensed_by', 'dispensed_at',
            'total_amount', 'insurance_covered', 'patient_payable',
            'items', 'items_count', 'total_quantity',
            'is_valid', 'can_be_dispensed',
            'medication_items',  # Write-only for creating items
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'prescription_id', 'is_valid', 'can_be_dispensed',
            'items_count', 'total_quantity', 'total_amount', 'patient_payable',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def validate(self, attrs):
        """Validate prescription data"""
        valid_until = attrs.get('valid_until')
        issue_date = attrs.get('issue_date') or timezone.now().date()
        
        if valid_until and valid_until < issue_date:
            raise serializers.ValidationError({
                'valid_until': 'Valid until date must be after issue date'
            })
        
        # Check if doctor is active and license is valid
        doctor = attrs.get('doctor') or self.instance.doctor if self.instance else None
        if doctor:
            if not doctor.is_active:
                raise serializers.ValidationError({
                    'doctor': 'Doctor is not active'
                })
            
            if not doctor.is_license_valid:
                raise serializers.ValidationError({
                    'doctor': 'Doctor license has expired'
                })
        
        return attrs
    
    def create(self, validated_data):
        """Create prescription with items"""
        medication_items = validated_data.pop('medication_items', [])
        
        with transaction.atomic():
            prescription = Prescription.objects.create(**validated_data)
            
            # Create prescription items
            for item_data in medication_items:
                medication_id = item_data.get('medication_id')
                quantity = item_data.get('quantity', 1)
                
                # Get medication
                try:
                    medication = Medication.objects.get(id=medication_id, is_active=True)
                except Medication.DoesNotExist:
                    raise serializers.ValidationError({
                        'medication_items': f'Medication with ID {medication_id} not found or inactive'
                    })
                
                # Create prescription item
                PrescriptionItem.objects.create(
                    prescription=prescription,
                    medication=medication,
                    dosage=item_data.get('dosage', 'As directed'),
                    frequency=item_data.get('frequency', 'BD'),
                    duration=item_data.get('duration', 7),
                    duration_unit=item_data.get('duration_unit', 'DAYS'),
                    quantity=quantity,
                    instructions=item_data.get('instructions', ''),
                    unit_price=medication.unit_price
                )
        
        return prescription
    
    def update(self, instance, validated_data):
        """Update prescription"""
        medication_items = validated_data.pop('medication_items', None)
        
        with transaction.atomic():
            prescription = super().update(instance, validated_data)
            
            # Update items if provided
            if medication_items is not None:
                # Delete existing items and create new ones
                prescription.items.all().delete()
                
                for item_data in medication_items:
                    medication_id = item_data.get('medication_id')
                    quantity = item_data.get('quantity', 1)
                    
                    try:
                        medication = Medication.objects.get(id=medication_id, is_active=True)
                    except Medication.DoesNotExist:
                        raise serializers.ValidationError({
                            'medication_items': f'Medication with ID {medication_id} not found or inactive'
                        })
                    
                    PrescriptionItem.objects.create(
                        prescription=prescription,
                        medication=medication,
                        dosage=item_data.get('dosage', 'As directed'),
                        frequency=item_data.get('frequency', 'BD'),
                        duration=item_data.get('duration', 7),
                        duration_unit=item_data.get('duration_unit', 'DAYS'),
                        quantity=quantity,
                        instructions=item_data.get('instructions', ''),
                        unit_price=medication.unit_price
                    )
        
        return prescription


class PrescriptionDispenseSerializer(serializers.Serializer):
    """Serializer for dispensing prescription"""
    
    pharmacy_id = serializers.IntegerField()
    items = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of items with medication_id and quantity"
    )
    
    def validate(self, attrs):
        """Validate dispense data"""
        items = attrs.get('items', [])
        
        if not items:
            raise serializers.ValidationError({
                'items': 'At least one item must be dispensed'
            })
        
        for item in items:
            if 'medication_id' not in item:
                raise serializers.ValidationError({
                    'items': 'Each item must have medication_id'
                })
            
            quantity = item.get('quantity', 0)
            if quantity <= 0:
                raise serializers.ValidationError({
                    'items': 'Dispense quantity must be greater than 0'
                })
        
        return attrs


class PrescriptionRefillSerializer(serializers.Serializer):
    """Serializer for refilling prescription"""
    
    refill_quantity = serializers.IntegerField(min_value=1, max_value=5, default=1)
    issue_date = serializers.DateField(default=timezone.now)
    valid_until = serializers.DateField(required=False)
    
    def validate(self, attrs):
        """Validate refill data"""
        issue_date = attrs['issue_date']
        valid_until = attrs.get('valid_until')
        
        if valid_until and valid_until < issue_date:
            raise serializers.ValidationError({
                'valid_until': 'Valid until date must be after issue date'
            })
        
        return attrs


class PrescriptionTemplateSerializer(serializers.ModelSerializer):
    """Serializer for PrescriptionTemplate"""
    
    specialization_display = serializers.CharField(source='get_specialization_display', read_only=True)
    
    class Meta:
        model = PrescriptionTemplate
        fields = [
            'id', 'template_id', 'name', 'description',
            'specialization', 'specialization_display',
            'diagnoses', 'default_diagnosis', 'default_notes', 'default_instructions',
            'is_active', 'usage_count',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'template_id', 'usage_count', 'created_at', 'updated_at', 
            'created_by', 'updated_by'
        ]


class TemplateMedicationSerializer(serializers.ModelSerializer):
    """Serializer for TemplateMedication"""
    
    medication_info = MedicationSerializer(source='medication', read_only=True)
    
    class Meta:
        model = TemplateMedication
        fields = [
            'id', 'template', 'medication', 'medication_info',
            'default_dosage', 'default_frequency', 'default_duration',
            'default_duration_unit', 'default_quantity', 'default_instructions',
            'display_order',
            'created_at', 'updated_at'
        ]


class PrescriptionSearchSerializer(serializers.Serializer):
    """Serializer for prescription search"""
    
    patient_id = serializers.IntegerField(required=False)
    doctor_id = serializers.IntegerField(required=False)
    prescription_id = serializers.CharField(required=False)
    status = serializers.CharField(required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    
    def validate(self, attrs):
        """Validate search parameters"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                'end_date': 'End date must be after start date'
            })
        
        return attrs


class MedicationStockUpdateSerializer(serializers.Serializer):
    """Serializer for updating medication stock"""
    
    action = serializers.ChoiceField(choices=['add', 'subtract', 'set'])
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.01)
    reason = serializers.CharField(max_length=500, required=False)
    reference_number = serializers.CharField(max_length=100, required=False)
    
    def validate(self, attrs):
        """Validate stock update"""
        action = attrs['action']
        quantity = attrs['quantity']
        
        if action == 'subtract' and quantity <= 0:
            raise serializers.ValidationError({
                'quantity': 'Quantity must be greater than 0 for subtraction'
            })
        
        return attrs


class PrescriptionStatsSerializer(serializers.Serializer):
    """Serializer for prescription statistics"""
    
    total_prescriptions = serializers.IntegerField()
    prescriptions_today = serializers.IntegerField()
    prescriptions_this_month = serializers.IntegerField()
    pending_dispensing = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    revenue_today = serializers.DecimalField(max_digits=12, decimal_places=2)
    revenue_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    top_medications = serializers.ListField(child=serializers.DictField())
    prescriptions_by_status = serializers.DictField()
    prescriptions_by_doctor = serializers.ListField(child=serializers.DictField())