# #apps/treatments/models.py
# from django.db import models
# from core.mixins.audit_fields import AuditFieldsMixin
# from core.mixins.soft_delete import SoftDeleteMixin
# from decimal import Decimal

# class TreatmentCategory(AuditFieldsMixin, SoftDeleteMixin, models.Model):
#     """Category of dental treatments (Cleaning, Filling, Extraction, etc.)"""
    
#     name = models.CharField(max_length=100)
#     code = models.CharField(max_length=20, unique=True)
#     description = models.TextField(blank=True)
#     is_active = models.BooleanField(default=True)
    
#     class Meta:
#         db_table = 'treatment_categories'
#         verbose_name_plural = 'Treatment Categories'
#         ordering = ['name']
    
#     def __str__(self):
#         return f"{self.name} ({self.code})"


# class Treatment(AuditFieldsMixin, SoftDeleteMixin, models.Model):
#     """Individual dental treatment/procedure"""
    
#     DIFFICULTY_CHOICES = [
#         ('EASY', 'Easy'),
#         ('MEDIUM', 'Medium'),
#         ('COMPLEX', 'Complex'),
#         ('SPECIALIST', 'Specialist'),
#     ]
    
#     DURATION_UNITS = [
#         ('MINUTES', 'Minutes'),
#         ('HOURS', 'Hours'),
#         ('DAYS', 'Days'),
#     ]
    
#     name = models.CharField(max_length=200)
#     code = models.CharField(max_length=30, unique=True)
#     category = models.ForeignKey(
#         TreatmentCategory,
#         on_delete=models.PROTECT,
#         related_name='treatments'
#     )
    
#     # Pricing
#     base_price = models.DecimalField(max_digits=10, decimal_places=2)
#     doctor_fee_percentage = models.DecimalField(
#         max_digits=5, 
#         decimal_places=2,
#         default=Decimal('30.00'),  # 30% of base price goes to doctor
#         help_text="Percentage of base price that goes to doctor"
#     )
#     tax_percentage = models.DecimalField(
#         max_digits=5,
#         decimal_places=2,
#         default=Decimal('18.00'),  # 18% GST
#         help_text="Tax percentage applied"
#     )
    
#     # Operational
#     difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='MEDIUM')
#     duration_value = models.PositiveIntegerField(default=30)
#     duration_unit = models.CharField(max_length=10, choices=DURATION_UNITS, default='MINUTES')
    
#     # Details
#     description = models.TextField(blank=True)
#     procedure_steps = models.TextField(blank=True, help_text="Step-by-step procedure")
#     materials_required = models.TextField(blank=True)
#     precautions = models.TextField(blank=True)
    
#     # Status
#     is_active = models.BooleanField(default=True)
#     requires_lab = models.BooleanField(default=False)
#     lab_days = models.PositiveIntegerField(default=0, help_text="Lab processing time in days")
    
#     class Meta:
#         db_table = 'treatments'
#         ordering = ['category', 'name']
#         indexes = [
#             models.Index(fields=['category', 'is_active']),
#             models.Index(fields=['code']),
#             models.Index(fields=['base_price']),
#         ]
    
#     def __str__(self):
#         return f"{self.code}: {self.name}"
    
#     @property
#     def doctor_fee(self):
#         """Calculate doctor's fee for this treatment"""
#         return (self.base_price * self.doctor_fee_percentage) / Decimal('100.00')
    
#     @property
#     def tax_amount(self):
#         """Calculate tax amount"""
#         return (self.base_price * self.tax_percentage) / Decimal('100.00')
    
#     @property
#     def total_price(self):
#         """Total price including tax"""
#         return self.base_price + self.tax_amount
    
#     @property
#     def duration_display(self):
#         """Human readable duration"""
#         return f"{self.duration_value} {self.duration_unit.lower()}"


# class TreatmentPlan(AuditFieldsMixin, SoftDeleteMixin, models.Model):
#     """Multi-visit treatment plan for a patient"""
    
#     STATUS_CHOICES = [
#         ('DRAFT', 'Draft'),
#         ('PROPOSED', 'Proposed to Patient'),
#         ('ACCEPTED', 'Accepted by Patient'),
#         ('IN_PROGRESS', 'In Progress'),
#         ('COMPLETED', 'Completed'),
#         ('CANCELLED', 'Cancelled'),
#     ]
    
#     patient = models.ForeignKey(
#         'patients.Patient',
#         on_delete=models.CASCADE,
#         related_name='treatment_plans'
#     )
#     doctor = models.ForeignKey(
#         'doctors.Doctor',
#         on_delete=models.PROTECT,
#         related_name='treatment_plans'
#     )
    
#     # Plan details
#     plan_id = models.CharField(max_length=50, unique=True, blank=True)
#     name = models.CharField(max_length=200)
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
#     # Financial
#     total_estimated_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
#     discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
#     discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
#     final_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
#     paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
#     # Timeline
#     estimated_start_date = models.DateField(null=True, blank=True)
#     estimated_end_date = models.DateField(null=True, blank=True)
#     actual_start_date = models.DateField(null=True, blank=True)
#     actual_end_date = models.DateField(null=True, blank=True)
    
#     # Notes
#     diagnosis = models.TextField(blank=True)
#     treatment_goals = models.TextField(blank=True)
#     notes = models.TextField(blank=True)
    
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         db_table = 'treatment_plans'
#         ordering = ['-created_at']
#         indexes = [
#             models.Index(fields=['patient', 'status']),
#             models.Index(fields=['doctor', 'status']),
#             models.Index(fields=['plan_id']),
#             models.Index(fields=['status', 'estimated_start_date']),
#         ]
    
#     def __str__(self):
#         return f"Plan {self.plan_id}: {self.name} ({self.get_status_display()})"
    
#     def save(self, *args, **kwargs):
#         if not self.plan_id:
#             self.plan_id = self._generate_plan_id()
        
#         # Calculate final amount
#         discount = (self.total_estimated_amount * self.discount_percentage) / Decimal('100.00')
#         self.discount_amount = discount
#         self.final_amount = self.total_estimated_amount - discount
        
#         super().save(*args, **kwargs)
    
#     def _generate_plan_id(self):
#         """Generate TP-YYYYMM-XXXX format ID"""
#         from datetime import datetime
#         from django.db.models import Count
        
#         today = datetime.now()
#         year_month = today.strftime('%Y%m')
        
#         last_plan = TreatmentPlan.objects.filter(
#             plan_id__startswith=f'TP-{year_month}-'
#         ).order_by('plan_id').last()
        
#         if last_plan:
#             last_num = int(last_plan.plan_id.split('-')[-1])
#             new_num = last_num + 1
#         else:
#             new_num = 1
        
#         return f'TP-{year_month}-{new_num:04d}'
    
#     @property
#     def balance_amount(self):
#         return self.final_amount - self.paid_amount
    
#     @property
#     def is_paid(self):
#         return self.paid_amount >= self.final_amount
    
#     @property
#     def progress_percentage(self):
#         """Calculate progress based on completed visits"""
#         total_items = self.plan_items.count()
#         if total_items == 0:
#             return 0
        
#         completed_items = self.plan_items.filter(status='COMPLETED').count()
#         return (completed_items / total_items) * 100


# class TreatmentPlanItem(AuditFieldsMixin, models.Model):
#     """Individual treatment within a plan"""
    
#     STATUS_CHOICES = [
#         ('PENDING', 'Pending'),
#         ('SCHEDULED', 'Scheduled'),
#         ('IN_PROGRESS', 'In Progress'),
#         ('COMPLETED', 'Completed'),
#         ('CANCELLED', 'Cancelled'),
#         ('DEFERRED', 'Deferred'),
#     ]
    
#     treatment_plan = models.ForeignKey(
#         TreatmentPlan,
#         on_delete=models.CASCADE,
#         related_name='plan_items'
#     )
#     treatment = models.ForeignKey(
#         Treatment,
#         on_delete=models.PROTECT,
#         related_name='plan_items'
#     )
    
#     # Scheduling
#     visit_number = models.PositiveIntegerField()
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
#     scheduled_date = models.DateField(null=True, blank=True)
#     scheduled_visit = models.ForeignKey(
#         'visits.Visit',
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='treatment_plan_items'
#     )
    
#     # Financial
#     actual_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
#     is_paid = models.BooleanField(default=False)
    
#     # Clinical
#     tooth_number = models.CharField(max_length=20, blank=True, help_text="Tooth FDI notation")
#     surface = models.CharField(max_length=50, blank=True, help_text="Tooth surface")
#     notes = models.TextField(blank=True)
    
#     # Dates
#     completed_date = models.DateField(null=True, blank=True)
    
#     class Meta:
#         db_table = 'treatment_plan_items'
#         ordering = ['treatment_plan', 'visit_number']
#         unique_together = ['treatment_plan', 'visit_number']
#         indexes = [
#             models.Index(fields=['treatment_plan', 'status']),
#             models.Index(fields=['status', 'scheduled_date']),
#             models.Index(fields=['scheduled_visit']),
#         ]
    
#     def __str__(self):
#         return f"{self.treatment_plan.plan_id} - Visit {self.visit_number}: {self.treatment.name}"
    
#     def save(self, *args, **kwargs):
#         # Auto-set actual_amount from treatment if not set
#         if not self.actual_amount and self.treatment:
#             self.actual_amount = self.treatment.total_price
#         super().save(*args, **kwargs)





# apps/treatments/models.py
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin
from decimal import Decimal
import json


class TreatmentCategory(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """Category of dental treatments"""
    
    class Meta:
        db_table = 'treatment_categories'
        verbose_name_plural = 'Treatment Categories'
        ordering = ['order', 'name']
    
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Icon class for UI")
    color = models.CharField(max_length=20, blank=True, default='#4CAF50', help_text="Hex color for UI")
    order = models.IntegerField(default=0, help_text="Display order in UI")
    is_active = models.BooleanField(default=True)
    
    # SEO/Reporting
    keywords = models.TextField(blank=True, help_text="SEO keywords")
    display_in_portal = models.BooleanField(default=True, help_text="Show in patient portal")
    
    def __str__(self):
        return f"{self.name} ({self.code})"


class Treatment(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """Individual dental treatment/procedure"""
    
    class Meta:
        db_table = 'treatments'
        ordering = ['category', 'order', 'name']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['code']),
            models.Index(fields=['base_price']),
            models.Index(fields=['popularity_score']),
        ]
    
    DIFFICULTY_LEVELS = [
        ('BASIC', 'Basic'),
        ('INTERMEDIATE', 'Intermediate'),
        ('ADVANCED', 'Advanced'),
        ('SPECIALIST', 'Specialist'),
        ('SURGICAL', 'Surgical'),
    ]
    
    DURATION_UNITS = [
        ('MINUTES', 'Minutes'),
        ('HOURS', 'Hours'),
        ('DAYS', 'Days'),
        ('SESSIONS', 'Sessions'),
    ]
    
    AGE_GROUPS = [
        ('CHILD', 'Child (0-12)'),
        ('TEEN', 'Teenager (13-19)'),
        ('ADULT', 'Adult (20-59)'),
        ('SENIOR', 'Senior (60+)'),
        ('ALL', 'All Ages'),
    ]
    
    # Basic Info
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=30, unique=True)
    display_name = models.CharField(max_length=200, blank=True, help_text="Display name for patients")
    category = models.ForeignKey(
        TreatmentCategory,
        on_delete=models.PROTECT,
        related_name='treatments'
    )
    
    # Pricing & Finance
    base_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    min_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Minimum price (for discounts)"
    )
    max_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum price"
    )
    
    # Commission/Fees
    doctor_fee_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        default=Decimal('30.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text="Doctor commission percentage"
    )
    assistant_fee_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    tax_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('18.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    
    # Operational Details
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_LEVELS, default='INTERMEDIATE')
    duration_value = models.PositiveIntegerField(default=30, help_text="Duration value")
    duration_unit = models.CharField(max_length=10, choices=DURATION_UNITS, default='MINUTES')
    num_sessions = models.PositiveIntegerField(default=1, help_text="Number of sessions required")
    recovery_days = models.PositiveIntegerField(default=0, help_text="Estimated recovery time")
    
    # Clinical Details
    description = models.TextField(blank=True)
    procedure_steps = models.TextField(blank=True)
    materials_required = models.JSONField(default=list, blank=True, help_text="List of materials with quantities")
    equipment_required = models.JSONField(default=list, blank=True, help_text="List of equipment needed")
    contraindications = models.TextField(blank=True, help_text="When not to perform this treatment")
    post_op_instructions = models.TextField(blank=True)
    success_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        default=Decimal('95.00'),
        help_text="Success rate percentage"
    )
    
    # Patient Demographics
    suitable_for_age = models.CharField(max_length=20, choices=AGE_GROUPS, default='ALL')
    suitable_for_gender = models.CharField(
        max_length=20,
        choices=[('MALE', 'Male'), ('FEMALE', 'Female'), ('ALL', 'All')],
        default='ALL'
    )
    medical_conditions = models.JSONField(
        default=list, 
        blank=True,
        help_text="Medical conditions that affect this treatment"
    )
    
    # Inventory & Lab
    requires_lab = models.BooleanField(default=False)
    lab_type = models.CharField(max_length=50, blank=True, help_text="Type of lab work needed")
    lab_days = models.PositiveIntegerField(default=0, help_text="Lab processing time")
    inventory_items = models.JSONField(
        default=list,
        blank=True,
        help_text="Inventory items consumed with quantities"
    )
    
    # Status & Analytics
    is_active = models.BooleanField(default=True)
    is_popular = models.BooleanField(default=False)
    popularity_score = models.IntegerField(default=0)
    order = models.IntegerField(default=0, help_text="Display order in lists")
    display_in_portal = models.BooleanField(default=True)
    
    # Metadata
    version = models.CharField(max_length=10, default='1.0')
    last_updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='treatments_last_updated_by'
    )
    
    def __str__(self):
        return f"{self.code}: {self.name}"
    
    @property
    def doctor_fee(self):
        """Calculate doctor's fee"""
        return (self.base_price * self.doctor_fee_percentage) / Decimal('100.00')
    
    @property
    def assistant_fee(self):
        """Calculate assistant's fee"""
        return (self.base_price * self.assistant_fee_percentage) / Decimal('100.00')
    
    @property
    def tax_amount(self):
        """Calculate tax"""
        return (self.base_price * self.tax_percentage) / Decimal('100.00')
    
    @property
    def total_price(self):
        """Total price including tax"""
        return self.base_price + self.tax_amount
    
    @property
    def duration_display(self):
        """Human readable duration"""
        if self.duration_unit == 'SESSIONS':
            return f"{self.num_sessions} session{'s' if self.num_sessions > 1 else ''}"
        return f"{self.duration_value} {self.duration_unit.lower()}"
    
    @property
    def clinic_cost(self):
        """Clinic's cost (price minus commissions)"""
        return self.base_price - self.doctor_fee - self.assistant_fee
    
    def calculate_price_for_age(self, age):
        """Calculate price based on patient age"""
        if self.suitable_for_age == 'CHILD' and age > 12:
            return self.base_price * Decimal('1.1')  # 10% more for adults
        elif self.suitable_for_age == 'ADULT' and age < 20:
            return self.base_price * Decimal('0.9')  # 10% less for children
        return self.base_price


class ToothChart(models.Model):
    """Dental tooth chart mapping"""
    
    class Meta:
        db_table = 'tooth_charts'
    
    TOOTH_NUMBERS = [(str(i), str(i)) for i in range(1, 33)]
    SURFACES = [
        ('OCCLUSAL', 'Occlusal'),
        ('MESIAL', 'Mesial'),
        ('DISTAL', 'Distal'),
        ('BUCCAL', 'Buccal'),
        ('LINGUAL', 'Lingual'),
        ('PALATAL', 'Palatal'),
        ('LABIAL', 'Labial'),
        ('INCISAL', 'Incisal'),
        ('CERVICAL', 'Cervical'),
    ]
    
    QUADRANTS = [
        (1, 'Upper Right'),
        (2, 'Upper Left'),
        (3, 'Lower Left'),
        (4, 'Lower Right'),
    ]
    
    tooth_number = models.CharField(max_length=3, choices=TOOTH_NUMBERS)
    quadrant = models.IntegerField(choices=QUADRANTS)
    fdi_notation = models.CharField(max_length=5, unique=True)
    universal_notation = models.CharField(max_length=5)
    name = models.CharField(max_length=100, help_text="Tooth name (e.g., Maxillary Right First Molar)")
    type = models.CharField(
        max_length=20,
        choices=[
            ('INCISOR', 'Incisor'),
            ('CANINE', 'Canine'),
            ('PREMOLAR', 'Premolar'),
            ('MOLAR', 'Molar'),
            ('WISDOM', 'Wisdom Tooth'),
        ]
    )
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Tooth {self.fdi_notation} - {self.name}"


class TreatmentPlan(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """Multi-visit treatment plan for a patient"""
    
    class Meta:
        db_table = 'treatment_plans'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['doctor', 'status']),
            models.Index(fields=['plan_id']),
            models.Index(fields=['status', 'estimated_start_date']),
            models.Index(fields=['branch', 'created_at']),
        ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PROPOSED', 'Proposed to Patient'),
        ('REVISED', 'Revised'),
        ('ACCEPTED', 'Accepted by Patient'),
        ('CONTRACT_SIGNED', 'Contract Signed'),
        ('IN_PROGRESS', 'In Progress'),
        ('ON_HOLD', 'On Hold'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('REFERRED', 'Referred to Specialist'),
    ]
    
    PRIORITY_CHOICES = [
        ('ROUTINE', 'Routine'),
        ('URGENT', 'Urgent'),
        ('EMERGENCY', 'Emergency'),
        ('ELECTIVE', 'Elective'),
    ]
    
    # Basic Info
    plan_id = models.CharField(max_length=50, unique=True, blank=True)
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
    branch = models.ForeignKey(
        'clinics.Branch',
        on_delete=models.PROTECT,
        related_name='treatment_plans'
    )
    referred_by = models.ForeignKey(
        'doctors.Doctor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referred_plans'
    )
    
    # Plan Details
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='ROUTINE')
    version = models.IntegerField(default=1, help_text="Plan version number")
    parent_plan = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revisions'
    )
    
    # Financial
    total_estimated_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_plan = models.JSONField(
        default=dict,
        blank=True,
        help_text="Payment schedule with dates and amounts"
    )
    
    # Insurance
    insurance_coverage = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    insurance_approved = models.BooleanField(default=False)
    insurance_notes = models.TextField(blank=True)
    
    # Timeline
    estimated_start_date = models.DateField(null=True, blank=True)
    estimated_end_date = models.DateField(null=True, blank=True)
    actual_start_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    next_review_date = models.DateField(null=True, blank=True)
    
    # Clinical
    diagnosis = models.TextField(blank=True)
    diagnosis_codes = models.JSONField(default=list, blank=True, help_text="ICD codes")
    treatment_goals = models.TextField(blank=True)
    clinical_notes = models.TextField(blank=True)
    pre_op_instructions = models.TextField(blank=True)
    post_op_instructions = models.TextField(blank=True)
    risks_and_complications = models.TextField(blank=True)
    
    # Dental Chart
    dental_chart = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON representation of dental chart with conditions"
    )
    
    # Documents
    consent_form_signed = models.BooleanField(default=False)
    consent_form_url = models.URLField(blank=True)
    xray_images = models.JSONField(default=list, blank=True, help_text="List of X-ray image URLs")
    
    # Analytics
    complexity_score = models.IntegerField(default=0, help_text="1-10 score of plan complexity")
    satisfaction_score = models.IntegerField(null=True, blank=True, help_text="Patient satisfaction 1-10")
    
    def __str__(self):
        return f"Plan {self.plan_id}: {self.name} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        if not self.plan_id:
            self.plan_id = self._generate_plan_id()
        
        # Calculate financials
        self.discount_amount = (self.total_estimated_amount * self.discount_percentage) / Decimal('100.00')
        self.final_amount = self.total_estimated_amount - self.discount_amount
        
        super().save(*args, **kwargs)
    
    def _generate_plan_id(self):
        """Generate TP-YYYYMM-XXXX format ID"""
        from datetime import datetime
        
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
        """Calculate progress based on completed items"""
        total_items = self.plan_items.count()
        if total_items == 0:
            return 0
        
        completed_items = self.plan_items.filter(status='COMPLETED').count()
        return round((completed_items / total_items) * 100, 2)
    
    @property
    def estimated_duration_days(self):
        """Calculate estimated duration in days"""
        if self.estimated_start_date and self.estimated_end_date:
            return (self.estimated_end_date - self.estimated_start_date).days
        return None
    
    def create_revision(self):
        """Create a new revision of this plan"""
        from django.utils import timezone
        
        # Create new plan as revision
        new_plan = TreatmentPlan.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            branch=self.branch,
            name=f"{self.name} (Revision {self.version + 1})",
            status='DRAFT',
            parent_plan=self,
            version=self.version + 1,
            # Copy other fields as needed
        )
        
        # Copy plan items
        for item in self.plan_items.all():
            TreatmentPlanItem.objects.create(
                treatment_plan=new_plan,
                treatment=item.treatment,
                visit_number=item.visit_number,
                tooth_number=item.tooth_number,
                surface=item.surface,
                notes=item.notes,
            )
        
        return new_plan


class TreatmentPlanItem(AuditFieldsMixin, models.Model):
    """Individual treatment within a plan"""
    
    class Meta:
        db_table = 'treatment_plan_items'
        ordering = ['treatment_plan', 'visit_number', 'order']
        unique_together = ['treatment_plan', 'visit_number']
        indexes = [
            models.Index(fields=['treatment_plan', 'status']),
            models.Index(fields=['status', 'scheduled_date']),
            models.Index(fields=['scheduled_visit']),
            models.Index(fields=['tooth_number']),
        ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('DEFERRED', 'Deferred'),
        ('POSTPONED', 'Postponed'),
    ]
    
    PHASE_CHOICES = [
        ('DIAGNOSTIC', 'Diagnostic'),
        ('PREVENTIVE', 'Preventive'),
        ('RESTORATIVE', 'Restorative'),
        ('SURGICAL', 'Surgical'),
        ('ORTHODONTIC', 'Orthodontic'),
        ('PROSTHETIC', 'Prosthetic'),
        ('MAINTENANCE', 'Maintenance'),
    ]
    
    # Basic Info
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
    order = models.IntegerField(default=0, help_text="Order within visit")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    phase = models.CharField(max_length=20, choices=PHASE_CHOICES, default='RESTORATIVE')
    scheduled_date = models.DateField(null=True, blank=True)
    scheduled_visit = models.ForeignKey(
        'visits.Visit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='treatment_plan_items'
    )
    depends_on = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dependencies',
        help_text="Item that must be completed before this one"
    )
    
    # Financial
    actual_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_applied = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_paid = models.BooleanField(default=False)
    payment_reference = models.CharField(max_length=100, blank=True)
    
    # Clinical Details
    tooth_number = models.CharField(max_length=20, blank=True)
    surface = models.CharField(max_length=50, blank=True)
    quadrant = models.IntegerField(choices=ToothChart.QUADRANTS, null=True, blank=True)
    tooth_condition = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('CARIES', 'Caries'),
            ('FRACTURE', 'Fracture'),
            ('ROOT_CANAL', 'Root Canal Treated'),
            ('MISSING', 'Missing'),
            ('IMPACTED', 'Impacted'),
            ('DISCOLORED', 'Discolored'),
            ('SENSITIVE', 'Sensitive'),
        ]
    )
    
    # Procedure Details
    materials_used = models.JSONField(default=list, blank=True, help_text="Materials actually used")
    equipment_used = models.JSONField(default=list, blank=True)
    procedure_notes = models.TextField(blank=True)
    complications = models.TextField(blank=True)
    anesthesia_type = models.CharField(max_length=50, blank=True)
    anesthesia_amount = models.CharField(max_length=50, blank=True)
    
    # Doctor & Staff
    performed_by = models.ForeignKey(
        'doctors.Doctor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='performed_treatments'
    )
    assistant = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assisted_treatments'
    )
    
    # Dates & Times
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    
    # Follow-up
    follow_up_required = models.BooleanField(default=False)
    follow_up_days = models.IntegerField(default=7, help_text="Days until follow-up")
    follow_up_notes = models.TextField(blank=True)
    
    # Quality
    quality_score = models.IntegerField(null=True, blank=True, help_text="1-10 quality score")
    patient_feedback = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.treatment_plan.plan_id} - Visit {self.visit_number}: {self.treatment.name}"
    
    def save(self, *args, **kwargs):
        # Auto-set actual_amount from treatment if not set
        if not self.actual_amount and self.treatment:
            self.actual_amount = self.treatment.total_price
        
        # Auto-set quadrant from tooth number
        if self.tooth_number and not self.quadrant:
            try:
                tooth_num = int(self.tooth_number)
                if 1 <= tooth_num <= 8:
                    self.quadrant = 1  # Upper Right
                elif 9 <= tooth_num <= 16:
                    self.quadrant = 2  # Upper Left
                elif 17 <= tooth_num <= 24:
                    self.quadrant = 3  # Lower Left
                elif 25 <= tooth_num <= 32:
                    self.quadrant = 4  # Lower Right
            except ValueError:
                pass
        
        super().save(*args, **kwargs)
    
    @property
    def duration_minutes(self):
        """Calculate actual duration in minutes"""
        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            return duration.total_seconds() / 60
        return None
    
    @property
    def doctor_commission(self):
        """Calculate doctor's commission for this item"""
        if self.actual_amount and self.treatment:
            return (self.actual_amount * self.treatment.doctor_fee_percentage) / Decimal('100.00')
        return Decimal('0.00')


class TreatmentNote(AuditFieldsMixin, models.Model):
    """Clinical notes for treatments"""
    
    class Meta:
        db_table = 'treatment_notes'
        ordering = ['-created_at']
    
    treatment_plan_item = models.ForeignKey(
        TreatmentPlanItem,
        on_delete=models.CASCADE,
        related_name='clinical_notes'
    )
    note_type = models.CharField(
        max_length=20,
        choices=[
            ('PRE_OP', 'Pre-operative'),
            ('INTRA_OP', 'Intra-operative'),
            ('POST_OP', 'Post-operative'),
            ('FOLLOW_UP', 'Follow-up'),
            ('COMPLICATION', 'Complication'),
            ('GENERAL', 'General'),
        ],
        default='GENERAL'
    )
    content = models.TextField()
    attachments = models.JSONField(default=list, blank=True, help_text="List of attached files")
    is_critical = models.BooleanField(default=False, help_text="Critical note requiring attention")
    
    def __str__(self):
        return f"Note for {self.treatment_plan_item} - {self.get_note_type_display()}"


class TreatmentTemplate(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """Template for common treatment combinations"""
    
    class Meta:
        db_table = 'treatment_templates'
        ordering = ['name']
    
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        TreatmentCategory,
        on_delete=models.PROTECT,
        related_name='templates'
    )
    treatments = models.ManyToManyField(
        Treatment,
        through='TemplateTreatment',
        related_name='templates'
    )
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.code}: {self.name}"


class TemplateTreatment(models.Model):
    """Treatment within a template"""
    
    class Meta:
        db_table = 'template_treatments'
        ordering = ['order']
        unique_together = ['template', 'treatment']
    
    template = models.ForeignKey(TreatmentTemplate, on_delete=models.CASCADE)
    treatment = models.ForeignKey(Treatment, on_delete=models.CASCADE)
    order = models.IntegerField(default=0)
    visit_number = models.IntegerField(default=1)
    
    def __str__(self):
        return f"{self.template.name} - {self.treatment.name}"