# apps/eod/serializers.py

from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, date
from decimal import Decimal

from .models import (
    EodLock, DailySummary, CashReconciliation, EodException,
    BaseAppModel
)
from ..clinics.serializers import BranchSerializer
from ..accounts.serializers import UserSerializer
from core.permissions import IsClinicManager, IsCashier, IsSuperAdmin


class EodLockSerializer(serializers.ModelSerializer):
    """Serializer for EOD Lock model"""
    
    # Related field representations
    branch_details = BranchSerializer(source='branch', read_only=True)
    prepared_by_details = UserSerializer(source='prepared_by', read_only=True)
    reviewed_by_details = UserSerializer(source='reviewed_by', read_only=True)
    locked_by_details = UserSerializer(source='locked_by', read_only=True)
    reversed_by_details = UserSerializer(source='reversed_by', read_only=True)
    
    # Status tracking
    is_editable = serializers.SerializerMethodField()
    can_review = serializers.SerializerMethodField()
    can_lock = serializers.SerializerMethodField()
    can_reverse = serializers.SerializerMethodField()
    
    # Financial summaries as formatted strings
    total_invoice_amount_display = serializers.SerializerMethodField()
    total_payment_amount_display = serializers.SerializerMethodField()
    total_cash_collected_display = serializers.SerializerMethodField()
    net_cash_position_display = serializers.SerializerMethodField()
    cash_difference_display = serializers.SerializerMethodField()
    
    class Meta:
        model = EodLock
        fields = [
            # Core fields
            'id', 'lock_number', 'branch', 'branch_details',
            'lock_date', 'status',
            
            # Financial summaries
            'total_invoices', 'total_invoice_amount', 'total_invoice_amount_display',
            'total_payments', 'total_payment_amount', 'total_payment_amount_display',
            'total_refunds', 'total_refund_amount',
            'total_cash_collected', 'total_cash_collected_display',
            'total_cash_refunded', 'net_cash_position', 'net_cash_position_display',
            
            # Digital payments breakdown
            'card_collections', 'upi_collections', 'bank_transfers',
            'insurance_collections', 'cheque_collections',
            
            # Cash handling
            'opening_cash', 'expected_cash', 'actual_cash',
            'cash_difference', 'cash_difference_display',
            
            # Personnel
            'prepared_by', 'prepared_by_details', 'prepared_at',
            'reviewed_by', 'reviewed_by_details', 'reviewed_at', 'review_notes',
            'locked_by', 'locked_by_details', 'locked_at',
            'reversed_by', 'reversed_by_details', 'reversed_at', 'reversal_reason',
            
            # Verification flags
            'cash_verified', 'cash_verified_by', 'cash_verified_at',
            'digital_payments_verified', 'digital_verified_by', 'digital_verified_at',
            'invoices_verified', 'invoices_verified_by', 'invoices_verified_at',
            
            # Discrepancies
            'has_discrepancies', 'discrepancy_notes',
            'discrepancy_resolved', 'discrepancy_resolved_by', 'discrepancy_resolved_at',
            'resolution_notes',
            
            # Counter
            'front_desk_counter',
            
            # Status flags
            'is_editable', 'can_review', 'can_lock', 'can_reverse',
            
            # Meta
            'notes', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'lock_number', 'total_invoices', 'total_invoice_amount',
            'total_payments', 'total_payment_amount', 'total_refunds',
            'total_refund_amount', 'total_cash_collected', 'total_cash_refunded',
            'net_cash_position', 'card_collections', 'upi_collections',
            'bank_transfers', 'insurance_collections', 'cheque_collections',
            'prepared_at', 'reviewed_at', 'locked_at', 'reversed_at',
            'cash_verified_at', 'digital_verified_at', 'invoices_verified_at',
            'discrepancy_resolved_at', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'branch': {'write_only': True},
            'prepared_by': {'write_only': True},
            'reviewed_by': {'write_only': True},
            'locked_by': {'write_only': True},
            'reversed_by': {'write_only': True},
        }
        validators = [
            UniqueTogetherValidator(
                queryset=EodLock.objects.all(),
                fields=['lock_date', 'branch'],
                message="EOD already exists for this date and branch"
            )
        ]
    
    def get_is_editable(self, obj):
        """Check if EOD is editable based on status"""
        return obj.status in [EodLock.PREPARED, EodLock.REVIEWED]
    
    def get_can_review(self, obj):
        """Check if current user can review this EOD"""
        request = self.context.get('request')
        if not request or not request.user:
            return False
        
        user = request.user
        return (obj.status == EodLock.PREPARED and 
                user.role in [IsClinicManager, IsSuperAdmin])
    
    def get_can_lock(self, obj):
        """Check if current user can lock this EOD"""
        request = self.context.get('request')
        if not request or not request.user:
            return False
        
        user = request.user
        return (obj.status == EodLock.REVIEWED and 
                user.role in [IsClinicManager, IsSuperAdmin])
    
    def get_can_reverse(self, obj):
        """Check if current user can reverse this EOD"""
        request = self.context.get('request')
        if not request or not request.user:
            return False
        
        user = request.user
        return (obj.status == EodLock.LOCKED and 
                user.role == IsSuperAdmin)  # Only super admin can reverse
    
    def get_total_invoice_amount_display(self, obj):
        return f"₹{obj.total_invoice_amount:,.2f}"
    
    def get_total_payment_amount_display(self, obj):
        return f"₹{obj.total_payment_amount:,.2f}"
    
    def get_total_cash_collected_display(self, obj):
        return f"₹{obj.total_cash_collected:,.2f}"
    
    def get_net_cash_position_display(self, obj):
        return f"₹{obj.net_cash_position:,.2f}"
    
    def get_cash_difference_display(self, obj):
        if obj.cash_difference is None:
            return "Not counted"
        sign = "+" if obj.cash_difference >= 0 else ""
        return f"₹{sign}{obj.cash_difference:,.2f}"
    
    def validate(self, data):
        """Validate EOD data"""
        request = self.context.get('request')
        
        # Prevent modification of locked EODs
        if self.instance and self.instance.status == EodLock.LOCKED:
            raise serializers.ValidationError("Cannot modify a locked EOD")
        
        # Validate lock date is not in future
        lock_date = data.get('lock_date', getattr(self.instance, 'lock_date', None))
        if lock_date and lock_date > timezone.now().date():
            raise serializers.ValidationError({
                'lock_date': 'Cannot create EOD for future date'
            })
        
        # Validate status transitions
        if self.instance and 'status' in data:
            current_status = self.instance.status
            new_status = data['status']
            
            valid_transitions = {
                EodLock.PREPARED: [EodLock.REVIEWED],
                EodLock.REVIEWED: [EodLock.LOCKED, EodLock.PREPARED],
                EodLock.LOCKED: [EodLock.REVERSED],
                EodLock.REVERSED: []
            }
            
            if new_status not in valid_transitions.get(current_status, []):
                raise serializers.ValidationError({
                    'status': f'Invalid transition from {current_status} to {new_status}'
                })
        
        return data
    
    def create(self, validated_data):
        """Create EOD with calculated totals"""
        request = self.context.get('request')
        validated_data['created_by'] = request.user
        validated_data['prepared_by'] = request.user
        
        # Auto-calculate totals on save
        eod = super().create(validated_data)
        eod.calculate_totals()
        
        return eod


class EodLockCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for EOD creation"""
    
    class Meta:
        model = EodLock
        fields = ['branch', 'lock_date', 'opening_cash', 'notes']
        read_only_fields = []
    
    def validate(self, data):
        """Validate EOD creation"""
        branch = data.get('branch')
        lock_date = data.get('lock_date')
        
        # Check if date is already locked
        if EodLock.objects.filter(branch=branch, lock_date=lock_date).exists():
            raise serializers.ValidationError(
                f"EOD already exists for {lock_date} at {branch.name}"
            )
        
        # Check if previous day is locked (business rule)
        previous_day = lock_date - timezone.timedelta(days=1)
        if not EodLock.objects.filter(branch=branch, lock_date=previous_day, status=EodLock.LOCKED).exists():
            # This is a warning, not an error
            data['_warning'] = f"Previous day ({previous_day}) is not locked"
        
        return data


class EodLockReviewSerializer(serializers.Serializer):
    """Serializer for reviewing EOD"""
    review_notes = serializers.CharField(required=False, allow_blank=True)
    cash_verified = serializers.BooleanField(default=False)
    actual_cash = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    
    def validate_actual_cash(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Actual cash cannot be negative")
        return value


class EodLockReverseSerializer(serializers.Serializer):
    """Serializer for reversing EOD"""
    reversal_reason = serializers.CharField(required=True, min_length=10)
    require_password = serializers.BooleanField(default=True)
    password = serializers.CharField(write_only=True, required=False)
    
    def validate(self, data):
        request = self.context.get('request')
        
        # Validate password if required
        if data.get('require_password') and not data.get('password'):
            raise serializers.ValidationError({
                'password': 'Password is required for EOD reversal'
            })
        
        if data.get('password') and not request.user.check_password(data['password']):
            raise serializers.ValidationError({
                'password': 'Incorrect password'
            })
        
        return data


class DailySummarySerializer(serializers.ModelSerializer):
    """Serializer for Daily Summary"""
    
    branch_details = BranchSerializer(source='branch', read_only=True)
    generated_by_details = UserSerializer(source='generated_by', read_only=True)
    eod_lock_details = EodLockSerializer(source='eod_lock', read_only=True)
    
    # Formatted amounts
    invoices_amount_display = serializers.SerializerMethodField()
    payments_amount_display = serializers.SerializerMethodField()
    refunds_amount_display = serializers.SerializerMethodField()
    
    # Time period display
    period_display = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    
    class Meta:
        model = DailySummary
        fields = [
            # Core fields
            'id', 'summary_number', 'branch', 'branch_details',
            'summary_date', 'summary_type', 'custom_name',
            
            # Time period
            'period_start', 'period_end', 'period_display', 'duration_display',
            
            # Financial summary
            'invoices_count', 'invoices_amount', 'invoices_amount_display',
            'payments_count', 'payments_amount', 'payments_amount_display',
            'refunds_count', 'refunds_amount', 'refunds_amount_display',
            
            # Appointment summary
            'appointments_total', 'appointments_completed',
            'appointments_cancelled', 'appointments_no_show',
            
            # Patient summary
            'new_patients', 'returning_patients',
            
            # Doctor summary
            'doctors_active', 'doctor_utilization',
            
            # Detailed data
            'invoice_details', 'payment_details', 'appointment_details',
            
            # Related EOD
            'eod_lock', 'eod_lock_details',
            
            # Generation info
            'generated_by', 'generated_by_details', 'generated_at',
            
            # Meta
            'notes', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'summary_number', 'invoices_count', 'invoices_amount',
            'payments_count', 'payments_amount', 'refunds_count', 'refunds_amount',
            'appointments_total', 'appointments_completed', 'appointments_cancelled',
            'appointments_no_show', 'new_patients', 'returning_patients',
            'doctors_active', 'doctor_utilization', 'generated_at'
        ]
    
    def get_invoices_amount_display(self, obj):
        return f"₹{obj.invoices_amount:,.2f}"
    
    def get_payments_amount_display(self, obj):
        return f"₹{obj.payments_amount:,.2f}"
    
    def get_refunds_amount_display(self, obj):
        return f"₹{obj.refunds_amount:,.2f}"
    
    def get_period_display(self, obj):
        return f"{obj.period_start.strftime('%I:%M %p')} - {obj.period_end.strftime('%I:%M %p')}"
    
    def get_duration_display(self, obj):
        duration = obj.period_end - obj.period_start
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        return f"{hours}h {minutes}m"


class DailySummaryCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Daily Summary"""
    
    class Meta:
        model = DailySummary
        fields = [
            'branch', 'summary_date', 'summary_type', 'custom_name',
            'period_start', 'period_end', 'notes'
        ]
    
    def validate(self, data):
        """Validate summary creation"""
        period_start = data.get('period_start')
        period_end = data.get('period_end')
        
        if period_start >= period_end:
            raise serializers.ValidationError({
                'period_end': 'End time must be after start time'
            })
        
        # Check if summary for this period already exists
        if DailySummary.objects.filter(
            branch=data.get('branch'),
            summary_date=data.get('summary_date'),
            summary_type=data.get('summary_type'),
            period_start__gte=period_start,
            period_end__lte=period_end
        ).exists():
            raise serializers.ValidationError(
                "Summary already exists for this period"
            )
        
        return data
    
    def create(self, validated_data):
        """Create summary with generated data"""
        request = self.context.get('request')
        validated_data['generated_by'] = request.user
        validated_data['created_by'] = request.user
        
        # Generate summary using service
        from .services import DailySummary
        summary = DailySummary.generate_summary(
            branch=validated_data['branch'],
            summary_type=validated_data['summary_type'],
            period_start=validated_data['period_start'],
            period_end=validated_data['period_end'],
            generated_by=request.user,
            custom_name=validated_data.get('custom_name', '')
        )
        
        return summary


class CashReconciliationSerializer(serializers.ModelSerializer):
    """Serializer for Cash Reconciliation"""
    
    branch_details = BranchSerializer(source='branch', read_only=True)
    cashier_details = UserSerializer(source='cashier', read_only=True)
    supervisor_details = UserSerializer(source='supervisor', read_only=True)
    counter_details = serializers.SerializerMethodField()
    eod_lock_details = EodLockSerializer(source='eod_lock', read_only=True)
    
    # Formatted amounts
    declared_cash_display = serializers.SerializerMethodField()
    counted_cash_display = serializers.SerializerMethodField()
    difference_display = serializers.SerializerMethodField()
    
    # Denomination breakdown
    denomination_total = serializers.SerializerMethodField()
    
    # Status flags
    is_verified = serializers.BooleanField(source='verified', read_only=True)
    can_verify = serializers.SerializerMethodField()
    
    class Meta:
        model = CashReconciliation
        fields = [
            # Core fields
            'id', 'reconciliation_number', 'branch', 'branch_details',
            'reconciliation_date', 'reconciliation_type',
            
            # Cash amounts
            'declared_cash', 'declared_cash_display',
            'counted_cash', 'counted_cash_display',
            'difference', 'difference_display',
            
            # Denomination breakdown
            'denomination_breakdown', 'denomination_total',
            
            # Personnel
            'cashier', 'cashier_details',
            'counter', 'counter_details',
            'supervisor', 'supervisor_details', 'supervised_at',
            
            # Status
            'verified', 'is_verified', 'verification_notes',
            'can_verify',
            
            # Related EOD
            'eod_lock', 'eod_lock_details',
            
            # Attachments
            'cash_count_image', 'signature_image',
            
            # Meta
            'notes', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'reconciliation_number', 'difference', 'supervised_at',
            'created_at', 'updated_at'
        ]
    
    def get_counter_details(self, obj):
        from ..clinics.serializers import CounterSerializer
        return CounterSerializer(obj.counter).data if obj.counter else None
    
    def get_declared_cash_display(self, obj):
        return f"₹{obj.declared_cash:,.2f}"
    
    def get_counted_cash_display(self, obj):
        if obj.counted_cash is None:
            return "Not counted"
        return f"₹{obj.counted_cash:,.2f}"
    
    def get_difference_display(self, obj):
        if obj.difference is None:
            return "N/A"
        sign = "+" if obj.difference >= 0 else ""
        return f"₹{sign}{obj.difference:,.2f}"
    
    def get_denomination_total(self, obj):
        return obj.get_denomination_total()
    
    def get_can_verify(self, obj):
        """Check if current user can verify this reconciliation"""
        request = self.context.get('request')
        if not request or not request.user:
            return False
        
        user = request.user
        return (not obj.verified and 
                user.role in ['clinic_manager', 'super_admin'] and
                user != obj.cashier)  # Cannot verify own reconciliation
    
    def validate(self, data):
        """Validate reconciliation data"""
        # Validate cash amounts
        declared_cash = data.get('declared_cash', getattr(self.instance, 'declared_cash', 0))
        if declared_cash < 0:
            raise serializers.ValidationError({
                'declared_cash': 'Declared cash cannot be negative'
            })
        
        # Validate counter belongs to branch
        counter = data.get('counter')
        branch = data.get('branch', getattr(self.instance, 'branch', None))
        
        if counter and branch and counter.branch != branch:
            raise serializers.ValidationError({
                'counter': 'Counter does not belong to this branch'
            })
        
        return data


class CashReconciliationVerifySerializer(serializers.Serializer):
    """Serializer for verifying cash reconciliation"""
    counted_cash = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=True
    )
    denomination_breakdown = serializers.DictField(
        child=serializers.IntegerField(min_value=0),
        required=False
    )
    verification_notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_counted_cash(self, value):
        if value < 0:
            raise serializers.ValidationError("Counted cash cannot be negative")
        return value
    
    def validate_denomination_breakdown(self, value):
        if value:
            total = sum(
                Decimal(denom) * count 
                for denom, count in value.items()
                if self._is_valid_denomination(denom)
            )
            return value
        return value
    
    def _is_valid_denomination(self, denomination):
        """Validate denomination format"""
        try:
            value = Decimal(denomination)
            return value > 0
        except:
            return False


class EodExceptionSerializer(serializers.ModelSerializer):
    """Serializer for EOD Exceptions"""
    
    branch_details = BranchSerializer(source='branch', read_only=True)
    assigned_to_details = UserSerializer(source='assigned_to', read_only=True)
    resolved_by_details = UserSerializer(source='resolved_by', read_only=True)
    eod_lock_details = EodLockSerializer(source='eod_lock', read_only=True)
    
    # Related record details
    related_invoice_details = serializers.SerializerMethodField()
    related_payment_details = serializers.SerializerMethodField()
    related_refund_details = serializers.SerializerMethodField()
    
    # Status tracking
    is_overdue = serializers.SerializerMethodField()
    days_open = serializers.SerializerMethodField()
    can_assign = serializers.SerializerMethodField()
    can_resolve = serializers.SerializerMethodField()
    
    # Formatted amount
    amount_involved_display = serializers.SerializerMethodField()
    
    class Meta:
        model = EodException
        fields = [
            # Core fields
            'id', 'exception_number', 'branch', 'branch_details',
            'exception_date', 'exception_type', 'severity',
            
            # Description
            'title', 'description',
            
            # Amount involved
            'amount_involved', 'amount_involved_display',
            
            # Related records
            'related_invoice', 'related_invoice_details',
            'related_payment', 'related_payment_details',
            'related_refund', 'related_refund_details',
            
            # Status tracking
            'status', 'is_overdue', 'days_open',
            
            # Assignment
            'assigned_to', 'assigned_to_details', 'assigned_at',
            
            # Resolution
            'resolved_by', 'resolved_by_details', 'resolved_at',
            'resolution_notes', 'resolution_action',
            
            # Related EOD
            'eod_lock', 'eod_lock_details',
            
            # Permissions
            'can_assign', 'can_resolve',
            
            # Attachments
            'attachment',
            
            # Meta
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'exception_number', 'assigned_at', 'resolved_at',
            'created_at', 'updated_at'
        ]
    
    def get_related_invoice_details(self, obj):
        from ..billing.serializers import InvoiceSerializer
        return InvoiceSerializer(obj.related_invoice).data if obj.related_invoice else None
    
    def get_related_payment_details(self, obj):
        from ..payments.serializers import PaymentSerializer
        return PaymentSerializer(obj.related_payment).data if obj.related_payment else None
    
    def get_related_refund_details(self, obj):
        from ..payments.serializers import RefundSerializer
        return RefundSerializer(obj.related_refund).data if obj.related_refund else None
    
    def get_is_overdue(self, obj):
        """Check if exception is overdue (open for > 7 days)"""
        if obj.status not in [EodException.OPEN, EodException.IN_PROGRESS]:
            return False
        
        days_open = (timezone.now().date() - obj.exception_date).days
        return days_open > 7
    
    def get_days_open(self, obj):
        """Get number of days exception has been open"""
        if obj.status in [EodException.RESOLVED, EodException.CANCELLED]:
            if obj.resolved_at:
                return (obj.resolved_at.date() - obj.exception_date).days
            return 0
        
        return (timezone.now().date() - obj.exception_date).days
    
    def get_can_assign(self, obj):
        """Check if current user can assign this exception"""
        request = self.context.get('request')
        if not request or not request.user:
            return False
        
        user = request.user
        return (obj.status == EodException.OPEN and 
                user.role in ['clinic_manager', 'super_admin'])
    
    def get_can_resolve(self, obj):
        """Check if current user can resolve this exception"""
        request = self.context.get('request')
        if not request or not request.user:
            return False
        
        user = request.user
        return (obj.status in [EodException.OPEN, EodException.IN_PROGRESS] and
                (user == obj.assigned_to or 
                 user.role in ['clinic_manager', 'super_admin']))
    
    def get_amount_involved_display(self, obj):
        if obj.amount_involved is None:
            return "N/A"
        return f"₹{obj.amount_involved:,.2f}"
    
    def validate(self, data):
        """Validate exception data"""
        # Validate that at least one related record is provided if amount is involved
        amount_involved = data.get('amount_involved')
        related_invoice = data.get('related_invoice')
        related_payment = data.get('related_payment')
        related_refund = data.get('related_refund')
        
        if amount_involved and not any([related_invoice, related_payment, related_refund]):
            raise serializers.ValidationError(
                "At least one related record must be provided when amount is involved"
            )
        
        return data


class EodExceptionAssignSerializer(serializers.Serializer):
    """Serializer for assigning exceptions"""
    assigned_to_id = serializers.UUIDField(required=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_assigned_to_id(self, value):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            user = User.objects.get(id=value)
            if user.role == 'patient':  # Patients cannot be assigned exceptions
                raise serializers.ValidationError("Cannot assign to patient")
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")


class EodExceptionResolveSerializer(serializers.Serializer):
    """Serializer for resolving exceptions"""
    resolution_notes = serializers.CharField(required=True, min_length=10)
    resolution_action = serializers.CharField(required=False, allow_blank=True)
    requires_approval = serializers.BooleanField(default=False)
    approval_notes = serializers.CharField(required=False, allow_blank=True)


class EodReportSerializer(serializers.Serializer):
    """Serializer for EOD reports"""
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    report_type = serializers.ChoiceField(
        choices=['daily', 'weekly', 'monthly', 'custom'],
        default='daily'
    )
    include_summaries = serializers.BooleanField(default=True)
    include_exceptions = serializers.BooleanField(default=False)
    format = serializers.ChoiceField(
        choices=['json', 'csv', 'pdf', 'excel'],
        default='json'
    )
    
    def validate(self, data):
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date > end_date:
            raise serializers.ValidationError({
                'start_date': 'Start date cannot be after end date'
            })
        
        # Limit report range to 90 days
        if (end_date - start_date).days > 90:
            raise serializers.ValidationError({
                'end_date': 'Report range cannot exceed 90 days'
            })
        
        return data


class CashPositionSerializer(serializers.Serializer):
    """Serializer for cash position"""
    as_of_date = serializers.DateField(default=timezone.now().date)
    include_details = serializers.BooleanField(default=False)
    
    def validate_as_of_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError("Cannot get cash position for future date")
        return value


class DateLockStatusSerializer(serializers.Serializer):
    """Serializer for checking date lock status"""
    check_date = serializers.DateField(required=True)
    transaction_type = serializers.ChoiceField(
        choices=['invoice', 'payment', 'refund', 'any'],
        default='any'
    )
    
    def validate_check_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError("Cannot check status for future date")
        return value