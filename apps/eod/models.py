# apps/eod/models.py

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import uuid

User = get_user_model()


class BaseModel(models.Model):
    """Base model with common fields"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class BranchScopedModel(models.Model):
    """Branch scoping mixin"""
    branch = models.ForeignKey('clinics.Branch', on_delete=models.PROTECT)
    
    class Meta:
        abstract = True


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


class BaseAppModel(BaseModel, AuditableModel, BranchScopedModel):
    """Combined base model for all apps"""
    class Meta:
        abstract = True


class EodLock(BaseAppModel):
    """
    Main EOD lock model - represents a locked day for a branch
    Once locked, no financial transactions can be modified for that day
    """
    # EOD Statuses
    PREPARED = 'PREPARED'
    REVIEWED = 'REVIEWED'
    LOCKED = 'LOCKED'
    REVERSED = 'REVERSED'
    
    STATUS_CHOICES = [
        (PREPARED, 'Prepared'),
        (REVIEWED, 'Reviewed'),
        (LOCKED, 'Locked'),
        (REVERSED, 'Reversed'),
    ]
    
    # Core fields
    lock_number = models.CharField(
        max_length=20, unique=True,
        help_text="Auto-generated lock number: EOD-YYYYMMDD-XXX"
    )
    lock_date = models.DateField()
    
    # Financial summaries
    total_invoices = models.PositiveIntegerField(default=0)
    total_invoice_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_payments = models.PositiveIntegerField(default=0)
    total_payment_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_refunds = models.PositiveIntegerField(default=0)
    total_refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cash_collected = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cash_refunded = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_cash_position = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
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
        help_text="Actual cash counted during EOD"
    )
    cash_difference = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        help_text="Difference between expected and actual"
    )
    
    # Digital payments
    card_collections = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    upi_collections = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bank_transfers = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    insurance_collections = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cheque_collections = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Status and workflow
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=PREPARED
    )
    
    # Personnel
    prepared_by = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='prepared_eods'
    )
    prepared_at = models.DateTimeField(default=timezone.now)
    
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_eods'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    locked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='locked_eods'
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    
    reversed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reversed_eods'
    )
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversal_reason = models.TextField(blank=True)
    
    # Verification flags
    cash_verified = models.BooleanField(default=False)
    cash_verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verified_cash_eods'
    )
    cash_verified_at = models.DateTimeField(null=True, blank=True)
    
    digital_payments_verified = models.BooleanField(default=False)
    digital_verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verified_digital_eods'
    )
    digital_verified_at = models.DateTimeField(null=True, blank=True)
    
    invoices_verified = models.BooleanField(default=False)
    invoices_verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verified_invoices_eods'
    )
    invoices_verified_at = models.DateTimeField(null=True, blank=True)
    
    # Discrepancies
    has_discrepancies = models.BooleanField(default=False)
    discrepancy_notes = models.TextField(blank=True)
    discrepancy_resolved = models.BooleanField(default=False)
    discrepancy_resolved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resolved_eod_discrepancies'
    )
    discrepancy_resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Counters
    front_desk_counter = models.ForeignKey(
        'clinics.Counter', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='eod_locks',
        help_text="Front desk counter used for the day"
    )
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "EOD Lock"
        verbose_name_plural = "EOD Locks"
        ordering = ['-lock_date', 'branch']
        unique_together = ['lock_date', 'branch']
        indexes = [
            models.Index(fields=['lock_number']),
            models.Index(fields=['lock_date', 'branch', 'status']),
            models.Index(fields=['status', 'has_discrepancies']),
            models.Index(fields=['branch', 'locked_at']),
        ]
    
    def __str__(self):
        return f"EOD {self.lock_number} - {self.branch} - {self.lock_date}"
    
    def save(self, *args, **kwargs):
        if not self.lock_number:
            self.lock_number = self.generate_lock_number()
        
        # Calculate net cash position
        self.net_cash_position = self.total_cash_collected - self.total_cash_refunded
        
        super().save(*args, **kwargs)
    
    def generate_lock_number(self):
        """Generate unique lock number: EOD-YYYYMMDD-XXX"""
        date_str = self.lock_date.strftime('%Y%m%d')
        branch_code = self.branch.code if self.branch.code else '000'
        
        same_day_locks = EodLock.objects.filter(
            lock_date=self.lock_date,
            branch=self.branch
        ).count()
        
        sequence = same_day_locks + 1
        return f"EOD-{date_str}-{branch_code}-{sequence:03d}"
    
    def calculate_totals(self):
        """Calculate all financial totals for the day"""
        from django.db.models import Sum, Count
        from billing.models import Invoice
        from payments.models import Payment, Refund
        
        # Invoice totals
        invoices = Invoice.objects.filter(
            branch=self.branch,
            invoice_date=self.lock_date,
            is_active=True
        ).aggregate(
            total_invoices=Count('id'),
            total_amount=Sum('grand_total')
        )
        
        self.total_invoices = invoices['total_invoices'] or 0
        self.total_invoice_amount = invoices['total_amount'] or Decimal('0')
        
        # Payment totals
        payments = Payment.objects.filter(
            branch=self.branch,
            payment_date__date=self.lock_date,
            status=Payment.COMPLETED
        ).aggregate(
            total_payments=Count('id'),
            total_amount=Sum('amount')
        )
        
        self.total_payments = payments['total_payments'] or 0
        self.total_payment_amount = payments['total_amount'] or Decimal('0')
        
        # Payment method breakdown
        payment_methods = Payment.objects.filter(
            branch=self.branch,
            payment_date__date=self.lock_date,
            status=Payment.COMPLETED
        ).values('payment_method__code').annotate(
            total=Sum('amount')
        )
        
        # Reset payment method totals
        self.card_collections = Decimal('0')
        self.upi_collections = Decimal('0')
        self.bank_transfers = Decimal('0')
        self.insurance_collections = Decimal('0')
        self.cheque_collections = Decimal('0')
        self.total_cash_collected = Decimal('0')
        
        for method in payment_methods:
            total = method['total'] or Decimal('0')
            code = method['payment_method__code']
            
            if code == 'CASH':
                self.total_cash_collected = total
            elif code == 'CARD':
                self.card_collections = total
            elif code == 'UPI':
                self.upi_collections = total
            elif code == 'BANK_TRANSFER':
                self.bank_transfers = total
            elif code == 'INSURANCE':
                self.insurance_collections = total
            elif code == 'CHEQUE':
                self.cheque_collections = total
        
        # Refund totals
        refunds = Refund.objects.filter(
            branch=self.branch,
            requested_at__date=self.lock_date,
            status__in=[Refund.COMPLETED]
        ).aggregate(
            total_refunds=Count('id'),
            total_amount=Sum('amount')
        )
        
        self.total_refunds = refunds['total_refunds'] or 0
        self.total_refund_amount = refunds['total_amount'] or Decimal('0')
        
        # Cash refunds
        cash_refunds = Refund.objects.filter(
            branch=self.branch,
            requested_at__date=self.lock_date,
            status=Refund.COMPLETED,
            refund_method=Refund.CASH
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        self.total_cash_refunded = cash_refunds
        
        # Calculate expected cash
        self.expected_cash = self.opening_cash + self.total_cash_collected - cash_refunds
        
        # Calculate net cash
        self.net_cash_position = self.total_cash_collected - cash_refunds
        
        self.save()
    
    def verify_cash(self, actual_cash, verified_by):
        """Verify cash count and update EOD"""
        self.actual_cash = actual_cash
        self.cash_difference = actual_cash - self.expected_cash
        self.cash_verified = True
        self.cash_verified_by = verified_by
        self.cash_verified_at = timezone.now()
        
        if abs(self.cash_difference) > Decimal('0.50'):  # 50 paise tolerance
            self.has_discrepancies = True
            self.discrepancy_notes = f"Cash discrepancy: {self.cash_difference}"
        
        self.save()
    
    def lock(self, locked_by):
        """Lock the EOD - prevents further modifications"""
        if self.status != self.REVIEWED:
            raise ValueError("EOD must be reviewed before locking")
        
        self.status = self.LOCKED
        self.locked_by = locked_by
        self.locked_at = timezone.now()
        
        # Lock all related transactions
        self._lock_related_transactions()
        
        self.save()
    
    def _lock_related_transactions(self):
        """Lock all invoices, payments, and refunds for this day"""
        from billing.models import Invoice
        from payments.models import Payment, Refund
        
        # Lock invoices
        Invoice.objects.filter(
            branch=self.branch,
            invoice_date=self.lock_date
        ).update(eod_locked=True, locked_eod_id=self.lock_number)
        
        # Lock payments
        Payment.objects.filter(
            branch=self.branch,
            payment_date__date=self.lock_date
        ).update(eod_locked=True, locked_eod_id=self.lock_number)
        
        # Lock refunds
        Refund.objects.filter(
            branch=self.branch,
            requested_at__date=self.lock_date
        ).update(eod_locked=True)
    
    def reverse(self, reversed_by, reason):
        """Reverse an EOD lock (requires special permissions)"""
        if self.status != self.LOCKED:
            raise ValueError("Only locked EODs can be reversed")
        
        self.status = self.REVERSED
        self.reversed_by = reversed_by
        self.reversed_at = timezone.now()
        self.reversal_reason = reason
        
        # Unlock related transactions
        self._unlock_related_transactions()
        
        self.save()
    
    def _unlock_related_transactions(self):
        """Unlock all invoices, payments, and refunds for this day"""
        from billing.models import Invoice
        from payments.models import Payment, Refund
        
        # Unlock invoices
        Invoice.objects.filter(
            branch=self.branch,
            invoice_date=self.lock_date
        ).update(eod_locked=False, locked_eod_id='')
        
        # Unlock payments
        Payment.objects.filter(
            branch=self.branch,
            payment_date__date=self.lock_date
        ).update(eod_locked=False, locked_eod_id='')
        
        # Unlock refunds
        Refund.objects.filter(
            branch=self.branch,
            requested_at__date=self.lock_date
        ).update(eod_locked=False)
    
    def is_locked_for_date(branch, date):
        """Check if a date is locked for a branch"""
        return EodLock.objects.filter(
            branch=branch,
            lock_date=date,
            status=EodLock.LOCKED
        ).exists()


class DailySummary(BaseAppModel):
    """
    Detailed daily summary - can be generated multiple times per day
    (e.g., morning summary, afternoon summary, EOD summary)
    """
    # Summary Types
    MORNING = 'MORNING'
    AFTERNOON = 'AFTERNOON'
    EVENING = 'EVENING'
    EOD = 'EOD'
    CUSTOM = 'CUSTOM'
    
    SUMMARY_TYPE_CHOICES = [
        (MORNING, 'Morning Summary'),
        (AFTERNOON, 'Afternoon Summary'),
        (EVENING, 'Evening Summary'),
        (EOD, 'End of Day Summary'),
        (CUSTOM, 'Custom Summary'),
    ]
    
    # Core fields
    summary_number = models.CharField(max_length=20, unique=True)
    summary_date = models.DateField()
    summary_type = models.CharField(max_length=20, choices=SUMMARY_TYPE_CHOICES)
    custom_name = models.CharField(max_length=100, blank=True)
    
    # Time period
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Financial summary
    invoices_count = models.PositiveIntegerField(default=0)
    invoices_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payments_count = models.PositiveIntegerField(default=0)
    payments_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    refunds_count = models.PositiveIntegerField(default=0)
    refunds_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Appointment summary
    appointments_total = models.PositiveIntegerField(default=0)
    appointments_completed = models.PositiveIntegerField(default=0)
    appointments_cancelled = models.PositiveIntegerField(default=0)
    appointments_no_show = models.PositiveIntegerField(default=0)
    
    # Patient summary
    new_patients = models.PositiveIntegerField(default=0)
    returning_patients = models.PositiveIntegerField(default=0)
    
    # Doctor summary
    doctors_active = models.PositiveIntegerField(default=0)
    doctor_utilization = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of doctor time utilized"
    )
    
    # Detailed data (can be JSON for flexibility)
    invoice_details = models.JSONField(default=dict, blank=True)
    payment_details = models.JSONField(default=dict, blank=True)
    appointment_details = models.JSONField(default=dict, blank=True)
    
    # Related EOD
    eod_lock = models.ForeignKey(
        EodLock, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='summaries'
    )
    
    # Generation info
    generated_by = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='generated_summaries'
    )
    generated_at = models.DateTimeField(default=timezone.now)
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Daily Summary"
        verbose_name_plural = "Daily Summaries"
        ordering = ['-summary_date', '-period_end']
        indexes = [
            models.Index(fields=['summary_number']),
            models.Index(fields=['summary_date', 'summary_type']),
            models.Index(fields=['branch', 'period_end']),
        ]
    
    def __str__(self):
        type_display = dict(self.SUMMARY_TYPE_CHOICES)[self.summary_type]
        return f"{type_display} - {self.summary_date} - {self.branch}"
    
    def save(self, *args, **kwargs):
        if not self.summary_number:
            self.summary_number = self.generate_summary_number()
        super().save(*args, **kwargs)
    
    def generate_summary_number(self):
        """Generate unique summary number: SUM-YYYYMMDD-TYPE-XXX"""
        date_str = self.summary_date.strftime('%Y%m%d')
        type_code = self.summary_type[:3]
        
        same_day_summaries = DailySummary.objects.filter(
            summary_date=self.summary_date,
            branch=self.branch,
            summary_type=self.summary_type
        ).count()
        
        sequence = same_day_summaries + 1
        return f"SUM-{date_str}-{type_code}-{sequence:03d}"
    
    @classmethod
    def generate_summary(cls, branch, summary_type, period_start, period_end, generated_by, custom_name=''):
        """Generate a new daily summary with calculated data"""
        from django.db.models import Count, Sum, Q
        from billing.models import Invoice
        from payments.models import Payment, Refund
        from visits.models import Appointment
        from patients.models import Patient
        from doctors.models import Doctor
        
        summary = cls(
            branch=branch,
            summary_type=summary_type,
            custom_name=custom_name,
            summary_date=period_start.date(),
            period_start=period_start,
            period_end=period_end,
            generated_by=generated_by,
            created_by=generated_by
        )
        
        # Invoice data
        invoices = Invoice.objects.filter(
            branch=branch,
            invoice_date__date=summary.summary_date,
            created_at__range=(period_start, period_end),
            is_active=True
        )
        summary.invoices_count = invoices.count()
        summary.invoices_amount = invoices.aggregate(
            total=Sum('grand_total')
        )['total'] or Decimal('0')
        
        # Payment data
        payments = Payment.objects.filter(
            branch=branch,
            payment_date__range=(period_start, period_end),
            status=Payment.COMPLETED
        )
        summary.payments_count = payments.count()
        summary.payments_amount = payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        # Refund data
        refunds = Refund.objects.filter(
            branch=branch,
            requested_at__range=(period_start, period_end),
            status__in=[Refund.COMPLETED]
        )
        summary.refunds_count = refunds.count()
        summary.refunds_amount = refunds.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        # Appointment data
        appointments = Appointment.objects.filter(
            branch=branch,
            scheduled_date__date=summary.summary_date,
            scheduled_time__range=(period_start.time(), period_end.time())
        )
        summary.appointments_total = appointments.count()
        summary.appointments_completed = appointments.filter(
            status=Appointment.COMPLETED
        ).count()
        summary.appointments_cancelled = appointments.filter(
            status=Appointment.CANCELLED
        ).count()
        summary.appointments_no_show = appointments.filter(
            status=Appointment.NO_SHOW
        ).count()
        
        # Patient data
        summary.new_patients = Patient.objects.filter(
            branch=branch,
            created_at__range=(period_start, period_end)
        ).count()
        
        # Doctor data
        summary.doctors_active = Doctor.objects.filter(
            branch=branch,
            is_active=True
        ).count()
        
        # Save detailed data as JSON
        summary.invoice_details = {
            'count': summary.invoices_count,
            'amount': str(summary.invoices_amount),
            'by_type': list(invoices.values('invoice_type').annotate(
                count=Count('id'),
                amount=Sum('grand_total')
            ))
        }
        
        summary.save()
        return summary


class CashReconciliation(BaseAppModel):
    """
    Cash reconciliation records - tracks cash handovers between shifts
    """
    # Reconciliation Types
    OPENING = 'OPENING'
    MID_DAY = 'MID_DAY'
    CLOSING = 'CLOSING'
    SURPRISE = 'SURPRISE'
    
    RECONCILIATION_TYPE_CHOICES = [
        (OPENING, 'Opening Cash'),
        (MID_DAY, 'Mid-Day Cash'),
        (CLOSING, 'Closing Cash'),
        (SURPRISE, 'Surprise Check'),
    ]
    
    # Core fields
    reconciliation_number = models.CharField(max_length=20, unique=True)
    reconciliation_date = models.DateField()
    reconciliation_type = models.CharField(max_length=20, choices=RECONCILIATION_TYPE_CHOICES)
    
    # Cash amounts
    declared_cash = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="Cash declared by cashier"
    )
    counted_cash = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        help_text="Cash counted by supervisor"
    )
    difference = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True,
        help_text="Difference between declared and counted"
    )
    
    # Denomination breakdown
    denomination_breakdown = models.JSONField(
        default=dict,
        help_text="JSON breakdown of cash by denomination"
    )
    
    # Personnel
    cashier = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='cash_reconciliations',
        help_text="Cashier responsible for the cash"
    )
    counter = models.ForeignKey(
        'clinics.Counter', on_delete=models.PROTECT,
        related_name='cash_reconciliations',
        help_text="Counter where cash is stored"
    )
    
    supervisor = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='supervised_reconciliations',
        help_text="Supervisor who verified the cash"
    )
    supervised_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    verified = models.BooleanField(default=False)
    verification_notes = models.TextField(blank=True)
    
    # Related EOD
    eod_lock = models.ForeignKey(
        EodLock, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cash_reconciliations'
    )
    
    # Images/Attachments (paths stored, files in media)
    cash_count_image = models.ImageField(
        upload_to='cash_reconciliations/%Y/%m/%d/',
        null=True, blank=True,
        help_text="Photo of cash count if surprise check"
    )
    signature_image = models.ImageField(
        upload_to='signatures/%Y/%m/%d/',
        null=True, blank=True,
        help_text="Cashier's signature"
    )
    
    # Notes
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Cash Reconciliation"
        verbose_name_plural = "Cash Reconciliations"
        ordering = ['-reconciliation_date', '-created_at']
        indexes = [
            models.Index(fields=['reconciliation_number']),
            models.Index(fields=['reconciliation_date', 'reconciliation_type']),
            models.Index(fields=['cashier', 'verified']),
            models.Index(fields=['counter', 'reconciliation_date']),
        ]
    
    def __str__(self):
        type_display = dict(self.RECONCILIATION_TYPE_CHOICES)[self.reconciliation_type]
        return f"Cash {type_display} - {self.reconciliation_date} - {self.cashier}"
    
    def save(self, *args, **kwargs):
        if not self.reconciliation_number:
            self.reconciliation_number = self.generate_reconciliation_number()
        
        # Calculate difference if counted cash is provided
        if self.counted_cash is not None:
            self.difference = self.counted_cash - self.declared_cash
        
        super().save(*args, **kwargs)
    
    def generate_reconciliation_number(self):
        """Generate unique reconciliation number: CASH-YYYYMMDD-TYPE-XXX"""
        date_str = self.reconciliation_date.strftime('%Y%m%d')
        type_code = self.reconciliation_type[:3]
        
        same_day_recons = CashReconciliation.objects.filter(
            reconciliation_date=self.reconciliation_date,
            branch=self.branch,
            reconciliation_type=self.reconciliation_type
        ).count()
        
        sequence = same_day_recons + 1
        return f"CASH-{date_str}-{type_code}-{sequence:03d}"
    
    def verify(self, supervisor, counted_cash, verification_notes='', denomination_breakdown=None):
        """Verify cash reconciliation"""
        self.supervisor = supervisor
        self.supervised_at = timezone.now()
        self.counted_cash = counted_cash
        self.difference = counted_cash - self.declared_cash
        
        if denomination_breakdown:
            self.denomination_breakdown = denomination_breakdown
        
        self.verification_notes = verification_notes
        self.verified = True
        
        self.save()
    
    def get_denomination_total(self):
        """Calculate total from denomination breakdown"""
        if not self.denomination_breakdown:
            return Decimal('0')
        
        total = Decimal('0')
        for denomination, count in self.denomination_breakdown.items():
            try:
                denom_value = Decimal(denomination)
                total += denom_value * count
            except (ValueError, TypeError):
                continue
        
        return total


class EodException(BaseAppModel):
    """
    Records exceptions/discrepancies found during EOD process
    """
    # Exception Types
    CASH_DISCREPANCY = 'CASH_DISCREPANCY'
    MISSING_RECEIPT = 'MISSING_RECEIPT'
    UNACCOUNTED_PAYMENT = 'UNACCOUNTED_PAYMENT'
    DATA_MISMATCH = 'DATA_MISMATCH'
    SYSTEM_ERROR = 'SYSTEM_ERROR'
    OTHER = 'OTHER'
    
    EXCEPTION_TYPE_CHOICES = [
        (CASH_DISCREPANCY, 'Cash Discrepancy'),
        (MISSING_RECEIPT, 'Missing Receipt'),
        (UNACCOUNTED_PAYMENT, 'Unaccounted Payment'),
        (DATA_MISMATCH, 'Data Mismatch'),
        (SYSTEM_ERROR, 'System Error'),
        (OTHER, 'Other'),
    ]
    
    # Severity Levels
    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'
    CRITICAL = 'CRITICAL'
    
    SEVERITY_CHOICES = [
        (LOW, 'Low'),
        (MEDIUM, 'Medium'),
        (HIGH, 'High'),
        (CRITICAL, 'Critical'),
    ]
    
    # Status
    OPEN = 'OPEN'
    IN_PROGRESS = 'IN_PROGRESS'
    RESOLVED = 'RESOLVED'
    CANCELLED = 'CANCELLED'
    
    STATUS_CHOICES = [
        (OPEN, 'Open'),
        (IN_PROGRESS, 'In Progress'),
        (RESOLVED, 'Resolved'),
        (CANCELLED, 'Cancelled'),
    ]
    
    # Core fields
    exception_number = models.CharField(max_length=20, unique=True)
    exception_date = models.DateField()
    exception_type = models.CharField(max_length=20, choices=EXCEPTION_TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default=MEDIUM)
    
    # Description
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Amount involved (if applicable)
    amount_involved = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True
    )
    
    # Related records
    related_invoice = models.ForeignKey(
        'billing.Invoice', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='eod_exceptions'
    )
    related_payment = models.ForeignKey(
        'payments.Payment', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='eod_exceptions'
    )
    related_refund = models.ForeignKey(
        'payments.Refund', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='eod_exceptions'
    )
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=OPEN)
    
    # Assignment
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_exceptions'
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    
    # Resolution
    resolved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='resolved_exceptions'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    resolution_action = models.CharField(max_length=200, blank=True)
    
    # Related EOD
    eod_lock = models.ForeignKey(
        EodLock, on_delete=models.CASCADE,
        related_name='exceptions',
        help_text="EOD during which this exception was found"
    )
    
    # Attachments
    attachment = models.FileField(
        upload_to='eod_exceptions/%Y/%m/%d/',
        null=True, blank=True
    )
    
    class Meta:
        verbose_name = "EOD Exception"
        verbose_name_plural = "EOD Exceptions"
        ordering = ['-exception_date', '-created_at']
        indexes = [
            models.Index(fields=['exception_number']),
            models.Index(fields=['exception_date', 'exception_type']),
            models.Index(fields=['status', 'severity']),
            models.Index(fields=['assigned_to', 'status']),
        ]
    
    def __str__(self):
        return f"Exception {self.exception_number}: {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.exception_number:
            self.exception_number = self.generate_exception_number()
        super().save(*args, **kwargs)
    
    def generate_exception_number(self):
        """Generate unique exception number: EXC-YYYYMMDD-XXX"""
        date_str = self.exception_date.strftime('%Y%m%d')
        
        same_day_exceptions = EodException.objects.filter(
            exception_date=self.exception_date,
            branch=self.branch
        ).count()
        
        sequence = same_day_exceptions + 1
        return f"EXC-{date_str}-{sequence:04d}"
    
    def assign(self, assigned_to):
        """Assign exception to a user"""
        self.assigned_to = assigned_to
        self.assigned_at = timezone.now()
        self.status = self.IN_PROGRESS
        self.save()
    
    def resolve(self, resolved_by, resolution_notes, resolution_action=''):
        """Mark exception as resolved"""
        self.resolved_by = resolved_by
        self.resolved_at = timezone.now()
        self.resolution_notes = resolution_notes
        self.resolution_action = resolution_action
        self.status = self.RESOLVED
        self.save()