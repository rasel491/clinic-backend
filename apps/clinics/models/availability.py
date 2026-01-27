# clinic/Backend/apps/clinics/models/availability.py
from django.db import models
from django.core.exceptions import ValidationError

from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin


class DoctorAvailability(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """
    Weekly availability of a doctor per branch.
    """

    DAYS = [
        ("mon", "Monday"),
        ("tue", "Tuesday"),
        ("wed", "Wednesday"),
        ("thu", "Thursday"),
        ("fri", "Friday"),
        ("sat", "Saturday"),
        ("sun", "Sunday"),
    ]

    doctor = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="availabilities",
        limit_choices_to={"role": "doctor"},
    )

    branch = models.ForeignKey(
        "clinics.Branch",
        on_delete=models.CASCADE,
        related_name="doctor_availabilities",
    )

    day_of_week = models.CharField(max_length=3, choices=DAYS)

    start_time = models.TimeField()
    end_time = models.TimeField()

    slot_duration_minutes = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "doctor_availabilities"
        ordering = ["branch", "doctor", "day_of_week"]
        unique_together = ("doctor", "branch", "day_of_week")

    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time")

    def __str__(self):
        return f"{self.doctor} @ {self.branch} ({self.day_of_week})"
