from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal

from .models import Invoice, InvoiceItem, DiscountPolicy, AppliedDiscount
from apps.patients.models import Patient
from apps.doctors.models import Doctor
from apps.clinics.models import Branch
from apps.visits.models import Visit
from apps.treatments.models import Treatment, TreatmentPlanItem
from core import constants
# from core.constants import PaymentModes 

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


class MinimalVisitSerializer(serializers.ModelSerializer):
    """Minimal visit serializer"""
    
    class Meta:
        model = Visit
        fields = ['id', 'visit_id', 'scheduled_date', 'scheduled_time', 'status']


class MinimalTreatmentSerializer(serializers.ModelSerializer):
    """Minimal treatment serializer"""
    
    class Meta:
        model = Treatment
        fields = ['id', 'code', 'name', 'base_price', 'total_price']


# ===========================================
# INVOICE ITEM SERIALIZERS
# ===========================================
class InvoiceItemSerializer(serializers.ModelSerializer):
    """Serializer for InvoiceItem"""
    
    treatment_details = MinimalTreatmentSerializer(source='treatment', read_only=True)
    doctor_details = MinimalDoctorSerializer(source='doctor', read_only=True)
    
    treatment_id = serializers.PrimaryKeyRelatedField(
        queryset=Treatment.objects.filter(is_active=True),
        write_only=True,
        source='treatment',
        required=False,
        allow_null=True
    )
    
    doctor_id = serializers.PrimaryKeyRelatedField(
        queryset=Doctor.objects.filter(is_active=True),
        write_only=True,
        source='doctor',
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = InvoiceItem
        fields = [
            'id', 'invoice', 'item_type', 'description', 'code',
            'treatment', 'treatment_details', 'treatment_id',
            'doctor', 'doctor_details', 'doctor_id',
            'unit_price', 'quantity', 'discount_percentage',
            'discount_amount', 'tax_percentage', 'tax_amount',
            'total_amount', 'doctor_commission_percentage',
            'doctor_commission_amount', 'is_taxable', 'hsn_code',
            'batch_number', 'expiry_date', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'discount_amount', 'tax_amount', 'total_amount',
            'doctor_commission_amount', 'created_at', 'updated_at'
        ]
    
    def validate(self, data):
        """Validate invoice item data"""
        # Validate treatment plan item belongs to same patient as invoice
        treatment_plan_item = data.get('treatment_plan_item')
        invoice = data.get('invoice') or getattr(self.instance, 'invoice', None)
        
        if treatment_plan_item and invoice:
            if treatment_plan_item.treatment_plan.patient != invoice.patient:
                raise serializers.ValidationError({
                    'treatment_plan_item': 'Treatment plan item must belong to same patient as invoice'
                })
        
        # Validate doctor commission
        doctor = data.get('doctor')
        commission = data.get('doctor_commission_percentage', 0)
        
        if doctor and commission > 0:
            if not doctor.is_active:
                raise serializers.ValidationError({
                    'doctor': 'Doctor is not active'
                })
        
        return data


class InvoiceItemCreateSerializer(serializers.Serializer):
    """Serializer for creating invoice items"""
    
    item_type = serializers.ChoiceField(choices=InvoiceItem.ITEM_TYPE_CHOICES)
    description = serializers.CharField(max_length=500)
    code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    treatment_id = serializers.IntegerField(required=False, allow_null=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, default=1, min_value=0.01)
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, default=0, min_value=0, max_value=100)
    tax_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, default=18, min_value=0)
    doctor_id = serializers.IntegerField(required=False, allow_null=True)
    doctor_commission_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, default=0, min_value=0, max_value=100)
    is_taxable = serializers.BooleanField(default=True)
    hsn_code = serializers.CharField(required=False, allow_blank=True)


# ===========================================
# INVOICE SERIALIZERS
# ===========================================
class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer for Invoice"""
    
    patient = MinimalPatientSerializer(read_only=True)
    patient_id = serializers.PrimaryKeyRelatedField(
        queryset=Patient.objects.all(),
        write_only=True,
        source='patient'
    )
    
    branch = MinimalBranchSerializer(read_only=True)
    branch_id = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.filter(is_active=True),
        write_only=True,
        source='branch'
    )
    
    visit = MinimalVisitSerializer(read_only=True)
    visit_id = serializers.PrimaryKeyRelatedField(
        queryset=Visit.objects.all(),
        write_only=True,
        source='visit',
        required=False,
        allow_null=True
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
    items = InvoiceItemSerializer(many=True, read_only=True)
    applied_discounts = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    
    # Calculated fields
    balance_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_paid = serializers.BooleanField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    can_modify = serializers.BooleanField(read_only=True)
    total_doctor_commission = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'patient', 'patient_id', 'branch', 'branch_id',
            'visit', 'visit_id', 'invoice_date', 'due_date', 'status',
            'is_locked', 'is_final', 'subtotal', 'discount_percentage',
            'discount_amount', 'tax_percentage', 'tax_amount', 'total_amount',
            'paid_amount', 'advance_paid', 'balance_amount', 'late_fee_percentage',
            'late_fee_amount', 'insurance_claim_amount', 'insurance_claim_status',
            'payment_terms', 'payment_due_date', 'last_payment_date',
            'override_reason', 'override_by', 'referred_by', 'referred_by_id',
            'referral_commission', 'notes', 'internal_notes',
            'is_paid', 'is_overdue', 'can_modify', 'total_doctor_commission',
            'items', 'applied_discounts', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]
        read_only_fields = [
            'invoice_number', 'created_at', 'updated_at', 'created_by', 'updated_by',
            'discount_amount', 'tax_amount', 'total_amount', 'balance_amount',
            'is_locked', 'is_final', 'is_paid', 'is_overdue', 'can_modify',
            'total_doctor_commission'
        ]
    
    def validate(self, data):
        """Validate invoice data"""
        # Validate dates
        due_date = data.get('due_date')
        if due_date:
            from django.utils import timezone
            if due_date < timezone.now().date():
                raise serializers.ValidationError({
                    'due_date': 'Due date cannot be in the past'
                })
        
        # Validate insurance claim
        insurance_claim_amount = data.get('insurance_claim_amount', 0)
        total_amount = data.get('total_amount', 0)
        
        if insurance_claim_amount > total_amount:
            raise serializers.ValidationError({
                'insurance_claim_amount': 'Insurance claim cannot exceed total amount'
            })
        
        # Validate discount
        discount = data.get('discount_percentage', 0)
        if discount < 0 or discount > 100:
            raise serializers.ValidationError({
                'discount_percentage': 'Discount must be between 0 and 100'
            })
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """Create invoice with audit fields"""
        request = self.context.get('request')
        
        if request and request.user:
            validated_data['created_by'] = request.user
            validated_data['updated_by'] = request.user
        
        return super().create(validated_data)
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update invoice with audit fields"""
        request = self.context.get('request')
        
        if request and request.user:
            validated_data['updated_by'] = request.user
        
        return super().update(instance, validated_data)


class InvoiceCreateSerializer(serializers.Serializer):
    """Serializer for creating invoices with items"""
    
    patient_id = serializers.IntegerField(required=True)
    branch_id = serializers.IntegerField(required=True)
    visit_id = serializers.IntegerField(required=False, allow_null=True)
    payment_terms = serializers.ChoiceField(choices=Invoice.PAYMENT_TERMS, default='IMMEDIATE')
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, default=0, min_value=0, max_value=100)
    tax_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, default=18, min_value=0)
    notes = serializers.CharField(required=False, allow_blank=True)
    items = serializers.ListField(
        child=serializers.DictField(),
        required=True,
        help_text="List of invoice items"
    )
    
    def validate(self, data):
        """Validate invoice creation data"""
        # Validate patient exists
        try:
            patient = Patient.objects.get(id=data['patient_id'])
            data['patient'] = patient
        except Patient.DoesNotExist:
            raise serializers.ValidationError({'patient_id': 'Patient not found'})
        
        # Validate branch exists
        try:
            branch = Branch.objects.get(id=data['branch_id'])
            data['branch'] = branch
        except Branch.DoesNotExist:
            raise serializers.ValidationError({'branch_id': 'Branch not found'})
        
        # Validate visit exists if provided
        if data.get('visit_id'):
            try:
                visit = Visit.objects.get(id=data['visit_id'])
                data['visit'] = visit
            except Visit.DoesNotExist:
                raise serializers.ValidationError({'visit_id': 'Visit not found'})
        
        # Validate items
        for i, item in enumerate(data['items']):
            if item.get('treatment_id'):
                try:
                    Treatment.objects.get(id=item['treatment_id'])
                except Treatment.DoesNotExist:
                    raise serializers.ValidationError({
                        f'items[{i}].treatment_id': 'Treatment not found'
                    })
            
            if item.get('doctor_id'):
                try:
                    Doctor.objects.get(id=item['doctor_id'])
                except Doctor.DoesNotExist:
                    raise serializers.ValidationError({
                        f'items[{i}].doctor_id': 'Doctor not found'
                    })
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """Create invoice with items"""
        request = self.context.get('request')
        items_data = validated_data.pop('items')
        
        # Create invoice
        invoice = Invoice.objects.create(
            **validated_data,
            created_by=request.user if request else None,
            updated_by=request.user if request else None
        )
        
        # Create invoice items
        for item_data in items_data:
            treatment_id = item_data.pop('treatment_id', None)
            doctor_id = item_data.pop('doctor_id', None)
            
            item = InvoiceItem(
                invoice=invoice,
                **item_data
            )
            
            if treatment_id:
                item.treatment_id = treatment_id
            
            if doctor_id:
                item.doctor_id = doctor_id
            
            if request and request.user:
                item.created_by = request.user
                item.updated_by = request.user
            
            item.save()
        
        return invoice


# ===========================================
# DISCOUNT SERIALIZERS
# ===========================================
class DiscountPolicySerializer(serializers.ModelSerializer):
    """Serializer for DiscountPolicy"""
    
    is_applicable = serializers.BooleanField(read_only=True)
    usage_remaining = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = DiscountPolicy
        fields = [
            'id', 'name', 'code', 'discount_type', 'percentage',
            'fixed_amount', 'applicable_to', 'minimum_amount',
            'maximum_discount', 'valid_from', 'valid_until',
            'is_active', 'requires_approval', 'min_approval_level',
            'usage_limit', 'used_count', 'is_applicable', 'usage_remaining',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'used_count', 'created_at', 'updated_at', 'created_by', 'updated_by',
            'is_applicable', 'usage_remaining'
        ]
    
    def validate_code(self, value):
        """Ensure code is unique"""
        if self.instance and self.instance.code == value:
            return value
        
        if DiscountPolicy.objects.filter(code=value).exists():
            raise serializers.ValidationError("Discount code already exists")
        return value.upper()
    
    def validate(self, data):
        """Validate discount policy data"""
        discount_type = data.get('discount_type')
        percentage = data.get('percentage')
        fixed_amount = data.get('fixed_amount')
        
        if discount_type == 'PERCENTAGE' and not percentage:
            raise serializers.ValidationError({
                'percentage': 'Percentage is required for percentage discounts'
            })
        
        if discount_type == 'FIXED' and not fixed_amount:
            raise serializers.ValidationError({
                'fixed_amount': 'Fixed amount is required for fixed discounts'
            })
        
        # Validate dates
        valid_from = data.get('valid_from')
        valid_until = data.get('valid_until')
        
        if valid_from and valid_until and valid_from > valid_until:
            raise serializers.ValidationError({
                'valid_until': 'Valid until date must be after valid from date'
            })
        
        return data


class AppliedDiscountSerializer(serializers.ModelSerializer):
    """Serializer for AppliedDiscount"""
    
    invoice_details = InvoiceSerializer(source='invoice', read_only=True)
    discount_policy_details = DiscountPolicySerializer(source='discount_policy', read_only=True)
    approved_by_details = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    
    class Meta:
        model = AppliedDiscount
        fields = [
            'id', 'invoice', 'invoice_details', 'discount_policy',
            'discount_policy_details', 'discount_amount', 'original_amount',
            'approved_by', 'approved_by_details', 'approved_at',
            'approval_notes', 'is_reversed', 'reversed_by',
            'reversed_at', 'reversal_reason', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'approved_by_details'
        ]


# ===========================================
# ACTION SERIALIZERS
# ===========================================
class ApplyPaymentSerializer(serializers.Serializer):
    """Serializer for applying payment to invoice"""
    
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    payment_method = serializers.ChoiceField(choices=constants.PaymentModes.choices)
    notes = serializers.CharField(required=False, allow_blank=True)
    transaction_id = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate payment data"""
        view = self.context.get('view')
        if not view:
            return data
        
        invoice = view.get_object()
        
        # Check if invoice can accept payments
        if not invoice.can_modify:
            raise serializers.ValidationError("Invoice cannot accept payments")
        
        # Check EOD lock
        if invoice.branch.is_eod_locked:
            raise serializers.ValidationError("EOD locked: payments are closed")
        
        # Check amount doesn't exceed balance
        if data['amount'] > invoice.balance_amount:
            raise serializers.ValidationError({
                'amount': f'Payment amount ({data["amount"]}) exceeds balance ({invoice.balance_amount})'
            })
        
        return data


class VoidInvoiceSerializer(serializers.Serializer):
    """Serializer for voiding an invoice"""
    
    reason = serializers.CharField(max_length=500, required=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate void request"""
        view = self.context.get('view')
        if not view:
            return data
        
        invoice = view.get_object()
        
        if invoice.status in ['PAID', 'VOID', 'REFUNDED']:
            raise serializers.ValidationError("Cannot void paid or already void invoice")
        
        if not invoice.can_modify:
            raise serializers.ValidationError("Invoice cannot be modified")
        
        return data


class ApplyDiscountSerializer(serializers.Serializer):
    """Serializer for applying discount to invoice"""
    
    discount_policy_id = serializers.IntegerField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate discount application"""
        view = self.context.get('view')
        if not view:
            return data
        
        invoice = view.get_object()
        
        try:
            discount_policy = DiscountPolicy.objects.get(id=data['discount_policy_id'])
            data['discount_policy'] = discount_policy
        except DiscountPolicy.DoesNotExist:
            raise serializers.ValidationError({'discount_policy_id': 'Discount policy not found'})
        
        # Check if discount can be applied
        can_apply, message = discount_policy.can_apply(invoice.patient, view.request.user)
        if not can_apply:
            raise serializers.ValidationError({'discount_policy_id': message})
        
        # Check minimum amount
        if discount_policy.minimum_amount and invoice.subtotal < discount_policy.minimum_amount:
            raise serializers.ValidationError({
                'discount_policy_id': f'Minimum amount {discount_policy.minimum_amount} required'
            })
        
        return data