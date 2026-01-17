# clinic/Backend/core/mixins/audit_fields.py
from django.db import models

class AuditFieldsMixin(models.Model):
    """Adds created/updated audit fields to models"""
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_%(class)ss',
        editable=False
    )
    updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_%(class)ss',
        editable=False
    )
    
    class Meta:
        abstract = True

