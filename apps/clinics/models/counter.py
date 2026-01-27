# clinic/Backend/apps/clinics/models/counter.py
from django.db import models

from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin


class Counter(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """
    Physical reception / cashier counter
    """

    branch = models.ForeignKey(
        "clinics.Branch",
        on_delete=models.CASCADE,
        related_name="counters",
    )

    counter_number = models.PositiveIntegerField()
    name = models.CharField(max_length=100)

    device_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text="Bound hardware device identifier",
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "counters"
        ordering = ["branch", "counter_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "counter_number"],
                name="unique_counter_per_branch",
            )
        ]
        indexes = [
            models.Index(fields=["device_id"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.branch.code}-Counter{self.counter_number}"
