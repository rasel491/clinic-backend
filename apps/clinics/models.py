# clinic/Backend/apps/clinics/models.py
from django.db import models
from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin

class Branch(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """Clinic branch/location"""
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    address = models.TextField()
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    
    # Operational hours
    opening_time = models.TimeField()
    closing_time = models.TimeField()
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'branches'
        verbose_name_plural = 'Branches'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"

class Counter(models.Model):
    """Physical counter at branch (for cashier binding)"""
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='counters')
    counter_number = models.PositiveIntegerField()
    name = models.CharField(max_length=100)
    device_id = models.CharField(max_length=255, unique=True, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'counters'
        unique_together = ['branch', 'counter_number']
        ordering = ['branch', 'counter_number']
    
    def __str__(self):
        return f"{self.branch.code}-Counter{self.counter_number}"
