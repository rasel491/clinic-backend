
from django.db import models
from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin
from decimal import Decimal
from django.utils import timezone

class Prescription(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """Doctor's prescription for a patient"""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('ISSUED', 'Issued'),
        ('DISPENSED', 'Dispensed'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PRESCRIPTION_TYPE = [
        ('NEW', 'New Prescription'),
        ('REFILL', 'Refill'),
        ('RENEWAL', 'Renewal'),
    ]
    
    visit = models.OneToOneField(
        'visits.Visit',
        on_delete=models.PROTECT,
        related_name='prescription'
    )
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
    
    # Prescription info
    prescription_id = models.CharField(max_length=50, unique=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    prescription_type = models.CharField(max_length=20, choices=PRESCRIPTION_TYPE, default='NEW')
    
    # Clinical details
    diagnosis = models.TextField(blank=True)
    symptoms = models.TextField(blank=True)
    clinical_findings = models.TextField(blank=True)
    advice = models.TextField(blank=True)
    
    # Follow-up
    next_review_date = models.DateField(null=True, blank=True)
    follow_up_instructions = models.TextField(blank=True)
    
    # Pharmacy
    pharmacy_notes = models.TextField(blank=True)
    is_pharmacy_copy_sent = models.BooleanField(default=False)
    pharmacy_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Digital signature
    doctor_signature = models.TextField(blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    
    # PDF storage
    pdf_file = models.FileField(upload_to='prescriptions/%Y/%m/%d/', null=True, blank=True)
    pdf_hash = models.CharField(max_length=64, blank=True, help_text="SHA-256 hash for verification")
    
    # QR code for pharmacy verification
    qr_code = models.ImageField(upload_to='prescription_qr/', null=True, blank=True)
    verification_code = models.CharField(max_length=32, unique=True, blank=True)
    
    class Meta:
        db_table = 'prescriptions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['prescription_id']),
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['doctor', 'status']),
            models.Index(fields=['visit']),
            models.Index(fields=['status', 'next_review_date']),
            models.Index(fields=['verification_code']),
        ]
    
    def __str__(self):
        return f"RX-{self.prescription_id}: {self.patient} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        if not self.prescription_id:
            self.prescription_id = self._generate_prescription_id()
        
        if not self.verification_code:
            import secrets
            self.verification_code = secrets.token_hex(16)
        
        super().save(*args, **kwargs)
    
    def _generate_prescription_id(self):
        """Generate RX-YYYYMMDD-XXXX format ID"""
        from datetime import datetime
        from django.db.models import Count
        
        today = datetime.now().strftime('%Y%m%d')
        
        last_prescription = Prescription.objects.filter(
            prescription_id__startswith=f'RX-{today}-'
        ).order_by('prescription_id').last()
        
        if last_prescription:
            last_num = int(last_prescription.prescription_id.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f'RX-{today}-{new_num:04d}'
    
    @property
    def is_signed(self):
        return bool(self.doctor_signature and self.signed_at)
    
    @property
    def total_medicines(self):
        return self.medicines.count()
    
    @property
    def is_dispensable(self):
        return self.status in ['ISSUED', 'DISPENSED']
    
    def mark_issued(self):
        """Mark prescription as officially issued"""
        if self.status == 'DRAFT':
            self.status = 'ISSUED'
            self.signed_at = timezone.now()
            self.save()
    
    def generate_pdf(self):
        """Generate PDF version of prescription"""
        # This would be implemented in a service
        pass


class Medicine(models.Model):
    """Medicine master data"""
    
    TYPE_CHOICES = [
        ('TABLET', 'Tablet'),
        ('CAPSULE', 'Capsule'),
        ('SYRUP', 'Syrup'),
        ('INJECTION', 'Injection'),
        ('OINTMENT', 'Ointment'),
        ('DROPS', 'Drops'),
        ('INHALER', 'Inhaler'),
        ('OTHER', 'Other'),
    ]
    
    name = models.CharField(max_length=200)
    generic_name = models.CharField(max_length=200, blank=True)
    brand = models.CharField(max_length=100, blank=True)
    medicine_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='TABLET')
    
    # Dosage forms
    strength = models.CharField(max_length=100, blank=True, help_text="e.g., 500mg, 10mg/ml")
    unit = models.CharField(max_length=50, blank=True, help_text="e.g., mg, ml, g")
    
    # Classification
    schedule = models.CharField(max_length=10, blank=True, help_text="H1, H, G, etc.")
    is_controlled = models.BooleanField(default=False)
    
    # Stock info
    default_pack_size = models.CharField(max_length=50, blank=True)
    default_mrp = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Metadata
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'medicines'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['generic_name']),
            models.Index(fields=['medicine_type', 'is_active']),
            models.Index(fields=['is_controlled']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.generic_name}) {self.strength}"


class PrescriptionMedicine(AuditFieldsMixin, models.Model):
    """Medicine prescribed to a patient"""
    
    FREQUENCY_CHOICES = [
        ('OD', 'Once daily'),
        ('BD', 'Twice daily'),
        ('TDS', 'Thrice daily'),
        ('QID', 'Four times daily'),
        ('HS', 'At bedtime'),
        ('SOS', 'As needed'),
        ('STAT', 'Immediately once'),
        ('PRN', 'When required'),
    ]
    
    DURATION_UNITS = [
        ('DAYS', 'Days'),
        ('WEEKS', 'Weeks'),
        ('MONTHS', 'Months'),
        ('UNTIL_FINISHED', 'Until finished'),
    ]
    
    ROUTE_CHOICES = [
        ('ORAL', 'Oral'),
        ('TOPICAL', 'Topical'),
        ('INHALATION', 'Inhalation'),
        ('INJECTION', 'Injection'),
        ('RECTAL', 'Rectal'),
        ('SUBLINGUAL', 'Sublingual'),
        ('OTHER', 'Other'),
    ]
    
    prescription = models.ForeignKey(
        Prescription,
        on_delete=models.CASCADE,
        related_name='medicines'
    )
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.PROTECT,
        related_name='prescriptions'
    )
    
    # Dosage instructions
    dosage = models.CharField(max_length=100, help_text="e.g., 1 tablet, 5ml")
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES)
    route = models.CharField(max_length=20, choices=ROUTE_CHOICES, default='ORAL')
    
    # Duration
    duration_value = models.PositiveIntegerField(default=7)
    duration_unit = models.CharField(max_length=20, choices=DURATION_UNITS, default='DAYS')
    
    # Timing
    before_food = models.BooleanField(default=False, help_text="Take before food")
    after_food = models.BooleanField(default=True, help_text="Take after food")
    specific_timing = models.CharField(max_length=100, blank=True, help_text="e.g., Morning, Evening")
    
    # Quantity
    quantity = models.DecimalField(max_digits=10, decimal_places=2, help_text="Total quantity to dispense")
    unit = models.CharField(max_length=20, blank=True, help_text="e.g., tablets, ml, bottles")
    
    # Substitution
    allow_generic = models.BooleanField(default=True, help_text="Allow generic substitution")
    allow_brand = models.BooleanField(default=True, help_text="Allow brand substitution")
    
    # Special instructions
    instructions = models.TextField(blank=True)
    precautions = models.TextField(blank=True)
    
    # For repeats
    is_repeat = models.BooleanField(default=False)
    repeat_count = models.PositiveIntegerField(default=0, help_text="Number of repeats allowed")
    repeat_interval = models.PositiveIntegerField(default=0, help_text="Days between repeats")
    
    class Meta:
        db_table = 'prescription_medicines'
        ordering = ['prescription', 'id']
        indexes = [
            models.Index(fields=['prescription', 'medicine']),
        ]
    
    def __str__(self):
        return f"{self.medicine.name} for {self.prescription.prescription_id}"
    
    @property
    def duration_display(self):
        return f"{self.duration_value} {self.duration_unit.lower()}"
    
    @property
    def timing_display(self):
        if self.before_food:
            return "Before food"
        elif self.after_food:
            return "After food"
        return self.specific_timing or ""


class PrescriptionDispense(models.Model):
    """Record of medicine dispensing by pharmacy"""
    
    prescription_medicine = models.ForeignKey(
        PrescriptionMedicine,
        on_delete=models.CASCADE,
        related_name='dispenses'
    )
    
    # Dispensing info
    dispense_id = models.CharField(max_length=50, unique=True, blank=True)
    dispensed_date = models.DateField(auto_now_add=True)
    dispensed_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    batch_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    # Pharmacy info
    pharmacy_name = models.CharField(max_length=200, blank=True)
    pharmacist_name = models.CharField(max_length=100, blank=True)
    pharmacy_license = models.CharField(max_length=100, blank=True)
    
    # Verification
    verified_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_dispenses'
    )
    verification_method = models.CharField(max_length=50, blank=True, help_text="QR scan, Manual, etc.")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'prescription_dispenses'
        ordering = ['-dispensed_date']
        indexes = [
            models.Index(fields=['prescription_medicine', 'dispensed_date']),
            models.Index(fields=['dispense_id']),
            models.Index(fields=['pharmacy_name']),
        ]
    
    def __str__(self):
        return f"Dispense {self.dispense_id}: {self.prescription_medicine.medicine.name}"
    
    def save(self, *args, **kwargs):
        if not self.dispense_id:
            self.dispense_id = self._generate_dispense_id()
        super().save(*args, **kwargs)
    
    def _generate_dispense_id(self):
        """Generate DISP-YYYYMMDD-XXXX format ID"""
        from datetime import datetime
        
        today = datetime.now().strftime('%Y%m%d')
        
        last_dispense = PrescriptionDispense.objects.filter(
            dispense_id__startswith=f'DISP-{today}-'
        ).order_by('dispense_id').last()
        
        if last_dispense:
            last_num = int(last_dispense.dispense_id.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f'DISP-{today}-{new_num:04d}'