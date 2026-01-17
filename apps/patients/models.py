# clinic/Backend/apps/patients/models.py
from django.db import models
from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin

class Patient(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """Patient profile linked to User account"""
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('U', 'Prefer not to say'),
    ]
    
    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='patient_profile'
    )
    
    # Personal details
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    blood_group = models.CharField(max_length=5, blank=True)
    
    # Contact
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=15, blank=True)
    emergency_contact_relation = models.CharField(max_length=50, blank=True)
    
    # Medical
    allergies = models.TextField(blank=True)
    chronic_conditions = models.TextField(blank=True)
    current_medications = models.TextField(blank=True)
    
    # Registration
    patient_id = models.CharField(max_length=50, unique=True, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    registered_branch = models.ForeignKey(
        'clinics.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registered_patients'
    )
    
    # Flags
    is_insurance_verified = models.BooleanField(default=False)
    insurance_provider = models.CharField(max_length=100, blank=True)
    insurance_id = models.CharField(max_length=100, blank=True)
    
    class Meta:
        db_table = 'patients'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient_id']),
            models.Index(fields=['user']),
            models.Index(fields=['registered_branch', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.full_name} (ID: {self.patient_id or 'N/A'})"
    
    def save(self, *args, **kwargs):
        if not self.patient_id:
            # Auto-generate patient ID: PAT-YYYY-MM-XXXX
            from datetime import datetime
            from django.db.models import Count
            today = datetime.now()
            year_month = today.strftime('%Y%m')
            
            last_patient = Patient.objects.filter(
                patient_id__startswith=f'PAT-{year_month}-'
            ).order_by('patient_id').last()
            
            if last_patient:
                last_num = int(last_patient.patient_id.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            
            self.patient_id = f'PAT-{year_month}-{new_num:04d}'
        
        super().save(*args, **kwargs)
