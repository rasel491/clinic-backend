# apps/audit/models.py
from django.db import models
# from django.contrib.postgres.fields import JSONField
from apps.accounts.models import User
from apps.clinics.models import Branch

class AuditLog(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    device_id = models.CharField(max_length=255, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    action = models.CharField(max_length=50)         # create/update/delete
    model_name = models.CharField(max_length=50)    # Visit, Invoice, Payment, etc.
    object_id = models.CharField(max_length=255)    # PK of affected object
    before = models.JSONField(null=True, blank=True)       # previous state
    after = models.JSONField(null=True, blank=True)        # new state

    timestamp = models.DateTimeField(auto_now_add=True)
    duration = models.DurationField(null=True, blank=True)

    class Meta:
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['branch', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['model_name', 'object_id']),
        ]

    def __str__(self):
        return f"{self.timestamp} | {self.user} | {self.action} | {self.model_name}"
