# from django.db import models

# class Payment(models.Model):
#     branch = models.ForeignKey("clinics.Branch", on_delete=models.PROTECT)
#     invoice = models.ForeignKey("billing.Invoice", on_delete=models.PROTECT)

#     amount = models.DecimalField(max_digits=10, decimal_places=2)
#     method = models.CharField(
#         max_length=20,
#         choices=[
#             ("cash", "Cash"),
#             ("card", "Card"),
#             ("mobile", "Mobile"),
#         ]
#     )

#     received_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
#     received_at = models.DateTimeField(auto_now_add=True)

#     is_refund = models.BooleanField(default=False)





# apps/payments/models.py
from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import uuid

# Import from your actual structure - these should be in your core app mixins
from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.branch_querystd import BranchScopedMixin
from core.mixins.soft_delete import SoftDeleteMixin

# Import from other apps
from apps.billing.models import Invoice
from apps.clinics.models import Branch
from apps.accounts.models import User
from apps.patients.models import Patient

User = get_user_model()


# First, let me check what base models you actually have
# Based on your previous apps, you likely have these base classes:

class BaseModel(models.Model):
    """Base model with common fields"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


# Now let's create the payments models using your actual mixins
# Since I don't know the exact implementation of your mixins, I'll create a combined version:

class AuditableModel(models.Model):
    """Audit fields mixin"""
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, editable=False,
        related_name='created_%(class)s'
    )
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, editable=False,
        related_name='updated_%(class)s'
    )
    
    class Meta:
        abstract = True


class BranchScopedModel(models.Model):
    """Branch scoping mixin"""
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    
    class Meta:
        abstract = True


class BaseAppModel(BaseModel, AuditableModel, BranchScopedModel):
    """Combined base model for all apps"""
    class Meta:
        abstract = True


# Now let's update the PaymentMethod model first
class PaymentMethod(models.Model):
    """System-wide payment methods configuration"""
    CASH = 'CASH'
    CARD = 'CARD'
    UPI = 'UPI'
    BANK_TRANSFER = 'BANK_TRANSFER'
    INSURANCE = 'INSURANCE'
    CHEQUE = 'CHEQUE'
    PAYMENT_PLAN = 'PAYMENT_PLAN'
    
    METHOD_CHOICES = [
        (CASH, 'Cash'),
        (CARD, 'Credit/Debit Card'),
        (UPI, 'UPI'),
        (BANK_TRANSFER, 'Bank Transfer'),
        (INSURANCE, 'Insurance'),
        (CHEQUE, 'Cheque'),
        (PAYMENT_PLAN, 'Payment Plan'),
    ]
    
    code = models.CharField(max_length=20, primary_key=True)
    name = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=False)
    approval_amount_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Amount above which manager approval is required"
    )
    requires_reference = models.BooleanField(
        default=False,
        help_text="Whether this method requires reference number"
    )
    sort_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = "Payment Method"
        verbose_name_plural = "Payment Methods"
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return self.name


class Payment(BaseAppModel):
    """Main payment model with comprehensive tracking"""
    # Payment Statuses
    PENDING = 'PENDING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    REFUNDED = 'REFUNDED'
    PARTIALLY_REFUNDED = 'PARTIALLY_REFUNDED'
    
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (COMPLETED, 'Completed'),
        (FAILED, 'Failed'),
        (REFUNDED, 'Refunded'),
        (PARTIALLY_REFUNDED, 'Partially Refunded'),
    ]
    
    # Core fields
    payment_number = models.CharField(
        max_length=20, unique=True,
        help_text="Auto-generated payment number: PAY-YYYYMMDD-XXXXX"
    )
    invoice = models.ForeignKey(
        Invoice, on_delete=models.PROTECT,
        related_name='payments',
        help_text="Invoice being paid"
    )
    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT,
        related_name='payments'
    )
    
    # Amount and method
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    payment_method = models.ForeignKey(
        PaymentMethod, on_delete=models.PROTECT,
        related_name='payments'
    )
    method_display = models.CharField(
        max_length=50,
        help_text="Snapshot of payment method name at time of payment"
    )
    
    # Reference and details
    reference_number = models.CharField(
        max_length=100, blank=True,
        help_text="Transaction ID, cheque number, UPI reference, etc."
    )
    card_last_four = models.CharField(max_length=4, blank=True)
    card_type = models.CharField(max_length=20, blank=True)
    upi_id = models.EmailField(blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    cheque_number = models.CharField(max_length=50, blank=True)
    
    # Insurance specific
    insurance_provider = models.CharField(max_length=100, blank=True)
    insurance_claim_id = models.CharField(max_length=100, blank=True)
    
    # Status and timing
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=PENDING
    )
    payment_date = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    
    # Approval tracking
    requires_approval = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_payments'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    
    # Receipt control
    receipt_generated = models.BooleanField(default=False)
    receipt_number = models.CharField(max_length=20, blank=True)
    receipt_reprint_count = models.PositiveIntegerField(default=0)
    last_reprinted_at = models.DateTimeField(null=True, blank=True)
    last_reprinted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reprinted_receipts'
    )
    
    # Reconciliation
    reconciled = models.BooleanField(default=False)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reconciled_payments'
    )
    
    # EOD locking
    eod_locked = models.BooleanField(default=False)
    locked_eod_id = models.CharField(max_length=50, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ['-payment_date', '-created_at']
        indexes = [
            models.Index(fields=['payment_number']),
            models.Index(fields=['invoice', 'status']),
            models.Index(fields=['patient', 'payment_date']),
            models.Index(fields=['payment_date', 'branch']),
            models.Index(fields=['status', 'eod_locked']),
        ]
    
    def __str__(self):
        return f"{self.payment_number} - {self.patient} - {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.payment_number:
            self.payment_number = self.generate_payment_number()
        if not self.method_display and self.payment_method:
            self.method_display = self.payment_method.name
        super().save(*args, **kwargs)
    
    def generate_payment_number(self):
        """Generate unique payment number: PAY-YYYYMMDD-XXXXX"""
        date_str = timezone.now().strftime('%Y%m%d')
        last_payment = Payment.objects.filter(
            payment_number__startswith=f'PAY-{date_str}-'
        ).order_by('payment_number').last()
        
        if last_payment:
            last_num = int(last_payment.payment_number[-5:])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f"PAY-{date_str}-{new_num:05d}"
    
    def mark_completed(self, user):
        """Mark payment as completed"""
        self.status = self.COMPLETED
        self.completed_at = timezone.now()
        self.save()
        # Update invoice payment status
        self.invoice.update_payment_status()
    
    def can_refund(self):
        """Check if payment can be refunded"""
        return (
            self.status == self.COMPLETED and
            not self.eod_locked and
            not self.refunds.filter(status=Refund.APPROVED).exists()
        )
    
    def get_refundable_amount(self):
        """Calculate remaining refundable amount"""
        from django.db.models import Sum
        total_refunded = self.refunds.filter(
            status__in=[Refund.APPROVED, Refund.COMPLETED]
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        return max(self.amount - total_refunded, Decimal('0'))


class Refund(BaseAppModel):
    """Refund model with approval workflow"""
    # Refund Statuses
    REQUESTED = 'REQUESTED'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'
    
    STATUS_CHOICES = [
        (REQUESTED, 'Requested'),
        (APPROVED, 'Approved by Manager'),
        (REJECTED, 'Rejected'),
        (COMPLETED, 'Completed'),
        (CANCELLED, 'Cancelled'),
    ]
    
    # Refund Methods
    CASH = 'CASH'
    CARD_REVERSAL = 'CARD_REVERSAL'
    BANK_TRANSFER = 'BANK_TRANSFER'
    CHEQUE = 'CHEQUE'
    CREDIT_NOTE = 'CREDIT_NOTE'
    
    METHOD_CHOICES = [
        (CASH, 'Cash'),
        (CARD_REVERSAL, 'Card Reversal'),
        (BANK_TRANSFER, 'Bank Transfer'),
        (CHEQUE, 'Cheque'),
        (CREDIT_NOTE, 'Credit Note'),
    ]
    
    # Core fields
    refund_number = models.CharField(
        max_length=20, unique=True,
        help_text="Auto-generated refund number: REF-YYYYMMDD-XXXXX"
    )
    payment = models.ForeignKey(
        Payment, on_delete=models.PROTECT,
        related_name='refunds'
    )
    invoice = models.ForeignKey(
        Invoice, on_delete=models.PROTECT,
        related_name='refunds'
    )
    
    # Amount and method
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    refund_method = models.CharField(
        max_length=20, choices=METHOD_CHOICES
    )
    
    # Status and workflow
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=REQUESTED
    )
    requested_by = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='requested_refunds'
    )
    requested_at = models.DateTimeField(default=timezone.now)
    
    # Approval tracking
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_refunds'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    
    # Rejection tracking
    rejected_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rejected_refunds'
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Completion
    completed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='completed_refunds'
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Reference and details
    reference_number = models.CharField(max_length=100, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)
    cheque_number = models.CharField(max_length=50, blank=True)
    
    # Credit Note
    credit_note_number = models.CharField(max_length=50, blank=True)
    credit_note_valid_until = models.DateField(null=True, blank=True)
    
    # Reason and notes
    reason = models.TextField(help_text="Reason for refund")
    notes = models.TextField(blank=True)
    
    # EOD locking
    eod_locked = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Refund"
        verbose_name_plural = "Refunds"
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['refund_number']),
            models.Index(fields=['payment', 'status']),
            models.Index(fields=['status', 'requested_at']),
        ]
    
    def __str__(self):
        return f"{self.refund_number} - {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.refund_number:
            self.refund_number = self.generate_refund_number()
        super().save(*args, **kwargs)
    
    def generate_refund_number(self):
        """Generate unique refund number: REF-YYYYMMDD-XXXXX"""
        date_str = timezone.now().strftime('%Y%m%d')
        last_refund = Refund.objects.filter(
            refund_number__startswith=f'REF-{date_str}-'
        ).order_by('refund_number').last()
        
        if last_refund:
            last_num = int(last_refund.refund_number[-5:])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f"REF-{date_str}-{new_num:05d}"
    
    def approve(self, user, notes=""):
        """Approve refund request"""
        self.status = self.APPROVED
        self.approved_by = user
        self.approved_at = timezone.now()
        self.approval_notes = notes
        self.save()
    
    def reject(self, user, reason):
        """Reject refund request"""
        self.status = self.REJECTED
        self.rejected_by = user
        self.rejected_at = timezone.now()
        self.rejection_reason = reason
        self.save()
    
    def complete(self, user):
        """Mark refund as completed"""
        self.status = self.COMPLETED
        self.completed_by = user
        self.completed_at = timezone.now()
        self.save()
        
        # Update payment status if fully refunded
        refundable_amount = self.payment.get_refundable_amount()
        if refundable_amount <= Decimal('0'):
            if self.payment.amount == self.amount:
                self.payment.status = Payment.REFUNDED
            else:
                self.payment.status = Payment.PARTIALLY_REFUNDED
            self.payment.save()


class PaymentReceipt(BaseAppModel):
    """Receipt management with duplicate prevention"""
    receipt_number = models.CharField(max_length=20, unique=True)
    payment = models.OneToOneField(
        Payment, on_delete=models.PROTECT,
        related_name='receipt'
    )
    
    # Content
    receipt_data = models.JSONField(
        help_text="Structured receipt data for rendering"
    )
    html_template = models.TextField(
        help_text="HTML template used for this receipt"
    )
    generated_html = models.TextField(
        help_text="Generated HTML receipt"
    )
    
    # Control fields
    is_duplicate = models.BooleanField(default=False)
    original_receipt = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='duplicates'
    )
    reprint_count = models.PositiveIntegerField(default=0)
    
    # Security
    security_code = models.CharField(
        max_length=10,
        help_text="Code to verify receipt authenticity"
    )
    qr_code_data = models.TextField(blank=True)
    
    # Generation info
    generated_by = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='generated_receipts'
    )
    generated_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        verbose_name = "Payment Receipt"
        verbose_name_plural = "Payment Receipts"
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['receipt_number']),
            models.Index(fields=['payment', 'is_duplicate']),
        ]
    
    def __str__(self):
        duplicate_tag = " (Duplicate)" if self.is_duplicate else ""
        return f"Receipt {self.receipt_number}{duplicate_tag}"
    
    def generate_security_code(self):
        """Generate a security code for receipt verification"""
        import random
        import string
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    def create_duplicate(self, user):
        """Create a duplicate receipt with proper tracking"""
        duplicate = PaymentReceipt.objects.create(
            receipt_number=f"{self.receipt_number}-DUP{self.reprint_count + 1:02d}",
            payment=self.payment,
            receipt_data=self.receipt_data,
            html_template=self.html_template,
            generated_html=self.generated_html,
            is_duplicate=True,
            original_receipt=self,
            security_code=self.generate_security_code(),
            generated_by=user,
            branch=self.branch,
            created_by=user
        )
        
        self.reprint_count += 1
        self.save()
        
        # Update payment reprint tracking
        self.payment.receipt_reprint_count = self.reprint_count
        self.payment.last_reprinted_at = timezone.now()
        self.payment.last_reprinted_by = user
        self.payment.save()
        
        return duplicate


class PaymentReconciliation(BaseAppModel):
    """Daily payment reconciliation"""
    reconciliation_number = models.CharField(max_length=20, unique=True)
    reconciliation_date = models.DateField()
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    
    # Cash handling
    opening_cash = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Cash in drawer at start of day"
    )
    expected_cash = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Expected cash based on transactions"
    )
    actual_cash = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        help_text="Actual cash counted"
    )
    cash_difference = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        help_text="Difference between expected and actual"
    )
    
    # Payment method summaries
    cash_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    card_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    upi_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bank_transfer_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    insurance_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cheque_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_plan_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Counts
    total_transactions = models.PositiveIntegerField(default=0)
    total_refunds = models.PositiveIntegerField(default=0)
    refund_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Status
    STATUS_OPEN = 'OPEN'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_DISCREPANCY = 'DISCREPANCY'
    
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_DISCREPANCY, 'Discrepancy'),
    ]
    
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN
    )
    
    # Personnel
    prepared_by = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='prepared_reconciliations'
    )
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_reconciliations'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    # Discrepancy handling
    discrepancy_notes = models.TextField(blank=True)
    discrepancy_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resolved_discrepancies'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # EOD integration
    eod_lock = models.ForeignKey(
        'eod.EodLock', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reconciliations'
    )
    
    class Meta:
        verbose_name = "Payment Reconciliation"
        verbose_name_plural = "Payment Reconciliations"
        ordering = ['-reconciliation_date']
        unique_together = ['reconciliation_date', 'branch']
        indexes = [
            models.Index(fields=['reconciliation_number']),
            models.Index(fields=['reconciliation_date', 'branch']),
            models.Index(fields=['status', 'discrepancy_resolved']),
        ]
    
    def __str__(self):
        return f"Reconciliation {self.reconciliation_number} - {self.reconciliation_date}"
    
    def calculate_totals(self):
        """Calculate payment method totals from payments"""
        from django.db.models import Sum, Count
        
        payments = Payment.objects.filter(
            branch=self.branch,
            payment_date__date=self.reconciliation_date,
            status=Payment.COMPLETED
        )
        
        # Get totals by payment method
        method_totals = payments.values('payment_method__code').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Reset totals
        self.cash_total = Decimal('0')
        self.card_total = Decimal('0')
        self.upi_total = Decimal('0')
        self.bank_transfer_total = Decimal('0')
        self.insurance_total = Decimal('0')
        self.cheque_total = Decimal('0')
        self.payment_plan_total = Decimal('0')
        self.total_transactions = 0
        
        for method in method_totals:
            total = method['total'] or Decimal('0')
            count = method['count'] or 0
            
            if method['payment_method__code'] == PaymentMethod.CASH:
                self.cash_total = total
            elif method['payment_method__code'] == PaymentMethod.CARD:
                self.card_total = total
            elif method['payment_method__code'] == PaymentMethod.UPI:
                self.upi_total = total
            elif method['payment_method__code'] == PaymentMethod.BANK_TRANSFER:
                self.bank_transfer_total = total
            elif method['payment_method__code'] == PaymentMethod.INSURANCE:
                self.insurance_total = total
            elif method['payment_method__code'] == PaymentMethod.CHEQUE:
                self.cheque_total = total
            elif method['payment_method__code'] == PaymentMethod.PAYMENT_PLAN:
                self.payment_plan_total = total
            
            self.total_transactions += count
        
        # Calculate expected cash
        self.expected_cash = self.opening_cash + self.cash_total
        
        # Calculate refund totals
        refunds = Refund.objects.filter(
            branch=self.branch,
            requested_at__date=self.reconciliation_date,
            status__in=[Refund.COMPLETED]
        ).aggregate(
            total_refunds=Count('id'),
            refund_total=Sum('amount')
        )
        
        self.total_refunds = refunds['total_refunds'] or 0
        self.refund_total = refunds['refund_total'] or Decimal('0')
        
        # Adjust expected cash for cash refunds
        cash_refunds = Refund.objects.filter(
            branch=self.branch,
            requested_at__date=self.reconciliation_date,
            status=Refund.COMPLETED,
            refund_method=Refund.CASH
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        self.expected_cash -= cash_refunds
        
        self.save()
    
    def update_cash_count(self, actual_cash):
        """Update with actual cash count and calculate difference"""
        self.actual_cash = actual_cash
        self.cash_difference = actual_cash - self.expected_cash
        
        if abs(self.cash_difference) > Decimal('0.50'):  # 50 paise tolerance
            self.status = self.STATUS_DISCREPANCY
        else:
            self.status = self.STATUS_COMPLETED
        
        self.save()