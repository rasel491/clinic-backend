# clinic/Backend/apps/clinics/models/branch.py
from django.db import models
from django.utils import timezone

from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin


class Branch(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """
    Physical clinic branch/location
    """

    clinic = models.ForeignKey(
        "clinics.Clinic",
        on_delete=models.CASCADE,
        related_name="branches",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)

    address = models.TextField()
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)

    opening_time = models.TimeField()
    closing_time = models.TimeField()

    is_active = models.BooleanField(default=True)

    # =========================
    # EOD (End Of Day) Lock
    # =========================
    is_eod_locked = models.BooleanField(default=False)
    eod_locked_at = models.DateTimeField(null=True, blank=True)
    eod_locked_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eod_locked_branches",
    )

    class Meta:
        db_table = "branches"
        verbose_name_plural = "Branches"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    # =========================
    # Domain logic
    # =========================
    def lock_eod(self, *, user):
        """
        Irreversible EOD lock.
        Must ONLY be called from service/view layer.
        """
        if self.is_eod_locked:
            raise RuntimeError("EOD already locked for this branch")

        self.is_eod_locked = True
        self.eod_locked_at = timezone.now()
        self.eod_locked_by = user

        self.save(update_fields=[
            "is_eod_locked",
            "eod_locked_at",
            "eod_locked_by",
        ])
