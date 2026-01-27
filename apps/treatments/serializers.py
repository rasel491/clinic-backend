#apps/treatments/serializers.py
# apps/treatments/serializers.py
from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
import json

from core.mixins.audit_fields import AuditFieldsMixin
from .models import (
    TreatmentCategory, Treatment, ToothChart,
    TreatmentPlan, TreatmentPlanItem, TreatmentNote,
    TreatmentTemplate, TemplateTreatment
)
from apps.patients.models import Patient
from apps.doctors.models import Doctor
from apps.clinics.models import Branch
from apps.visits.models import Visit


# ===========================================
# UTILITY SERIALIZERS
# ===========================================
class MinimalPatientSerializer(serializers.ModelSerializer):
    """Minimal patient serializer"""
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = Patient
        fields = ['id', 'patient_id', 'full_name', 'gender', 'date_of_birth']


class MinimalDoctorSerializer(serializers.ModelSerializer):
    """Minimal doctor serializer"""
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = Doctor
        fields = ['id', 'doctor_id', 'full_name', 'specialization']


class MinimalBranchSerializer(serializers.ModelSerializer):
    """Minimal branch serializer"""
    
    class Meta:
        model = Branch
        fields = ['id', 'name', 'code', 'address']


class MinimalTreatmentSerializer(serializers.ModelSerializer):
    """Minimal treatment serializer"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    duration_display = serializers.CharField(read_only=True)
    
    class Meta:
        model = Treatment
        fields = [
            'id', 'code', 'name', 'display_name', 'category', 'category_name',
            'base_price', 'total_price', 'duration_display', 'difficulty'
        ]


class MinimalVisitSerializer(serializers.ModelSerializer):
    """Minimal visit serializer"""
    
    class Meta:
        model = Visit
        fields = ['id', 'visit_id', 'scheduled_date', 'scheduled_time', 'status']


# ===========================================
# CORE MODELS SERIALIZERS
# ===========================================
class TreatmentCategorySerializer(serializers.ModelSerializer):
    """Serializer for TreatmentCategory"""
    
    treatment_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = TreatmentCategory
        fields = [
            'id', 'name', 'code', 'description', 'icon', 'color', 'order',
            'is_active', 'keywords', 'display_in_portal', 'treatment_count',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
    def validate_code(self, value):
        """Ensure code is unique"""
        if self.instance and self.instance.code == value:
            return value
        
        if TreatmentCategory.objects.filter(code=value).exists():
            raise serializers.ValidationError("Category code already exists")
        return value.upper()


class ToothChartSerializer(serializers.ModelSerializer):
    """Serializer for ToothChart"""
    
    class Meta:
        model = ToothChart
        fields = [
            'id', 'tooth_number', 'quadrant', 'fdi_notation', 
            'universal_notation', 'name', 'type', 'is_active'
        ]


class TreatmentSerializer(serializers.ModelSerializer):
    """Serializer for Treatment"""
    
    category = TreatmentCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=TreatmentCategory.objects.filter(is_active=True),
        write_only=True,
        source='category'
    )
    
    # Calculated fields
    doctor_fee = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    assistant_fee = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    tax_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    duration_display = serializers.CharField(read_only=True)
    clinic_cost = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = Treatment
        fields = [
            'id', 'code', 'name', 'display_name', 'category', 'category_id',
            'base_price', 'min_price', 'max_price', 'doctor_fee_percentage',
            'assistant_fee_percentage', 'tax_percentage', 'doctor_fee',
            'assistant_fee', 'tax_amount', 'total_price', 'clinic_cost',
            'difficulty', 'duration_value', 'duration_unit', 'duration_display',
            'num_sessions', 'recovery_days', 'description', 'procedure_steps',
            'materials_required', 'equipment_required', 'contraindications',
            'post_op_instructions', 'success_rate', 'suitable_for_age',
            'suitable_for_gender', 'medical_conditions', 'requires_lab',
            'lab_type', 'lab_days', 'inventory_items', 'is_active', 'is_popular',
            'popularity_score', 'order', 'display_in_portal', 'version',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'created_by', 'updated_by',
            'popularity_score', 'doctor_fee', 'assistant_fee', 'tax_amount',
            'total_price', 'clinic_cost', 'duration_display'
        ]
    
    def validate_code(self, value):
        """Ensure code is unique"""
        if self.instance and self.instance.code == value:
            return value
        
        if Treatment.objects.filter(code=value).exists():
            raise serializers.ValidationError("Treatment code already exists")
        return value.upper()
    
    def validate(self, data):
        """Validate treatment data"""
        # Validate price ranges
        base_price = data.get('base_price', getattr(self.instance, 'base_price', None))
        min_price = data.get('min_price', getattr(self.instance, 'min_price', None))
        max_price = data.get('max_price', getattr(self.instance, 'max_price', None))
        
        if min_price and max_price:
            if min_price > max_price:
                raise serializers.ValidationError({
                    'min_price': 'Minimum price cannot be greater than maximum price'
                })
            
            if base_price and (base_price < min_price or base_price > max_price):
                raise serializers.ValidationError({
                    'base_price': f'Base price must be between {min_price} and {max_price}'
                })
        
        # Validate percentages
        doctor_fee = data.get('doctor_fee_percentage', getattr(self.instance, 'doctor_fee_percentage', 30))
        assistant_fee = data.get('assistant_fee_percentage', getattr(self.instance, 'assistant_fee_percentage', 5))
        tax = data.get('tax_percentage', getattr(self.instance, 'tax_percentage', 18))
        
        total_percentage = doctor_fee + assistant_fee + tax
        if total_percentage > 100:
            raise serializers.ValidationError({
                'doctor_fee_percentage': f'Total percentage (doctor + assistant + tax) cannot exceed 100%. Current: {total_percentage}%'
            })
        
        return data


# ===========================================
# TREATMENT PLAN SERIALIZERS
# ===========================================
class TreatmentPlanItemSerializer(serializers.ModelSerializer):
    """Serializer for TreatmentPlanItem"""
    
    treatment = MinimalTreatmentSerializer(read_only=True)
    treatment_id = serializers.PrimaryKeyRelatedField(
        queryset=Treatment.objects.filter(is_active=True),
        write_only=True,
        source='treatment'
    )
    
    scheduled_visit = MinimalVisitSerializer(read_only=True)
    scheduled_visit_id = serializers.PrimaryKeyRelatedField(
        queryset=Visit.objects.all(),
        write_only=True,
        source='scheduled_visit',
        required=False,
        allow_null=True
    )
    
    performed_by = MinimalDoctorSerializer(read_only=True)
    performed_by_id = serializers.PrimaryKeyRelatedField(
        queryset=Doctor.objects.filter(is_active=True),
        write_only=True,
        source='performed_by',
        required=False,
        allow_null=True
    )
    
    # Calculated fields
    duration_minutes = serializers.IntegerField(read_only=True)
    doctor_commission = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = TreatmentPlanItem
        fields = [
            'id', 'treatment_plan', 'treatment', 'treatment_id', 'visit_number',
            'order', 'status', 'phase', 'scheduled_date', 'scheduled_visit',
            'scheduled_visit_id', 'depends_on', 'actual_amount', 'discount_applied',
            'is_paid', 'payment_reference', 'tooth_number', 'surface', 'quadrant',
            'tooth_condition', 'materials_used', 'equipment_used', 'procedure_notes',
            'complications', 'anesthesia_type', 'anesthesia_amount', 'performed_by',
            'performed_by_id', 'assistant', 'start_time', 'end_time', 'completed_date',
            'follow_up_required', 'follow_up_days', 'follow_up_notes', 'quality_score',
            'patient_feedback', 'duration_minutes', 'doctor_commission',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'created_by', 'updated_by',
            'duration_minutes', 'doctor_commission'
        ]
    
    def validate(self, data):
        """Validate plan item data"""
        treatment_plan = data.get('treatment_plan') or getattr(self.instance, 'treatment_plan', None)
        
        # Ensure visit number is unique within plan
        visit_number = data.get('visit_number')
        if treatment_plan and visit_number:
            existing = TreatmentPlanItem.objects.filter(
                treatment_plan=treatment_plan,
                visit_number=visit_number
            )
            if self.instance:
                existing = existing.exclude(id=self.instance.id)
            
            if existing.exists():
                raise serializers.ValidationError({
                    'visit_number': f'Visit number {visit_number} already exists in this plan'
                })
        
        # Validate dependencies
        depends_on = data.get('depends_on')
        if depends_on and depends_on.treatment_plan != treatment_plan:
            raise serializers.ValidationError({
                'depends_on': 'Dependency must be within the same treatment plan'
            })
        
        # Validate scheduled visit belongs to same patient
        scheduled_visit = data.get('scheduled_visit')
        if treatment_plan and scheduled_visit:
            if scheduled_visit.patient != treatment_plan.patient:
                raise serializers.ValidationError({
                    'scheduled_visit': 'Visit must belong to the same patient'
                })
        
        return data


class TreatmentNoteSerializer(serializers.ModelSerializer):
    """Serializer for TreatmentNote"""
    
    treatment_plan_item_details = TreatmentPlanItemSerializer(
        source='treatment_plan_item',
        read_only=True
    )
    
    class Meta:
        model = TreatmentNote
        fields = [
            'id', 'treatment_plan_item', 'treatment_plan_item_details',
            'note_type', 'content', 'attachments', 'is_critical',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']


class TreatmentPlanSerializer(serializers.ModelSerializer):
    """Serializer for TreatmentPlan"""
    
    patient = MinimalPatientSerializer(read_only=True)
    patient_id = serializers.PrimaryKeyRelatedField(
        queryset=Patient.objects.all(),
        write_only=True,
        source='patient'
    )
    
    doctor = MinimalDoctorSerializer(read_only=True)
    doctor_id = serializers.PrimaryKeyRelatedField(
        queryset=Doctor.objects.filter(is_active=True),
        write_only=True,
        source='doctor'
    )
    
    branch = MinimalBranchSerializer(read_only=True)
    branch_id = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.filter(is_active=True),
        write_only=True,
        source='branch'
    )
    
    referred_by = MinimalDoctorSerializer(read_only=True)
    referred_by_id = serializers.PrimaryKeyRelatedField(
        queryset=Doctor.objects.filter(is_active=True),
        write_only=True,
        source='referred_by',
        required=False,
        allow_null=True
    )
    
    # Related fields
    plan_items = TreatmentPlanItemSerializer(many=True, read_only=True)
    clinical_notes = TreatmentNoteSerializer(many=True, read_only=True)
    revisions = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    
    # Calculated fields
    balance_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_paid = serializers.BooleanField(read_only=True)
    progress_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    estimated_duration_days = serializers.IntegerField(read_only=True, allow_null=True)
    
    class Meta:
        model = TreatmentPlan
        fields = [
            'id', 'plan_id', 'patient', 'patient_id', 'doctor', 'doctor_id',
            'branch', 'branch_id', 'referred_by', 'referred_by_id', 'name',
            'status', 'priority', 'version', 'parent_plan', 'total_estimated_amount',
            'discount_percentage', 'discount_amount', 'tax_amount', 'final_amount',
            'paid_amount', 'payment_plan', 'insurance_coverage', 'insurance_approved',
            'insurance_notes', 'estimated_start_date', 'estimated_end_date',
            'actual_start_date', 'actual_end_date', 'next_review_date', 'diagnosis',
            'diagnosis_codes', 'treatment_goals', 'clinical_notes', 'pre_op_instructions',
            'post_op_instructions', 'risks_and_complications', 'dental_chart',
            'consent_form_signed', 'consent_form_url', 'xray_images', 'complexity_score',
            'satisfaction_score', 'balance_amount', 'is_paid', 'progress_percentage',
            'estimated_duration_days', 'plan_items', 'clinical_notes', 'revisions',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'plan_id', 'created_at', 'updated_at', 'created_by', 'updated_by',
            'discount_amount', 'final_amount', 'balance_amount', 'is_paid',
            'progress_percentage', 'estimated_duration_days'
        ]
    
    def validate(self, data):
        """Validate treatment plan data"""
        # Validate dates
        estimated_start = data.get('estimated_start_date')
        estimated_end = data.get('estimated_end_date')
        
        if estimated_start and estimated_end and estimated_start > estimated_end:
            raise serializers.ValidationError({
                'estimated_end_date': 'End date must be after start date'
            })
        
        # Validate discount
        discount = data.get('discount_percentage', 0)
        if discount < 0 or discount > 100:
            raise serializers.ValidationError({
                'discount_percentage': 'Discount must be between 0 and 100'
            })
        
        # Validate insurance
        insurance_coverage = data.get('insurance_coverage', 0)
        total_amount = data.get('total_estimated_amount', 0)
        if insurance_coverage > total_amount:
            raise serializers.ValidationError({
                'insurance_coverage': 'Insurance coverage cannot exceed total amount'
            })
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """Create treatment plan with audit fields"""
        request = self.context.get('request')
        
        if request and request.user:
            validated_data['created_by'] = request.user
            validated_data['updated_by'] = request.user
        
        return super().create(validated_data)
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update treatment plan with audit fields"""
        request = self.context.get('request')
        
        if request and request.user:
            validated_data['updated_by'] = request.user
        
        return super().update(instance, validated_data)


class TreatmentPlanCreateSerializer(serializers.Serializer):
    """Serializer for creating treatment plans with items"""
    
    patient_id = serializers.IntegerField(required=True)
    doctor_id = serializers.IntegerField(required=True)
    branch_id = serializers.IntegerField(required=True)
    name = serializers.CharField(max_length=200, required=True)
    diagnosis = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(
        child=serializers.DictField(),
        required=True,
        help_text="List of treatment items with treatment_id, visit_number, etc."
    )
    
    def validate(self, data):
        """Validate plan creation data"""
        # Validate patient exists
        try:
            patient = Patient.objects.get(id=data['patient_id'])
        except Patient.DoesNotExist:
            raise serializers.ValidationError({'patient_id': 'Patient not found'})
        
        # Validate doctor exists
        try:
            doctor = Doctor.objects.get(id=data['doctor_id'])
        except Doctor.DoesNotExist:
            raise serializers.ValidationError({'doctor_id': 'Doctor not found'})
        
        # Validate branch exists
        try:
            branch = Branch.objects.get(id=data['branch_id'])
        except Branch.DoesNotExist:
            raise serializers.ValidationError({'branch_id': 'Branch not found'})
        
        # Validate treatment items
        total_amount = Decimal('0.00')
        for i, item in enumerate(data['items']):
            try:
                treatment = Treatment.objects.get(id=item.get('treatment_id'))
                total_amount += treatment.total_price
            except Treatment.DoesNotExist:
                raise serializers.ValidationError({
                    f'items[{i}].treatment_id': 'Treatment not found'
                })
        
        data['total_estimated_amount'] = total_amount
        return data


# ===========================================
# TEMPLATE SERIALIZERS
# ===========================================
class TemplateTreatmentSerializer(serializers.ModelSerializer):
    """Serializer for TemplateTreatment"""
    
    treatment_details = MinimalTreatmentSerializer(source='treatment', read_only=True)
    
    class Meta:
        model = TemplateTreatment
        fields = ['id', 'template', 'treatment', 'treatment_details', 'order', 'visit_number']


class TreatmentTemplateSerializer(serializers.ModelSerializer):
    """Serializer for TreatmentTemplate"""
    
    category = TreatmentCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=TreatmentCategory.objects.filter(is_active=True),
        write_only=True,
        source='category'
    )
    
    treatments = TemplateTreatmentSerializer(source='templatetreatment_set', many=True, read_only=True)
    treatment_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of treatment IDs to include in template"
    )
    
    class Meta:
        model = TreatmentTemplate
        fields = [
            'id', 'name', 'code', 'description', 'category', 'category_id',
            'total_price', 'is_active', 'treatments', 'treatment_ids',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'created_by', 'updated_by',
            'total_price'
        ]
    
    @transaction.atomic
    def create(self, validated_data):
        """Create template with treatments"""
        treatment_ids = validated_data.pop('treatment_ids', [])
        template = super().create(validated_data)
        
        # Add treatments to template
        total_price = Decimal('0.00')
        for order, treatment_id in enumerate(treatment_ids):
            try:
                treatment = Treatment.objects.get(id=treatment_id)
                TemplateTreatment.objects.create(
                    template=template,
                    treatment=treatment,
                    order=order
                )
                total_price += treatment.total_price
            except Treatment.DoesNotExist:
                pass
        
        # Update total price
        template.total_price = total_price
        template.save()
        
        return template
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update template with treatments"""
        treatment_ids = validated_data.pop('treatment_ids', None)
        
        if treatment_ids is not None:
            # Clear existing treatments
            instance.templatetreatment_set.all().delete()
            
            # Add new treatments
            total_price = Decimal('0.00')
            for order, treatment_id in enumerate(treatment_ids):
                try:
                    treatment = Treatment.objects.get(id=treatment_id)
                    TemplateTreatment.objects.create(
                        template=instance,
                        treatment=treatment,
                        order=order
                    )
                    total_price += treatment.total_price
                except Treatment.DoesNotExist:
                    pass
            
            validated_data['total_price'] = total_price
        
        return super().update(instance, validated_data)


# ===========================================
# ACTION SERIALIZERS
# ===========================================
class TreatmentPlanStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating treatment plan status"""
    
    status = serializers.ChoiceField(choices=TreatmentPlan.STATUS_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate status transition"""
        view = self.context.get('view')
        if not view:
            return data
        
        plan = view.get_object()
        new_status = data['status']
        
        # Define allowed status transitions
        allowed_transitions = {
            'DRAFT': ['PROPOSED', 'CANCELLED'],
            'PROPOSED': ['ACCEPTED', 'REVISED', 'CANCELLED'],
            'REVISED': ['PROPOSED', 'CANCELLED'],
            'ACCEPTED': ['CONTRACT_SIGNED', 'IN_PROGRESS', 'CANCELLED'],
            'CONTRACT_SIGNED': ['IN_PROGRESS', 'CANCELLED'],
            'IN_PROGRESS': ['ON_HOLD', 'COMPLETED', 'CANCELLED', 'REFERRED'],
            'ON_HOLD': ['IN_PROGRESS', 'CANCELLED'],
            'COMPLETED': [],
            'CANCELLED': [],
            'REFERRED': ['CANCELLED'],
        }
        
        if new_status not in allowed_transitions.get(plan.status, []):
            raise serializers.ValidationError({
                'status': f'Cannot transition from {plan.status} to {new_status}'
            })
        
        return data


class TreatmentPlanItemStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating plan item status"""
    
    status = serializers.ChoiceField(choices=TreatmentPlanItem.STATUS_CHOICES)
    notes = serializers.CharField(required=False, allow_blank=True)
    completed_date = serializers.DateField(required=False, allow_null=True)
    
    def validate(self, data):
        """Validate item status transition"""
        view = self.context.get('view')
        if not view:
            return data
        
        item = view.get_object()
        new_status = data['status']
        
        # Check dependencies
        if new_status in ['IN_PROGRESS', 'COMPLETED']:
            if item.depends_on and item.depends_on.status != 'COMPLETED':
                raise serializers.ValidationError({
                    'status': f'Dependency {item.depends_on} must be completed first'
                })
        
        return data


class ApplyTemplateSerializer(serializers.Serializer):
    """Serializer for applying template to patient"""
    
    template_id = serializers.IntegerField(required=True)
    patient_id = serializers.IntegerField(required=True)
    doctor_id = serializers.IntegerField(required=True)
    branch_id = serializers.IntegerField(required=True)
    start_date = serializers.DateField(required=False)
    
    def validate(self, data):
        """Validate template application"""
        try:
            template = TreatmentTemplate.objects.get(id=data['template_id'], is_active=True)
            data['template'] = template
        except TreatmentTemplate.DoesNotExist:
            raise serializers.ValidationError({'template_id': 'Template not found or inactive'})
        
        try:
            patient = Patient.objects.get(id=data['patient_id'])
            data['patient'] = patient
        except Patient.DoesNotExist:
            raise serializers.ValidationError({'patient_id': 'Patient not found'})
        
        try:
            doctor = Doctor.objects.get(id=data['doctor_id'], is_active=True)
            data['doctor'] = doctor
        except Doctor.DoesNotExist:
            raise serializers.ValidationError({'doctor_id': 'Doctor not found or inactive'})
        
        try:
            branch = Branch.objects.get(id=data['branch_id'])
            data['branch'] = branch
        except Branch.DoesNotExist:
            raise serializers.ValidationError({'branch_id': 'Branch not found'})
        
        return data