#apps/billing/models.py

from django.db import models
from django.utils import timezone
from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator

class Invoice(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """Invoice for patient visit - IMMUTABLE after payment"""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ISSUED', 'Issued'),
        ('UNPAID', 'Unpaid'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('VOID', 'Void'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    # Core relationships
    branch = models.ForeignKey(
        'clinics.Branch',
        on_delete=models.PROTECT,
        related_name='invoices'
    )
    visit = models.OneToOneField(
        'visits.Visit',
        on_delete=models.PROTECT,
        related_name='invoice_link'  # ✅ Matches visits.linked_invoice
    )
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.PROTECT,
        related_name='invoices'
    )
    
    # Invoice identification
    invoice_number = models.CharField(max_length=50, unique=True, blank=True)
    invoice_date = models.DateField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    is_locked = models.BooleanField(default=False, help_text="Locked by EOD process")
    is_final = models.BooleanField(default=False, help_text="Final invoice, cannot modify")
    
    # Financial breakdown
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Percentage discount"
    )
    
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    tax_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('18.00'),  # Default GST
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Calculated fields
    balance_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Payment tracking
    payment_due_date = models.DateField(null=True, blank=True)
    last_payment_date = models.DateField(null=True, blank=True)
    
    # Override control
    override_reason = models.TextField(blank=True)
    override_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='overridden_invoices'
    )
    
    # EOD linkage
    # eod_lock = models.ForeignKey(
    #     'eod.EodLock',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='invoices'
    # )
    
    class Meta:
        db_table = 'invoices'
        ordering = ['-invoice_date', '-created_at']
        indexes = [
            models.Index(fields=['invoice_number']),
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['branch', 'status', 'invoice_date']),
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['visit']),
            models.Index(fields=['is_locked']),
            models.Index(fields=['is_final']),
        ]
    
    def __str__(self):
        return f"Invoice {self.invoice_number}: {self.patient} - ₹{self.total_amount}"
    
    def save(self, *args, **kwargs):
        # Auto-generate invoice number
        if not self.invoice_number:
            self.invoice_number = self._generate_invoice_number()
        
        # Auto-calculate amounts
        self._calculate_amounts()
        
        # Auto-set due date (30 days from invoice date)
        if not self.due_date:
            from datetime import timedelta
            self.due_date = self.invoice_date + timedelta(days=30)
        
        # Calculate balance
        self.balance_amount = self.total_amount - self.paid_amount
        
        # Auto-update status based on payments
        self._update_status()
        
        super().save(*args, **kwargs)
    
    def _generate_invoice_number(self):
        """Generate INV-YYYYMM-XXXX format"""
        from datetime import datetime
        from django.db.models import Count
        
        today = datetime.now()
        year_month = today.strftime('%Y%m')
        
        last_invoice = Invoice.objects.filter(
            invoice_number__startswith=f'INV-{year_month}-'
        ).order_by('invoice_number').last()
        
        if last_invoice:
            last_num = int(last_invoice.invoice_number.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f'INV-{year_month}-{new_num:04d}'
    
    def _calculate_amounts(self):
        """Calculate all financial amounts"""
        # Calculate discount amount
        self.discount_amount = (self.subtotal * self.discount_percentage) / Decimal('100.00')
        
        # Calculate taxable amount
        taxable_amount = self.subtotal - self.discount_amount
        
        # Calculate tax
        self.tax_amount = (taxable_amount * self.tax_percentage) / Decimal('100.00')
        
        # Calculate total
        self.total_amount = taxable_amount + self.tax_amount
    
    def _update_status(self):
        """Update invoice status based on payments"""
        if self.status in ['VOID', 'CANCELLED']:
            return
        
        if self.paid_amount <= 0:
            self.status = 'UNPAID'
        elif self.paid_amount >= self.total_amount:
            self.status = 'PAID'
            self.is_final = True
        elif self.paid_amount > 0:
            self.status = 'PARTIALLY_PAID'
        
        # Check if overdue
        if self.status in ['UNPAID', 'PARTIALLY_PAID'] and self.due_date:
            from django.utils import timezone
            if timezone.now().date() > self.due_date:
                self.status = 'OVERDUE'
    
    @property
    def is_paid(self):
        return self.status == 'PAID'
    
    @property
    def is_overdue(self):
        return self.status == 'OVERDUE'
    
    @property
    def can_modify(self):
        """Check if invoice can be modified"""
        return not (self.is_final or self.is_locked or self.status in ['PAID', 'VOID'])
    
    def apply_payment(self, amount, payment_method, user):
        """Apply payment to invoice"""
        from apps.payments.models import Payment
        
        if not self.can_modify:
            raise ValueError("Invoice cannot accept payments (locked, paid, or void)")
        
        payment = Payment.objects.create(
            invoice=self,
            amount=amount,
            payment_method=payment_method,
            received_by=user,
            branch=self.branch,
            status='COMPLETED'
        )
        
        self.paid_amount += amount
        self.last_payment_date = timezone.now().date()
        self.save()
        
        return payment
    
    def void_invoice(self, reason, user):
        """Void an invoice (requires manager approval)"""
        if self.status in ['PAID', 'VOID']:
            raise ValueError("Cannot void paid or already void invoice")
        
        self.status = 'VOID'
        self.override_reason = reason
        self.override_by = user
        self.is_final = True
        self.save()


class InvoiceItem(AuditFieldsMixin, models.Model):
    """Line items on an invoice"""
    
    ITEM_TYPE_CHOICES = [
        ('TREATMENT', 'Treatment'),
        ('MEDICINE', 'Medicine'),
        ('CONSULTATION', 'Consultation'),
        ('LAB', 'Lab Test'),
        ('PROCEDURE', 'Procedure'),
        ('OTHER', 'Other'),
    ]
    
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='items'
    )
    
    # Item identification
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    description = models.CharField(max_length=500)
    code = models.CharField(max_length=50, blank=True, help_text="Treatment code or medicine code")
    
    # Link to treatment if applicable
    treatment = models.ForeignKey(
        'treatments.Treatment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_items'
    )
    
    treatment_plan_item = models.ForeignKey(
        'treatments.TreatmentPlanItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_items'
    )
    
    # Pricing
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    tax_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('18.00')
    )
    
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Doctor commission
    doctor = models.ForeignKey(
        'doctors.Doctor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='commission_items'
    )
    
    doctor_commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    doctor_commission_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    class Meta:
        db_table = 'invoice_items'
        ordering = ['invoice', 'id']
        indexes = [
            models.Index(fields=['invoice', 'item_type']),
            models.Index(fields=['treatment']),
            models.Index(fields=['doctor']),
        ]
    
    def __str__(self):
        return f"{self.description} - ₹{self.total_amount}"
    
    def save(self, *args, **kwargs):
        # Calculate amounts
        self._calculate_amounts()
        super().save(*args, **kwargs)
        
        # Update parent invoice subtotal
        if self.invoice:
            self.invoice.subtotal = self.invoice.items.aggregate(
                total=models.Sum('total_amount')
            )['total'] or Decimal('0.00')
            self.invoice.save()
    
    def _calculate_amounts(self):
        """Calculate item financials"""
        base_amount = self.unit_price * self.quantity
        
        # Calculate discount
        self.discount_amount = (base_amount * self.discount_percentage) / Decimal('100.00')
        
        # Calculate taxable amount
        taxable_amount = base_amount - self.discount_amount
        
        # Calculate tax
        self.tax_amount = (taxable_amount * self.tax_percentage) / Decimal('100.00')
        
        # Calculate total
        self.total_amount = taxable_amount + self.tax_amount
        
        # Calculate doctor commission
        if self.doctor and self.doctor_commission_percentage > 0:
            self.doctor_commission_amount = (
                self.total_amount * self.doctor_commission_percentage
            ) / Decimal('100.00')


class DiscountPolicy(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """Discount policies for different user roles"""
    
    DISCOUNT_TYPE_CHOICES = [
        ('PERCENTAGE', 'Percentage'),
        ('FIXED', 'Fixed Amount'),
        ('FREE', 'Free'),
    ]
    
    APPLICABLE_TO_CHOICES = [
        ('ALL', 'All Patients'),
        ('STAFF', 'Staff Only'),
        ('SENIOR_CITIZEN', 'Senior Citizen'),
        ('CHILD', 'Child'),
        ('INSURANCE', 'Insurance Patients'),
        ('CORPORATE', 'Corporate Clients'),
        ('SPECIAL', 'Special Cases'),
    ]
    
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    
    # Discount value
    percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    
    fixed_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Applicability
    applicable_to = models.CharField(max_length=20, choices=APPLICABLE_TO_CHOICES, default='ALL')
    minimum_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    maximum_discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Validity
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Approval requirements
    requires_approval = models.BooleanField(default=False)
    min_approval_level = models.CharField(
        max_length=20,
        choices=[('MANAGER', 'Manager'), ('ADMIN', 'Admin')],
        default='MANAGER'
    )
    
    # Usage limits
    usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum times this discount can be used")
    used_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'discount_policies'
        verbose_name_plural = 'Discount Policies'
        ordering = ['code']
        indexes = [
            models.Index(fields=['code', 'is_active']),
            models.Index(fields=['applicable_to', 'is_active']),
            models.Index(fields=['valid_from', 'valid_until']),
        ]
    
    def __str__(self):
        return f"{self.code}: {self.name}"
    
    def calculate_discount(self, invoice_amount):
        """Calculate discount amount for given invoice amount"""
        if not self.is_active:
            return Decimal('0.00')
        
        if self.discount_type == 'PERCENTAGE' and self.percentage:
            discount = (invoice_amount * self.percentage) / Decimal('100.00')
        elif self.discount_type == 'FIXED' and self.fixed_amount:
            discount = self.fixed_amount
        elif self.discount_type == 'FREE':
            discount = invoice_amount
        else:
            discount = Decimal('0.00')
        
        # Apply maximum discount limit
        if self.maximum_discount and discount > self.maximum_discount:
            discount = self.maximum_discount
        
        return discount
    
    def can_apply(self, patient, user):
        """Check if discount can be applied"""
        if not self.is_active:
            return False, "Discount is not active"
        
        # Check validity dates
        from django.utils import timezone
        today = timezone.now().date()
        if today < self.valid_from:
            return False, "Discount not yet valid"
        if self.valid_until and today > self.valid_until:
            return False, "Discount expired"
        
        # Check usage limit
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False, "Discount usage limit reached"
        
        # Check approval requirement
        if self.requires_approval and not user.has_role(self.min_approval_level):
            return False, f"Requires {self.min_approval_level} approval"
        
        return True, ""


class AppliedDiscount(AuditFieldsMixin, models.Model):
    """Record of discounts applied to invoices"""
    
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='applied_discounts'
    )
    
    discount_policy = models.ForeignKey(
        DiscountPolicy,
        on_delete=models.PROTECT,
        related_name='applications'
    )
    
    # Discount details
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    original_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Approval tracking
    approved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_discounts'
    )
    
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    
    # Reversal tracking
    is_reversed = models.BooleanField(default=False)
    reversed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reversed_discounts'
    )
    
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversal_reason = models.TextField(blank=True)
    
    class Meta:
        db_table = 'applied_discounts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invoice', 'discount_policy']),
            models.Index(fields=['is_reversed']),
        ]
    
    def __str__(self):
        return f"Discount: {self.discount_policy.code} - ₹{self.discount_amount}"
    
    def save(self, *args, **kwargs):
        if not self.pk:  # New record
            # Increment usage count
            self.discount_policy.used_count += 1
            self.discount_policy.save()
        
        super().save(*args, **kwargs)