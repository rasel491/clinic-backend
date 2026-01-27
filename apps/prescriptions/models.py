# # old model
# from django.db import models
# from core.mixins.audit_fields import AuditFieldsMixin
# from core.mixins.soft_delete import SoftDeleteMixin
# from decimal import Decimal
# from django.utils import timezone

# class Prescription(AuditFieldsMixin, SoftDeleteMixin, models.Model):
#     """Doctor's prescription for a patient"""
    
#     STATUS_CHOICES = [
#         ('DRAFT', 'Draft'),
#         ('ISSUED', 'Issued'),
#         ('DISPENSED', 'Dispensed'),
#         ('COMPLETED', 'Completed'),
#         ('CANCELLED', 'Cancelled'),
#     ]
    
#     PRESCRIPTION_TYPE = [
#         ('NEW', 'New Prescription'),
#         ('REFILL', 'Refill'),
#         ('RENEWAL', 'Renewal'),
#     ]
    
#     visit = models.OneToOneField(
#         'visits.Visit',
#         on_delete=models.PROTECT,
#         related_name='prescription'
#     )
#     patient = models.ForeignKey(
#         'patients.Patient',
#         on_delete=models.PROTECT,
#         related_name='prescriptions'
#     )
#     doctor = models.ForeignKey(
#         'doctors.Doctor',
#         on_delete=models.PROTECT,
#         related_name='prescriptions'
#     )
    
#     # Prescription info
#     prescription_id = models.CharField(max_length=50, unique=True, blank=True)
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
#     prescription_type = models.CharField(max_length=20, choices=PRESCRIPTION_TYPE, default='NEW')
    
#     # Clinical details
#     diagnosis = models.TextField(blank=True)
#     symptoms = models.TextField(blank=True)
#     clinical_findings = models.TextField(blank=True)
#     advice = models.TextField(blank=True)
    
#     # Follow-up
#     next_review_date = models.DateField(null=True, blank=True)
#     follow_up_instructions = models.TextField(blank=True)
    
#     # Pharmacy
#     pharmacy_notes = models.TextField(blank=True)
#     is_pharmacy_copy_sent = models.BooleanField(default=False)
#     pharmacy_sent_at = models.DateTimeField(null=True, blank=True)
    
#     # Digital signature
#     doctor_signature = models.TextField(blank=True)
#     signed_at = models.DateTimeField(null=True, blank=True)
    
#     # PDF storage
#     pdf_file = models.FileField(upload_to='prescriptions/%Y/%m/%d/', null=True, blank=True)
#     pdf_hash = models.CharField(max_length=64, blank=True, help_text="SHA-256 hash for verification")
    
#     # QR code for pharmacy verification
#     qr_code = models.ImageField(upload_to='prescription_qr/', null=True, blank=True)
#     verification_code = models.CharField(max_length=32, unique=True, blank=True)
    
#     class Meta:
#         db_table = 'prescriptions'
#         ordering = ['-created_at']
#         indexes = [
#             models.Index(fields=['prescription_id']),
#             models.Index(fields=['patient', 'status']),
#             models.Index(fields=['doctor', 'status']),
#             models.Index(fields=['visit']),
#             models.Index(fields=['status', 'next_review_date']),
#             models.Index(fields=['verification_code']),
#         ]
    
#     def __str__(self):
#         return f"RX-{self.prescription_id}: {self.patient} ({self.get_status_display()})"
    
#     def save(self, *args, **kwargs):
#         if not self.prescription_id:
#             self.prescription_id = self._generate_prescription_id()
        
#         if not self.verification_code:
#             import secrets
#             self.verification_code = secrets.token_hex(16)
        
#         super().save(*args, **kwargs)
    
#     def _generate_prescription_id(self):
#         """Generate RX-YYYYMMDD-XXXX format ID"""
#         from datetime import datetime
#         from django.db.models import Count
        
#         today = datetime.now().strftime('%Y%m%d')
        
#         last_prescription = Prescription.objects.filter(
#             prescription_id__startswith=f'RX-{today}-'
#         ).order_by('prescription_id').last()
        
#         if last_prescription:
#             last_num = int(last_prescription.prescription_id.split('-')[-1])
#             new_num = last_num + 1
#         else:
#             new_num = 1
        
#         return f'RX-{today}-{new_num:04d}'
    
#     @property
#     def is_signed(self):
#         return bool(self.doctor_signature and self.signed_at)
    
#     @property
#     def total_medicines(self):
#         return self.medicines.count()
    
#     @property
#     def is_dispensable(self):
#         return self.status in ['ISSUED', 'DISPENSED']
    
#     def mark_issued(self):
#         """Mark prescription as officially issued"""
#         if self.status == 'DRAFT':
#             self.status = 'ISSUED'
#             self.signed_at = timezone.now()
#             self.save()
    
#     def generate_pdf(self):
#         """Generate PDF version of prescription"""
#         # This would be implemented in a service
#         pass


# class Medicine(models.Model):
#     """Medicine master data"""
    
#     TYPE_CHOICES = [
#         ('TABLET', 'Tablet'),
#         ('CAPSULE', 'Capsule'),
#         ('SYRUP', 'Syrup'),
#         ('INJECTION', 'Injection'),
#         ('OINTMENT', 'Ointment'),
#         ('DROPS', 'Drops'),
#         ('INHALER', 'Inhaler'),
#         ('OTHER', 'Other'),
#     ]
    
#     name = models.CharField(max_length=200)
#     generic_name = models.CharField(max_length=200, blank=True)
#     brand = models.CharField(max_length=100, blank=True)
#     medicine_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='TABLET')
    
#     # Dosage forms
#     strength = models.CharField(max_length=100, blank=True, help_text="e.g., 500mg, 10mg/ml")
#     unit = models.CharField(max_length=50, blank=True, help_text="e.g., mg, ml, g")
    
#     # Classification
#     schedule = models.CharField(max_length=10, blank=True, help_text="H1, H, G, etc.")
#     is_controlled = models.BooleanField(default=False)
    
#     # Stock info
#     default_pack_size = models.CharField(max_length=50, blank=True)
#     default_mrp = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
#     # Metadata
#     is_active = models.BooleanField(default=True)
#     notes = models.TextField(blank=True)
    
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         db_table = 'medicines'
#         ordering = ['name']
#         indexes = [
#             models.Index(fields=['name']),
#             models.Index(fields=['generic_name']),
#             models.Index(fields=['medicine_type', 'is_active']),
#             models.Index(fields=['is_controlled']),
#         ]
    
#     def __str__(self):
#         return f"{self.name} ({self.generic_name}) {self.strength}"


# class PrescriptionMedicine(AuditFieldsMixin, models.Model):
#     """Medicine prescribed to a patient"""
    
#     FREQUENCY_CHOICES = [
#         ('OD', 'Once daily'),
#         ('BD', 'Twice daily'),
#         ('TDS', 'Thrice daily'),
#         ('QID', 'Four times daily'),
#         ('HS', 'At bedtime'),
#         ('SOS', 'As needed'),
#         ('STAT', 'Immediately once'),
#         ('PRN', 'When required'),
#     ]
    
#     DURATION_UNITS = [
#         ('DAYS', 'Days'),
#         ('WEEKS', 'Weeks'),
#         ('MONTHS', 'Months'),
#         ('UNTIL_FINISHED', 'Until finished'),
#     ]
    
#     ROUTE_CHOICES = [
#         ('ORAL', 'Oral'),
#         ('TOPICAL', 'Topical'),
#         ('INHALATION', 'Inhalation'),
#         ('INJECTION', 'Injection'),
#         ('RECTAL', 'Rectal'),
#         ('SUBLINGUAL', 'Sublingual'),
#         ('OTHER', 'Other'),
#     ]
    
#     prescription = models.ForeignKey(
#         Prescription,
#         on_delete=models.CASCADE,
#         related_name='medicines'
#     )
#     medicine = models.ForeignKey(
#         Medicine,
#         on_delete=models.PROTECT,
#         related_name='prescriptions'
#     )
    
#     # Dosage instructions
#     dosage = models.CharField(max_length=100, help_text="e.g., 1 tablet, 5ml")
#     frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES)
#     route = models.CharField(max_length=20, choices=ROUTE_CHOICES, default='ORAL')
    
#     # Duration
#     duration_value = models.PositiveIntegerField(default=7)
#     duration_unit = models.CharField(max_length=20, choices=DURATION_UNITS, default='DAYS')
    
#     # Timing
#     before_food = models.BooleanField(default=False, help_text="Take before food")
#     after_food = models.BooleanField(default=True, help_text="Take after food")
#     specific_timing = models.CharField(max_length=100, blank=True, help_text="e.g., Morning, Evening")
    
#     # Quantity
#     quantity = models.DecimalField(max_digits=10, decimal_places=2, help_text="Total quantity to dispense")
#     unit = models.CharField(max_length=20, blank=True, help_text="e.g., tablets, ml, bottles")
    
#     # Substitution
#     allow_generic = models.BooleanField(default=True, help_text="Allow generic substitution")
#     allow_brand = models.BooleanField(default=True, help_text="Allow brand substitution")
    
#     # Special instructions
#     instructions = models.TextField(blank=True)
#     precautions = models.TextField(blank=True)
    
#     # For repeats
#     is_repeat = models.BooleanField(default=False)
#     repeat_count = models.PositiveIntegerField(default=0, help_text="Number of repeats allowed")
#     repeat_interval = models.PositiveIntegerField(default=0, help_text="Days between repeats")
    
#     class Meta:
#         db_table = 'prescription_medicines'
#         ordering = ['prescription', 'id']
#         indexes = [
#             models.Index(fields=['prescription', 'medicine']),
#         ]
    
#     def __str__(self):
#         return f"{self.medicine.name} for {self.prescription.prescription_id}"
    
#     @property
#     def duration_display(self):
#         return f"{self.duration_value} {self.duration_unit.lower()}"
    
#     @property
#     def timing_display(self):
#         if self.before_food:
#             return "Before food"
#         elif self.after_food:
#             return "After food"
#         return self.specific_timing or ""


# class PrescriptionDispense(models.Model):
#     """Record of medicine dispensing by pharmacy"""
    
#     prescription_medicine = models.ForeignKey(
#         PrescriptionMedicine,
#         on_delete=models.CASCADE,
#         related_name='dispenses'
#     )
    
#     # Dispensing info
#     dispense_id = models.CharField(max_length=50, unique=True, blank=True)
#     dispensed_date = models.DateField(auto_now_add=True)
#     dispensed_quantity = models.DecimalField(max_digits=10, decimal_places=2)
#     batch_number = models.CharField(max_length=100, blank=True)
#     expiry_date = models.DateField(null=True, blank=True)
    
#     # Pharmacy info
#     pharmacy_name = models.CharField(max_length=200, blank=True)
#     pharmacist_name = models.CharField(max_length=100, blank=True)
#     pharmacy_license = models.CharField(max_length=100, blank=True)
    
#     # Verification
#     verified_by = models.ForeignKey(
#         'accounts.User',
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='verified_dispenses'
#     )
#     verification_method = models.CharField(max_length=50, blank=True, help_text="QR scan, Manual, etc.")
    
#     created_at = models.DateTimeField(auto_now_add=True)
    
#     class Meta:
#         db_table = 'prescription_dispenses'
#         ordering = ['-dispensed_date']
#         indexes = [
#             models.Index(fields=['prescription_medicine', 'dispensed_date']),
#             models.Index(fields=['dispense_id']),
#             models.Index(fields=['pharmacy_name']),
#         ]
    
#     def __str__(self):
#         return f"Dispense {self.dispense_id}: {self.prescription_medicine.medicine.name}"
    
#     def save(self, *args, **kwargs):
#         if not self.dispense_id:
#             self.dispense_id = self._generate_dispense_id()
#         super().save(*args, **kwargs)
    
#     def _generate_dispense_id(self):
#         """Generate DISP-YYYYMMDD-XXXX format ID"""
#         from datetime import datetime
        
#         today = datetime.now().strftime('%Y%m%d')
        
#         last_dispense = PrescriptionDispense.objects.filter(
#             dispense_id__startswith=f'DISP-{today}-'
#         ).order_by('dispense_id').last()
        
#         if last_dispense:
#             last_num = int(last_dispense.dispense_id.split('-')[-1])
#             new_num = last_num + 1
#         else:
#             new_num = 1
        
#         return f'DISP-{today}-{new_num:04d}'

# apps/prescriptions/models.py

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin


class Prescription(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """Digital prescription issued by a doctor"""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ISSUED', 'Issued'),
        ('DISPENSED', 'Dispensed'),
        ('CANCELLED', 'Cancelled'),
        ('EXPIRED', 'Expired'),
    ]
    
    PRESCRIPTION_TYPE_CHOICES = [
        ('NEW', 'New Prescription'),
        ('REFILL', 'Refill'),
        ('RENEWAL', 'Renewal'),
    ]
    
    prescription_id = models.CharField(max_length=50, unique=True, blank=True)
    prescription_type = models.CharField(
        max_length=20, 
        choices=PRESCRIPTION_TYPE_CHOICES, 
        default='NEW'
    )
    
    # Relationships
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.PROTECT,
        related_name='prescriptions'
    )
    doctor = models.ForeignKey(
        'doctors.Doctor',
        on_delete=models.PROTECT,
        related_name='prescriptions'
    )
    visit = models.ForeignKey(
        'visits.Visit',  # Will create visits app later
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prescriptions'
    )
    
    # Prescription details
    diagnosis = models.TextField(blank=True, help_text="Clinical diagnosis")
    notes = models.TextField(blank=True, help_text="Doctor's notes")
    instructions = models.TextField(blank=True, help_text="General instructions for patient")
    
    # Status & Dates
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    issue_date = models.DateField(default=timezone.now)
    valid_until = models.DateField()
    
    # Refill information
    is_refillable = models.BooleanField(default=False)
    max_refills = models.PositiveIntegerField(default=0)
    refills_remaining = models.PositiveIntegerField(default=0)
    last_refill_date = models.DateField(null=True, blank=True)
    
    # Digital signature
    is_signed = models.BooleanField(default=False)
    signed_at = models.DateTimeField(null=True, blank=True)
    
    # Pharmacy details
    dispensing_pharmacy = models.ForeignKey(
        'clinics.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dispensed_prescriptions'
    )
    dispensed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dispensed_prescriptions'
    )
    dispensed_at = models.DateTimeField(null=True, blank=True)
    
    # Billing
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    insurance_covered = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    patient_payable = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    class Meta:
        db_table = 'prescriptions'
        ordering = ['-issue_date', '-created_at']
        indexes = [
            models.Index(fields=['prescription_id']),
            models.Index(fields=['patient', 'doctor', 'issue_date']),
            models.Index(fields=['status', 'valid_until']),
            models.Index(fields=['doctor', 'issue_date']),
            models.Index(fields=['is_refillable', 'refills_remaining']),
        ]
        verbose_name = 'Prescription'
        verbose_name_plural = 'Prescriptions'
    
    def __str__(self):
        return f"{self.prescription_id} - {self.patient.full_name}"
    
    def clean(self):
        """Validate prescription data"""
        super().clean()
        
        if self.valid_until and self.valid_until < self.issue_date:
            raise ValidationError({
                'valid_until': 'Valid until date must be after issue date'
            })
        
        if self.refills_remaining > self.max_refills:
            raise ValidationError({
                'refills_remaining': 'Refills remaining cannot exceed maximum refills'
            })
        
        # Check if doctor is active and license is valid
        if not self.doctor.is_active:
            raise ValidationError({
                'doctor': 'Doctor is not active'
            })
        
        if not self.doctor.is_license_valid:
            raise ValidationError({
                'doctor': 'Doctor license has expired'
            })
    
    def save(self, *args, **kwargs):
        if not self.prescription_id:
            self.prescription_id = self._generate_prescription_id()
        
        # Set default valid_until (30 days from issue)
        if not self.valid_until:
            self.valid_until = self.issue_date + timedelta(days=30)
        
        # Auto-calculate patient payable
        self.patient_payable = self.total_amount - self.insurance_covered
        
        # Update status based on dates
        if self.status != 'CANCELLED' and self.valid_until < timezone.now().date():
            self.status = 'EXPIRED'
        
        super().save(*args, **kwargs)
    
    def _generate_prescription_id(self):
        """Generate RX-YYYYMM-XXXX format ID"""
        from django.db.models import Count
        from datetime import datetime
        
        now = datetime.now()
        year_month = now.strftime('%Y%m')
        
        current_month_count = Prescription.objects.filter(
            prescription_id__startswith=f'RX-{year_month}-'
        ).count() + 1
        
        return f'RX-{year_month}-{current_month_count:04d}'
    
    @property
    def is_valid(self):
        """Check if prescription is still valid"""
        if self.status in ['CANCELLED', 'EXPIRED']:
            return False
        return self.valid_until >= timezone.now().date()
    
    @property
    def can_be_dispensed(self):
        """Check if prescription can be dispensed"""
        return (
            self.is_valid and
            self.status in ['ISSUED', 'DISPENSED'] and
            (self.is_refillable or self.refills_remaining > 0)
        )
    
    @property
    def items_count(self):
        """Count of prescription items"""
        return self.items.count()
    
    @property
    def total_quantity(self):
        """Total quantity of all medications"""
        return self.items.aggregate(total=models.Sum('quantity'))['total'] or 0
    
    def mark_as_dispensed(self, pharmacy, dispensed_by):
        """Mark prescription as dispensed"""
        if not self.can_be_dispensed:
            raise ValidationError("Prescription cannot be dispensed")
        
        self.status = 'DISPENSED'
        self.dispensing_pharmacy = pharmacy
        self.dispensed_by = dispensed_by
        self.dispensed_at = timezone.now()
        
        if self.is_refillable and self.refills_remaining > 0:
            self.refills_remaining -= 1
            self.last_refill_date = timezone.now().date()
        
        self.save()
    
    def refill(self):
        """Refill the prescription"""
        if not self.is_refillable:
            raise ValidationError("This prescription is not refillable")
        
        if self.refills_remaining <= 0:
            raise ValidationError("No refills remaining")
        
        # Create a new prescription as refill
        refill_prescription = Prescription.objects.create(
            prescription_type='REFILL',
            patient=self.patient,
            doctor=self.doctor,
            visit=self.visit,
            diagnosis=self.diagnosis,
            notes=f"Refill of {self.prescription_id}",
            instructions=self.instructions,
            status='ISSUED',
            issue_date=timezone.now().date(),
            valid_until=timezone.now().date() + timedelta(days=30),
            is_refillable=self.is_refillable,
            max_refills=self.max_refills - 1,
            refills_remaining=self.refills_remaining - 1,
            total_amount=self.total_amount,
            insurance_covered=self.insurance_covered,
            patient_payable=self.patient_payable
        )
        
        # Copy prescription items
        for item in self.items.all():
            PrescriptionItem.objects.create(
                prescription=refill_prescription,
                medication=item.medication,
                dosage=item.dosage,
                frequency=item.frequency,
                duration=item.duration,
                quantity=item.quantity,
                instructions=item.instructions,
                unit_price=item.unit_price
            )
        
        # Update current prescription
        self.refills_remaining -= 1
        self.last_refill_date = timezone.now().date()
        self.save()
        
        return refill_prescription


class Medication(models.Model):
    """Medication master data"""
    
    CATEGORY_CHOICES = [
        ('ANTIBIOTIC', 'Antibiotic'),
        ('ANALGESIC', 'Analgesic (Pain Killer)'),
        ('ANTI_INFLAMMATORY', 'Anti-inflammatory'),
        ('ANTISEPTIC', 'Antiseptic'),
        ('ANESTHETIC', 'Anesthetic'),
        ('FILLING', 'Filling Material'),
        ('IMPLANT', 'Implant'),
        ('ORTHODONTIC', 'Orthodontic'),
        ('PROSTHETIC', 'Prosthetic'),
        ('HYGIENE', 'Oral Hygiene'),
        ('OTHER', 'Other'),
    ]
    
    FORM_CHOICES = [
        ('TABLET', 'Tablet'),
        ('CAPSULE', 'Capsule'),
        ('SYRUP', 'Syrup'),
        ('INJECTION', 'Injection'),
        ('OINTMENT', 'Ointment'),
        ('CREAM', 'Cream'),
        ('GEL', 'Gel'),
        ('MOUTHWASH', 'Mouthwash'),
        ('PASTE', 'Paste'),
        ('POWDER', 'Powder'),
        ('SPRAY', 'Spray'),
        ('DROPS', 'Drops'),
        ('LOZENGE', 'Lozenge'),
        ('OTHER', 'Other'),
    ]
    
    medicine_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    generic_name = models.CharField(max_length=200, blank=True)
    brand = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    form = models.CharField(max_length=50, choices=FORM_CHOICES)
    strength = models.CharField(max_length=100, blank=True)
    unit = models.CharField(max_length=50, default='Unit')
    
    # Stock information
    in_stock = models.BooleanField(default=True)
    current_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    min_stock_level = models.DecimalField(max_digits=10, decimal_places=2, default=10)
    max_stock_level = models.DecimalField(max_digits=10, decimal_places=2, default=100)
    
    # Pricing
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Medical information
    indications = models.TextField(blank=True)
    contraindications = models.TextField(blank=True)
    side_effects = models.TextField(blank=True)
    dosage_instructions = models.TextField(blank=True)
    storage_instructions = models.TextField(blank=True)
    
    # Regulatory
    requires_prescription = models.BooleanField(default=True)
    schedule = models.CharField(max_length=10, blank=True)  # H, H1, X, etc.
    mfg_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    batch_number = models.CharField(max_length=100, blank=True)
    
    # Active status
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'medications'
        ordering = ['name', 'brand']
        indexes = [
            models.Index(fields=['medicine_id']),
            models.Index(fields=['name', 'generic_name']),
            models.Index(fields=['category']),
            models.Index(fields=['requires_prescription', 'is_active']),
            models.Index(fields=['in_stock', 'current_stock']),
        ]
        verbose_name = 'Medication'
        verbose_name_plural = 'Medications'
    
    def __str__(self):
        return f"{self.name} ({self.brand}) - {self.strength}"
    
    def clean(self):
        """Validate medication data"""
        super().clean()
        
        if self.expiry_date and self.mfg_date and self.expiry_date <= self.mfg_date:
            raise ValidationError({
                'expiry_date': 'Expiry date must be after manufacturing date'
            })
        
        if self.current_stock < 0:
            raise ValidationError({
                'current_stock': 'Stock cannot be negative'
            })
        
        if self.unit_price < 0:
            raise ValidationError({
                'unit_price': 'Price cannot be negative'
            })
    
    @property
    def is_expired(self):
        """Check if medication is expired"""
        if not self.expiry_date:
            return False
        return self.expiry_date < timezone.now().date()
    
    @property
    def stock_status(self):
        """Get stock status"""
        if self.current_stock <= 0:
            return 'OUT_OF_STOCK'
        elif self.current_stock <= self.min_stock_level:
            return 'LOW_STOCK'
        else:
            return 'IN_STOCK'
    
    @property
    def needs_restocking(self):
        """Check if medication needs restocking"""
        return self.current_stock <= self.min_stock_level
    
    def update_stock(self, quantity, action='add'):
        """Update stock quantity"""
        if action == 'add':
            self.current_stock += Decimal(str(quantity))
        elif action == 'subtract':
            if self.current_stock < quantity:
                raise ValidationError(f"Insufficient stock. Available: {self.current_stock}")
            self.current_stock -= Decimal(str(quantity))
        
        self.in_stock = self.current_stock > 0
        self.save(update_fields=['current_stock', 'in_stock', 'updated_at'])


class PrescriptionItem(AuditFieldsMixin, models.Model):
    """Individual medication item in a prescription"""
    
    FREQUENCY_CHOICES = [
        ('OD', 'Once daily'),
        ('BD', 'Twice daily'),
        ('TDS', 'Three times daily'),
        ('QID', 'Four times daily'),
        ('QHS', 'At bedtime'),
        ('PRN', 'As needed'),
        ('STAT', 'Immediately'),
        ('Q4H', 'Every 4 hours'),
        ('Q6H', 'Every 6 hours'),
        ('Q8H', 'Every 8 hours'),
        ('Q12H', 'Every 12 hours'),
        ('QW', 'Once a week'),
        ('BIW', 'Twice a week'),
        ('TIW', 'Three times a week'),
    ]
    
    DURATION_UNIT_CHOICES = [
        ('DAYS', 'Days'),
        ('WEEKS', 'Weeks'),
        ('MONTHS', 'Months'),
    ]
    
    prescription = models.ForeignKey(
        Prescription,
        on_delete=models.CASCADE,
        related_name='items'
    )
    medication = models.ForeignKey(
        Medication,
        on_delete=models.PROTECT,
        related_name='prescription_items'
    )
    
    # Dosage information
    dosage = models.CharField(max_length=100, help_text="e.g., 500mg, 1 tablet")
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='BD')
    duration = models.PositiveIntegerField(default=7, help_text="Duration value")
    duration_unit = models.CharField(max_length=10, choices=DURATION_UNIT_CHOICES, default='DAYS')
    
    # Quantity & Instructions
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    instructions = models.TextField(blank=True, help_text="Specific instructions for this medication")
    
    # Pricing
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Dispensing
    is_dispensed = models.BooleanField(default=False)
    dispensed_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    dispensed_at = models.DateTimeField(null=True, blank=True)
    dispensed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dispensed_items'
    )
    
    class Meta:
        db_table = 'prescription_items'
        ordering = ['prescription', 'created_at']
        indexes = [
            models.Index(fields=['prescription', 'medication']),
            models.Index(fields=['is_dispensed']),
        ]
        verbose_name = 'Prescription Item'
        verbose_name_plural = 'Prescription Items'
    
    def __str__(self):
        return f"{self.medication.name} - {self.prescription.prescription_id}"
    
    def clean(self):
        """Validate prescription item"""
        super().clean()
        
        if self.quantity <= 0:
            raise ValidationError({
                'quantity': 'Quantity must be greater than 0'
            })
        
        if self.dispensed_quantity > self.quantity:
            raise ValidationError({
                'dispensed_quantity': 'Dispensed quantity cannot exceed prescribed quantity'
            })
    
    def save(self, *args, **kwargs):
        # Calculate total price
        self.total_price = self.quantity * self.unit_price
        
        # Auto-set unit price from medication if not set
        if not self.unit_price and self.medication:
            self.unit_price = self.medication.unit_price
        
        super().save(*args, **kwargs)
        
        # Update prescription total amount
        if self.prescription:
            self.prescription.total_amount = self.prescription.items.aggregate(
                total=models.Sum('total_price')
            )['total'] or 0
            self.prescription.save(update_fields=['total_amount', 'updated_at'])
    
    @property
    def total_duration_days(self):
        """Calculate total duration in days"""
        multiplier = {
            'DAYS': 1,
            'WEEKS': 7,
            'MONTHS': 30,  # Approximate
        }
        return self.duration * multiplier.get(self.duration_unit, 1)
    
    @property
    def remaining_quantity(self):
        """Calculate remaining quantity to be dispensed"""
        return self.quantity - self.dispensed_quantity
    
    @property
    def is_fully_dispensed(self):
        """Check if item is fully dispensed"""
        return self.dispensed_quantity >= self.quantity
    
    def dispense(self, quantity, dispensed_by):
        """Dispense medication"""
        remaining = self.remaining_quantity
        
        if quantity <= 0:
            raise ValidationError("Dispense quantity must be greater than 0")
        
        if quantity > remaining:
            raise ValidationError(f"Cannot dispense more than remaining quantity: {remaining}")
        
        self.dispensed_quantity += quantity
        self.is_dispensed = self.dispensed_quantity >= self.quantity
        self.dispensed_by = dispensed_by
        self.dispensed_at = timezone.now()
        self.save()
        
        # Update medication stock
        self.medication.update_stock(quantity, action='subtract')


class PrescriptionTemplate(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """Reusable prescription templates for common conditions"""
    
    SPECIALIZATION_CHOICES = [
        ('GENERAL', 'General Dentistry'),
        ('ORTHO', 'Orthodontics'),
        ('PERIO', 'Periodontics'),
        ('ENDO', 'Endodontics'),
        ('PEDO', 'Pediatric Dentistry'),
        ('SURG', 'Oral Surgery'),
        ('PROS', 'Prosthodontics'),
        ('ALL', 'All Specializations'),
    ]
    
    template_id = models.CharField(max_length=50, unique=True, blank=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Template specialization
    specialization = models.CharField(
        max_length=50, 
        choices=SPECIALIZATION_CHOICES, 
        default='GENERAL'
    )
    
    # Common diagnoses this template is for
    diagnoses = models.TextField(blank=True, help_text="Common diagnoses (comma-separated)")
    
    # Template content
    default_diagnosis = models.TextField(blank=True)
    default_notes = models.TextField(blank=True)
    default_instructions = models.TextField(blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    usage_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'prescription_templates'
        ordering = ['name']
        indexes = [
            models.Index(fields=['template_id']),
            models.Index(fields=['specialization', 'is_active']),
        ]
        verbose_name = 'Prescription Template'
        verbose_name_plural = 'Prescription Templates'
    
    def __str__(self):
        return f"{self.name} ({self.get_specialization_display()})"
    
    def save(self, *args, **kwargs):
        if not self.template_id:
            self.template_id = self._generate_template_id()
        super().save(*args, **kwargs)
    
    def _generate_template_id(self):
        """Generate TEMP-XXXX format ID"""
        from django.db.models import Count
        
        count = PrescriptionTemplate.objects.count() + 1
        return f'TEMP-{count:04d}'
    
    def increment_usage(self):
        """Increment usage count"""
        self.usage_count += 1
        self.save(update_fields=['usage_count', 'updated_at'])


class TemplateMedication(models.Model):
    """Medications in a prescription template"""
    
    template = models.ForeignKey(
        PrescriptionTemplate,
        on_delete=models.CASCADE,
        related_name='medications'
    )
    medication = models.ForeignKey(
        Medication,
        on_delete=models.CASCADE,
        related_name='template_medications'
    )
    
    # Default values for this medication in the template
    default_dosage = models.CharField(max_length=100, default='As directed')
    default_frequency = models.CharField(max_length=20, choices=PrescriptionItem.FREQUENCY_CHOICES, default='BD')
    default_duration = models.PositiveIntegerField(default=7)
    default_duration_unit = models.CharField(
        max_length=10, 
        choices=PrescriptionItem.DURATION_UNIT_CHOICES, 
        default='DAYS'
    )
    default_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    default_instructions = models.TextField(blank=True)
    
    # Order in the template
    display_order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'template_medications'
        ordering = ['template', 'display_order']
        unique_together = ['template', 'medication']
        verbose_name = 'Template Medication'
        verbose_name_plural = 'Template Medications'
    
    def __str__(self):
        return f"{self.medication.name} in {self.template.name}"