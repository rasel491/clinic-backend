#apps/doctors/models.py

from django.db import models
from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin

class Doctor(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """Doctor profile - link to User account"""
    
    SPECIALIZATION_CHOICES = [
        ('GENERAL', 'General Dentistry'),
        ('ORTHO', 'Orthodontics'),
        ('PERIO', 'Periodontics'),
        ('ENDO', 'Endodontics'),
        ('PEDO', 'Pediatric Dentistry'),
        ('SURG', 'Oral Surgery'),
        ('PROS', 'Prosthodontics'),
    ]
    
    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='doctor_profile'
    )
    
    # Professional details
    doctor_id = models.CharField(max_length=50, unique=True, blank=True)
    specialization = models.CharField(max_length=50, choices=SPECIALIZATION_CHOICES)
    qualification = models.CharField(max_length=200)
    license_number = models.CharField(max_length=100, unique=True)
    license_expiry = models.DateField()
    
    # Branch association
    primary_branch = models.ForeignKey(
        'clinics.Branch',
        on_delete=models.PROTECT,
        related_name='doctors'
    )
    
    # Availability
    is_active = models.BooleanField(default=True)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Bio
    bio = models.TextField(blank=True)
    years_of_experience = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'doctors'
        ordering = ['doctor_id']
        indexes = [
            models.Index(fields=['doctor_id']),
            models.Index(fields=['specialization']),
            models.Index(fields=['primary_branch', 'is_active']),
            models.Index(fields=['license_number']),
        ]
    
    def __str__(self):
        return f"Dr. {self.user.full_name} ({self.specialization})"
    
    def save(self, *args, **kwargs):
        if not self.doctor_id:
            self.doctor_id = self._generate_doctor_id()
        super().save(*args, **kwargs)
    
    def _generate_doctor_id(self):
        """Generate DOC-XXX format ID"""
        from django.db.models import Count
        
        count = Doctor.objects.count() + 1
        return f'DOC-{count:03d}'

class DoctorSchedule(AuditFieldsMixin, models.Model):
    """Doctor's working schedule"""
    
    DAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    
    # Break timings
    break_start = models.TimeField(null=True, blank=True)
    break_end = models.TimeField(null=True, blank=True)
    
    # Appointment settings
    slot_duration = models.PositiveIntegerField(default=30)  # minutes
    max_patients_per_slot = models.PositiveIntegerField(default=1)
    
    class Meta:
        db_table = 'doctor_schedules'
        unique_together = ['doctor', 'day_of_week']
        ordering = ['doctor', 'day_of_week']
        indexes = [
            models.Index(fields=['doctor', 'day_of_week', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.doctor} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"

class DoctorLeave(models.Model):
    """Doctor's leave/absence records"""
    
    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name='leaves'
    )
    
    leave_date = models.DateField()
    reason = models.CharField(max_length=200)
    is_full_day = models.BooleanField(default=True)
    
    # For half-day leaves
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    
    approved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='approved_leaves'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'doctor_leaves'
        unique_together = ['doctor', 'leave_date']
        ordering = ['-leave_date']
        indexes = [
            models.Index(fields=['doctor', 'leave_date']),
        ]
    
    def __str__(self):
        return f"{self.doctor} - {self.leave_date} ({self.reason})"
