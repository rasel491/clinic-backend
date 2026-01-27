# # apps/audit/models.py
# from django.db import models
# from apps.accounts.models import User
# from apps.clinics.models import Branch

# class AuditLog(models.Model):
#     branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
#     user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
#     device_id = models.CharField(max_length=255, null=True, blank=True)
#     ip_address = models.GenericIPAddressField(null=True, blank=True)

#     action = models.CharField(max_length=50, db_index=True)         # create/update/delete
#     model_name = models.CharField(max_length=50)                    # Visit, Invoice, Payment, etc.
#     object_id = models.CharField(max_length=255)                    # PK of affected object
#     before = models.JSONField(null=True, blank=True)                # previous state
#     after = models.JSONField(null=True, blank=True)                 # new state

#     # 🔐 HASH CHAIN
#     previous_hash = models.CharField(max_length=64, blank=True)
#     record_hash = models.CharField(max_length=64, editable=False)

#     timestamp = models.DateTimeField(auto_now_add=True)
#     duration = models.DurationField(null=True, blank=True)

#     class Meta:
#         ordering = ["id"]  # IMPORTANT: strict append-only order
#         verbose_name = 'Audit Log'
#         verbose_name_plural = 'Audit Logs'
#         ordering = ['-timestamp']
#         indexes = [
#             models.Index(fields=['branch', 'timestamp']),
#             models.Index(fields=['user', 'timestamp']),
#             models.Index(fields=['model_name', 'object_id']),
#             models.Index(fields=["record_hash"]),
#         ]

#     def __str__(self):
#         return f"{self.timestamp} | {self.user} | {self.action} | {self.model_name}"


# apps/audit/models.py
from django.db import models
from django.core.exceptions import PermissionDenied
from hashlib import sha256
import json
import hashlib
from apps.accounts.models import User
from apps.clinics.models import Branch


class AuditLog(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, null=True, blank=True, verbose_name='Branch')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    device_id = models.CharField(max_length=255, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    action = models.CharField(max_length=50, db_index=True)
    model_name = models.CharField(max_length=50)
    object_id = models.CharField(max_length=255)

    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    object_repr = models.TextField(blank=True, null=True)

    # 🔐 HASH CHAIN (IMMUTABLE)
    previous_hash = models.CharField(max_length=64, blank=True)
    record_hash = models.CharField(max_length=64, editable=False, db_index=True)

    timestamp = models.DateTimeField(auto_now_add=True)
    duration = models.DurationField(null=True, blank=True)

    class Meta:
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

        # 🔐 STRICT APPEND-ONLY ORDER
        ordering = ["id"]

        indexes = [
            models.Index(fields=["branch", "timestamp"]),
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["model_name", "object_id"]),
            models.Index(fields=["record_hash"]),
        ]

    def __str__(self):
        return f"{self.id} | {self.action} | {self.model_name}:{self.object_id}"

    # ============================
    # 🔐 IMMUTABILITY ENFORCEMENT
    # ============================

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionDenied("AuditLog is immutable (update forbidden)")

        # Fetch previous hash
        last = AuditLog.objects.order_by("-id").only("record_hash").first()
        self.previous_hash = last.record_hash if last else ""

        # Compute current hash
        payload = {
            "previous_hash": self.previous_hash,
            "branch_id": self.branch_id,
            "user_id": self.user_id,
            "action": self.action,
            "model_name": self.model_name,
            "object_id": self.object_id,
            "before": self.before,
            "after": self.after,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat() if self.timestamp else "",
        }

        serialized = json.dumps(payload, sort_keys=True, default=str)
        raw = (self.previous_hash or "") + serialized
        self.record_hash = hashlib.sha256(raw.encode()).hexdigest()

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("AuditLog cannot be deleted")
