# clinic/Backend/apps/clinics/models/clinic.py
from django.db import models
from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin


class Clinic(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """
    Top-level organization.
    Useful for multi-company or franchise setups.
    """

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "clinics"
        ordering = ["name"]

    def __str__(self):
        return self.name
