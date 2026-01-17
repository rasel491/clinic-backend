#apps/treatments/models.py
from django.db import models
from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin
from decimal import Decimal

class TreatmentCategory(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """Category of dental treatments (Cleaning, Filling, Extraction, etc.)"""
    
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'treatment_categories'
        verbose_name_plural = 'Treatment Categories'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class Treatment(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """Individual dental treatment/procedure"""
    
    DIFFICULTY_CHOICES = [
        ('EASY', 'Easy'),
        ('MEDIUM', 'Medium'),
        ('COMPLEX', 'Complex'),
        ('SPECIALIST', 'Specialist'),
    ]
    
    DURATION_UNITS = [
        ('MINUTES', 'Minutes'),
        ('HOURS', 'Hours'),
        ('DAYS', 'Days'),
    ]
    
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=30, unique=True)
    category = models.ForeignKey(
        TreatmentCategory,
        on_delete=models.PROTECT,
        related_name='treatments'
    )
    
    # Pricing
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    doctor_fee_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        default=Decimal('30.00'),  # 30% of base price goes to doctor
        help_text="Percentage of base price that goes to doctor"
    )
    tax_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('18.00'),  # 18% GST
        help_text="Tax percentage applied"
    )
    
    # Operational
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='MEDIUM')
    duration_value = models.PositiveIntegerField(default=30)
    duration_unit = models.CharField(max_length=10, choices=DURATION_UNITS, default='MINUTES')
    
    # Details
    description = models.TextField(blank=True)
    procedure_steps = models.TextField(blank=True, help_text="Step-by-step procedure")
    materials_required = models.TextField(blank=True)
    precautions = models.TextField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    requires_lab = models.BooleanField(default=False)
    lab_days = models.PositiveIntegerField(default=0, help_text="Lab processing time in days")
    
    class Meta:
        db_table = 'treatments'
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['code']),
            models.Index(fields=['base_price']),
        ]
    
    def __str__(self):
        return f"{self.code}: {self.name}"
    
    @property
    def doctor_fee(self):
        """Calculate doctor's fee for this treatment"""
        return (self.base_price * self.doctor_fee_percentage) / Decimal('100.00')
    
    @property
    def tax_amount(self):
        """Calculate tax amount"""
        return (self.base_price * self.tax_percentage) / Decimal('100.00')
    
    @property
    def total_price(self):
        """Total price including tax"""
        return self.base_price + self.tax_amount
    
    @property
    def duration_display(self):
        """Human readable duration"""
        return f"{self.duration_value} {self.duration_unit.lower()}"


class TreatmentPlan(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """Multi-visit treatment plan for a patient"""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PROPOSED', 'Proposed to Patient'),
        ('ACCEPTED', 'Accepted by Patient'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='treatment_plans'
    )
    doctor = models.ForeignKey(
        'doctors.Doctor',
        on_delete=models.PROTECT,
        related_name='treatment_plans'
    )
    
    # Plan details
    plan_id = models.CharField(max_length=50, unique=True, blank=True)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Financial
    total_estimated_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Timeline
    estimated_start_date = models.DateField(null=True, blank=True)
    estimated_end_date = models.DateField(null=True, blank=True)
    actual_start_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    
    # Notes
    diagnosis = models.TextField(blank=True)
    treatment_goals = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'treatment_plans'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['doctor', 'status']),
            models.Index(fields=['plan_id']),
            models.Index(fields=['status', 'estimated_start_date']),
        ]
    
    def __str__(self):
        return f"Plan {self.plan_id}: {self.name} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        if not self.plan_id:
            self.plan_id = self._generate_plan_id()
        
        # Calculate final amount
        discount = (self.total_estimated_amount * self.discount_percentage) / Decimal('100.00')
        self.discount_amount = discount
        self.final_amount = self.total_estimated_amount - discount
        
        super().save(*args, **kwargs)
    
    def _generate_plan_id(self):
        """Generate TP-YYYYMM-XXXX format ID"""
        from datetime import datetime
        from django.db.models import Count
        
        today = datetime.now()
        year_month = today.strftime('%Y%m')
        
        last_plan = TreatmentPlan.objects.filter(
            plan_id__startswith=f'TP-{year_month}-'
        ).order_by('plan_id').last()
        
        if last_plan:
            last_num = int(last_plan.plan_id.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f'TP-{year_month}-{new_num:04d}'
    
    @property
    def balance_amount(self):
        return self.final_amount - self.paid_amount
    
    @property
    def is_paid(self):
        return self.paid_amount >= self.final_amount
    
    @property
    def progress_percentage(self):
        """Calculate progress based on completed visits"""
        total_items = self.plan_items.count()
        if total_items == 0:
            return 0
        
        completed_items = self.plan_items.filter(status='COMPLETED').count()
        return (completed_items / total_items) * 100


class TreatmentPlanItem(AuditFieldsMixin, models.Model):
    """Individual treatment within a plan"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('DEFERRED', 'Deferred'),
    ]
    
    treatment_plan = models.ForeignKey(
        TreatmentPlan,
        on_delete=models.CASCADE,
        related_name='plan_items'
    )
    treatment = models.ForeignKey(
        Treatment,
        on_delete=models.PROTECT,
        related_name='plan_items'
    )
    
    # Scheduling
    visit_number = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_visit = models.ForeignKey(
        'visits.Visit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='treatment_plan_items'
    )
    
    # Financial
    actual_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    
    # Clinical
    tooth_number = models.CharField(max_length=20, blank=True, help_text="Tooth FDI notation")
    surface = models.CharField(max_length=50, blank=True, help_text="Tooth surface")
    notes = models.TextField(blank=True)
    
    # Dates
    completed_date = models.DateField(null=True, blank=True)
    
    class Meta:
        db_table = 'treatment_plan_items'
        ordering = ['treatment_plan', 'visit_number']
        unique_together = ['treatment_plan', 'visit_number']
        indexes = [
            models.Index(fields=['treatment_plan', 'status']),
            models.Index(fields=['status', 'scheduled_date']),
            models.Index(fields=['scheduled_visit']),
        ]
    
    def __str__(self):
        return f"{self.treatment_plan.plan_id} - Visit {self.visit_number}: {self.treatment.name}"
    
    def save(self, *args, **kwargs):
        # Auto-set actual_amount from treatment if not set
        if not self.actual_amount and self.treatment:
            self.actual_amount = self.treatment.total_price
        super().save(*args, **kwargs)