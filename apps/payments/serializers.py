from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal

from .models import (
    PaymentMethod, Payment, Refund, 
    PaymentReceipt, PaymentSplit
)
from apps.billing.models import Invoice
from apps.patients.models import Patient
from apps.doctors.models import Doctor
from apps.clinics.models import Branch, Counter
from apps.accounts.models import User
from core.constants import PaymentModes


# ===========================================
# UTILITY SERIALIZERS
# ===========================================
class MinimalPatientSerializer(serializers.ModelSerializer):
    """Minimal patient serializer"""
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = Patient
        fields = ['id', 'patient_id', 'full_name', 'gender', 'date_of_birth']


class MinimalInvoiceSerializer(serializers.ModelSerializer):
    """Minimal invoice serializer"""
    
    class Meta:
        model = Invoice
        fields = ['id', 'invoice_number', 'total_amount', 'paid_amount', 'balance_amount', 'status']


class MinimalBranchSerializer(serializers.ModelSerializer):
    """Minimal branch serializer"""
    
    class Meta:
        model = Branch
        fields = ['id', 'name', 'code', 'address']


class MinimalUserSerializer(serializers.ModelSerializer):
    """Minimal user serializer"""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']


# ===========================================
# PAYMENT METHOD SERIALIZERS
# ===========================================
class PaymentMethodSerializer(serializers.ModelSerializer):
    """Serializer for PaymentMethod"""
    
    class Meta:
        model = PaymentMethod
        fields = [
            'code', 'name', 'description', 'is_active',
            'requires_approval', 'approval_amount_limit',
            'requires_reference', 'sort_order', 'icon_class',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def validate_code(self, value):
        """Ensure code is unique"""
        if self.instance and self.instance.code == value:
            return value
        
        if PaymentMethod.objects.filter(code=value).exists():
            raise serializers.ValidationError("Payment method code already exists")
        return value.upper()


# ===========================================
# PAYMENT SERIALIZERS
# ===========================================
class PaymentSplitSerializer(serializers.ModelSerializer):
    """Serializer for PaymentSplit"""
    
    payment_method_details = PaymentMethodSerializer(source='payment_method', read_only=True)
    
    class Meta:
        model = PaymentSplit
        fields = [
            'id', 'payment', 'payment_method', 'payment_method_details',
            'amount', 'reference_number', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment"""
    
    # Related objects
    invoice = MinimalInvoiceSerializer(read_only=True)
    invoice_id = serializers.PrimaryKeyRelatedField(
        queryset=Invoice.objects.all(),
        write_only=True,
        source='invoice'
    )
    
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
    
    payment_method = PaymentMethodSerializer(read_only=True)
    payment_method_id = serializers.PrimaryKeyRelatedField(
        queryset=PaymentMethod.objects.filter(is_active=True),
        write_only=True,
        source='payment_method'
    )
    
    approved_by = MinimalUserSerializer(read_only=True)
    reconciled_by = MinimalUserSerializer(read_only=True)
    
    # Related fields
    splits = PaymentSplitSerializer(many=True, read_only=True)
    refunds = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    receipt_link = serializers.PrimaryKeyRelatedField(read_only=True)
    
    # Calculated fields
    refundable_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    can_refund = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'payment_number', 'invoice', 'invoice_id', 'patient', 'patient_id',
            'branch', 'branch_id', 'amount', 'payment_method', 'payment_method_id',
            'method_display', 'reference_number', 'card_last_four', 'card_type',
            'card_authorization_code', 'upi_id', 'upi_transaction_id', 'bank_name',
            'account_number', 'ifsc_code', 'cheque_number', 'cheque_date',
            'cheque_bank', 'insurance_provider', 'insurance_claim_id',
            'insurance_approval_code', 'status', 'payment_date', 'completed_at',
            'failed_at', 'failure_reason', 'requires_approval', 'approved_by',
            'approved_at', 'approval_notes', 'receipt_generated', 'receipt_number',
            'receipt_reprint_count', 'last_reprinted_at', 'last_reprinted_by',
            'reconciled', 'reconciled_at', 'reconciled_by', 'is_locked', 'counter',
            'notes', 'internal_notes', 'refundable_amount', 'can_refund',
            'splits', 'refunds', 'receipt_link', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]
        read_only_fields = [
            'payment_number', 'method_display', 'completed_at', 'failed_at',
            'approved_at', 'reconciled_at', 'last_reprinted_at', 'is_locked',
            'refundable_amount', 'can_refund', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]
    
    def validate(self, data):
        """Validate payment data"""
        invoice = data.get('invoice')
        amount = data.get('amount')
        payment_method = data.get('payment_method')
        
        if invoice and amount:
            # Check if payment amount exceeds invoice balance
            if amount > invoice.balance_amount:
                raise serializers.ValidationError({
                    'amount': f'Payment amount ({amount}) exceeds invoice balance ({invoice.balance_amount})'
                })
            
            # Check if invoice is payable
            if not invoice.can_modify:
                raise serializers.ValidationError({
                    'invoice': 'Invoice cannot accept payments'
                })
        
        if payment_method and payment_method.requires_reference:
            reference_number = data.get('reference_number', '')
            if not reference_number:
                raise serializers.ValidationError({
                    'reference_number': f'{payment_method.name} requires a reference number'
                })
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """Create payment with audit fields"""
        request = self.context.get('request')
        
        if request and request.user:
            validated_data['created_by'] = request.user
            validated_data['updated_by'] = request.user
            
            # Set requested_by for refunds if applicable
            if 'requested_by' not in validated_data and hasattr(self, 'initial_data'):
                if self.initial_data.get('refund'):
                    validated_data['requested_by'] = request.user
        
        payment = super().create(validated_data)
        
        # Mark as completed if no approval required
        if not payment.requires_approval:
            payment.status = Payment.COMPLETED
            payment.completed_at = timezone.now()
            payment.save()
        
        return payment


class PaymentCreateSerializer(serializers.Serializer):
    """Serializer for creating payments with splits"""
    
    invoice_id = serializers.IntegerField(required=True)
    payment_date = serializers.DateTimeField(default=timezone.now)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    # Single payment method
    payment_method_id = serializers.CharField(required=False)
    amount = serializers.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01')
    )
    reference_number = serializers.CharField(required=False, allow_blank=True)
    
    # Split payments
    splits = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        help_text="List of payment splits with payment_method_id, amount, reference_number"
    )
    
    def validate(self, data):
        """Validate payment creation data"""
        invoice_id = data.get('invoice_id')
        amount = data.get('amount')
        splits = data.get('splits')
        
        # Get invoice
        try:
            invoice = Invoice.objects.get(id=invoice_id)
            data['invoice'] = invoice
        except Invoice.DoesNotExist:
            raise serializers.ValidationError({'invoice_id': 'Invoice not found'})
        
        # Validate either single payment or splits
        if splits:
            if amount or data.get('payment_method_id'):
                raise serializers.ValidationError(
                    "Cannot specify both single payment and splits"
                )
            
            # Validate splits
            total_split_amount = Decimal('0')
            for i, split in enumerate(splits):
                split_amount = Decimal(str(split.get('amount', 0)))
                total_split_amount += split_amount
                
                # Validate payment method
                payment_method_id = split.get('payment_method_id')
                try:
                    PaymentMethod.objects.get(code=payment_method_id, is_active=True)
                except PaymentMethod.DoesNotExist:
                    raise serializers.ValidationError({
                        f'splits[{i}].payment_method_id': 'Invalid payment method'
                    })
            
            if total_split_amount > invoice.balance_amount:
                raise serializers.ValidationError({
                    'splits': f'Total split amount ({total_split_amount}) exceeds invoice balance ({invoice.balance_amount})'
                })
            
            data['total_amount'] = total_split_amount
        
        else:
            # Single payment validation
            if not amount:
                raise serializers.ValidationError({
                    'amount': 'Amount is required for single payment'
                })
            
            if not data.get('payment_method_id'):
                raise serializers.ValidationError({
                    'payment_method_id': 'Payment method is required for single payment'
                })
            
            if amount > invoice.balance_amount:
                raise serializers.ValidationError({
                    'amount': f'Amount ({amount}) exceeds invoice balance ({invoice.balance_amount})'
                })
            
            data['total_amount'] = amount
        
        # Check if invoice is payable
        if not invoice.can_modify:
            raise serializers.ValidationError({
                'invoice_id': 'Invoice cannot accept payments'
            })
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """Create payment with optional splits"""
        request = self.context.get('request')
        invoice = validated_data['invoice']
        splits = validated_data.get('splits')
        
        if splits:
            # Create main payment with first split's method
            first_split = splits[0]
            payment_method = PaymentMethod.objects.get(code=first_split['payment_method_id'])
            
            payment = Payment.objects.create(
                invoice=invoice,
                patient=invoice.patient,
                branch=invoice.branch,
                amount=validated_data['total_amount'],
                payment_method=payment_method,
                payment_date=validated_data.get('payment_date', timezone.now()),
                notes=validated_data.get('notes', ''),
                created_by=request.user if request else None,
                updated_by=request.user if request else None
            )
            
            # Create splits
            for split_data in splits:
                split_method = PaymentMethod.objects.get(code=split_data['payment_method_id'])
                PaymentSplit.objects.create(
                    payment=payment,
                    payment_method=split_method,
                    amount=Decimal(str(split_data['amount'])),
                    reference_number=split_data.get('reference_number', ''),
                    notes=split_data.get('notes', '')
                )
        else:
            # Single payment
            payment_method = PaymentMethod.objects.get(code=validated_data['payment_method_id'])
            
            payment = Payment.objects.create(
                invoice=invoice,
                patient=invoice.patient,
                branch=invoice.branch,
                amount=validated_data['amount'],
                payment_method=payment_method,
                reference_number=validated_data.get('reference_number', ''),
                payment_date=validated_data.get('payment_date', timezone.now()),
                notes=validated_data.get('notes', ''),
                created_by=request.user if request else None,
                updated_by=request.user if request else None
            )
        
        # Auto-complete if no approval needed
        if not payment.requires_approval:
            payment.status = Payment.COMPLETED
            payment.completed_at = timezone.now()
            payment.save()
        
        return payment


# ===========================================
# REFUND SERIALIZERS
# ===========================================
class RefundSerializer(serializers.ModelSerializer):
    """Serializer for Refund"""
    
    payment = PaymentSerializer(read_only=True)
    payment_id = serializers.PrimaryKeyRelatedField(
        queryset=Payment.objects.filter(status=Payment.COMPLETED),
        write_only=True,
        source='payment'
    )
    
    invoice = MinimalInvoiceSerializer(read_only=True)
    invoice_id = serializers.PrimaryKeyRelatedField(
        queryset=Invoice.objects.all(),
        write_only=True,
        source='invoice'
    )
    
    requested_by = MinimalUserSerializer(read_only=True)
    approved_by = MinimalUserSerializer(read_only=True)
    rejected_by = MinimalUserSerializer(read_only=True)
    completed_by = MinimalUserSerializer(read_only=True)
    
    class Meta:
        model = Refund
        fields = [
            'id', 'refund_number', 'payment', 'payment_id', 'invoice', 'invoice_id',
            'branch', 'amount', 'refund_method', 'status', 'requested_by',
            'requested_at', 'approved_by', 'approved_at', 'approval_notes',
            'rejected_by', 'rejected_at', 'rejection_reason', 'completed_by',
            'completed_at', 'reference_number', 'bank_name', 'account_number',
            'ifsc_code', 'cheque_number', 'cheque_date', 'credit_note_number',
            'credit_note_valid_until', 'reason', 'notes', 'is_locked',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'refund_number', 'status', 'requested_at', 'approved_at',
            'rejected_at', 'completed_at', 'is_locked', 'created_at',
            'updated_at', 'created_by', 'updated_by'
        ]
    
    def validate(self, data):
        """Validate refund data"""
        payment = data.get('payment')
        amount = data.get('amount')
        
        if payment and amount:
            # Check if payment can be refunded
            if not payment.can_refund:
                raise serializers.ValidationError({
                    'payment': 'Payment cannot be refunded'
                })
            
            # Check refund amount
            if amount > payment.refundable_amount:
                raise serializers.ValidationError({
                    'amount': f'Refund amount ({amount}) exceeds refundable amount ({payment.refundable_amount})'
                })
        
        return data


class RefundCreateSerializer(serializers.Serializer):
    """Serializer for creating refunds"""
    
    payment_id = serializers.IntegerField(required=True)
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.01')
    )
    refund_method = serializers.ChoiceField(choices=Refund.METHOD_CHOICES)
    reason = serializers.CharField(max_length=500, required=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    # Method-specific fields
    reference_number = serializers.CharField(required=False, allow_blank=True)
    bank_name = serializers.CharField(required=False, allow_blank=True)
    account_number = serializers.CharField(required=False, allow_blank=True)
    ifsc_code = serializers.CharField(required=False, allow_blank=True)
    cheque_number = serializers.CharField(required=False, allow_blank=True)
    cheque_date = serializers.DateField(required=False, allow_null=True)
    
    def validate(self, data):
        """Validate refund creation"""
        try:
            payment = Payment.objects.get(id=data['payment_id'])
            data['payment'] = payment
        except Payment.DoesNotExist:
            raise serializers.ValidationError({'payment_id': 'Payment not found'})
        
        # Validate payment can be refunded
        if not payment.can_refund:
            raise serializers.ValidationError({'payment_id': 'Payment cannot be refunded'})
        
        # Validate amount
        if data['amount'] > payment.refundable_amount:
            raise serializers.ValidationError({
                'amount': f'Amount ({data["amount"]}) exceeds refundable amount ({payment.refundable_amount})'
            })
        
        # Validate method-specific fields
        refund_method = data['refund_method']
        if refund_method == Refund.BANK_TRANSFER:
            if not data.get('bank_name') or not data.get('account_number') or not data.get('ifsc_code'):
                raise serializers.ValidationError({
                    'refund_method': 'Bank transfer requires bank name, account number, and IFSC code'
                })
        elif refund_method == Refund.CHEQUE:
            if not data.get('cheque_number') or not data.get('cheque_date'):
                raise serializers.ValidationError({
                    'refund_method': 'Cheque requires cheque number and date'
                })
        
        return data


# ===========================================
# RECEIPT SERIALIZERS
# ===========================================
class PaymentReceiptSerializer(serializers.ModelSerializer):
    """Serializer for PaymentReceipt"""
    
    payment = PaymentSerializer(read_only=True)
    generated_by = MinimalUserSerializer(read_only=True)
    original_receipt = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = PaymentReceipt
        fields = [
            'id', 'receipt_number', 'payment', 'branch', 'receipt_data',
            'html_template', 'generated_html', 'pdf_file', 'is_duplicate',
            'original_receipt', 'reprint_count', 'security_code', 'qr_code_data',
            'generated_by', 'generated_at', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]
        read_only_fields = [
            'receipt_number', 'security_code', 'generated_at', 'is_duplicate',
            'reprint_count', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]


class ReceiptGenerateSerializer(serializers.Serializer):
    """Serializer for generating receipts"""
    
    payment_id = serializers.IntegerField(required=True)
    template_type = serializers.ChoiceField(
        choices=[('STANDARD', 'Standard'), ('DETAILED', 'Detailed'), ('MINIMAL', 'Minimal')],
        default='STANDARD'
    )
    include_qr_code = serializers.BooleanField(default=True)
    generate_pdf = serializers.BooleanField(default=True)
    
    def validate(self, data):
        """Validate receipt generation"""
        try:
            payment = Payment.objects.get(id=data['payment_id'])
            data['payment'] = payment
        except Payment.DoesNotExist:
            raise serializers.ValidationError({'payment_id': 'Payment not found'})
        
        if payment.status != Payment.COMPLETED:
            raise serializers.ValidationError({'payment_id': 'Payment must be completed'})
        
        if payment.receipt_generated:
            raise serializers.ValidationError({'payment_id': 'Receipt already generated'})
        
        return data


# ===========================================
# ACTION SERIALIZERS
# ===========================================
class ApprovePaymentSerializer(serializers.Serializer):
    """Serializer for approving payments"""
    
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate approval"""
        view = self.context.get('view')
        if not view:
            return data
        
        payment = view.get_object()
        
        if payment.status != Payment.PENDING:
            raise serializers.ValidationError('Only pending payments can be approved')
        
        if not payment.requires_approval:
            raise serializers.ValidationError('Payment does not require approval')
        
        return data


class CompleteRefundSerializer(serializers.Serializer):
    """Serializer for completing refunds"""
    
    reference_number = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate refund completion"""
        view = self.context.get('view')
        if not view:
            return data
        
        refund = view.get_object()
        
        if refund.status != Refund.APPROVED:
            raise serializers.ValidationError('Only approved refunds can be completed')
        
        # Validate reference number for certain methods
        if refund.refund_method in [Refund.BANK_TRANSFER, Refund.CHEQUE, Refund.CARD_REVERSAL]:
            if not data.get('reference_number'):
                raise serializers.ValidationError({
                    'reference_number': f'Reference number is required for {refund.get_refund_method_display()}'
                })
        
        return data


class ReconcilePaymentSerializer(serializers.Serializer):
    """Serializer for reconciling payments"""
    
    reconciled = serializers.BooleanField(default=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Validate reconciliation"""
        view = self.context.get('view')
        if not view:
            return data
        
        payment = view.get_object()
        
        if payment.status != Payment.COMPLETED:
            raise serializers.ValidationError('Only completed payments can be reconciled')
        
        if payment.reconciled:
            raise serializers.ValidationError('Payment already reconciled')
        
        return data