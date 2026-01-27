# # clinic/Backend/apps/clinics/models.py old

# from django.db import models
# from django.utils import timezone

# from core.mixins.audit_fields import AuditFieldsMixin
# from core.mixins.soft_delete import SoftDeleteMixin



# class Branch(AuditFieldsMixin, SoftDeleteMixin, models.Model):
#     """Clinic branch/location"""

#     name = models.CharField(max_length=200)
#     code = models.CharField(max_length=20, unique=True)
#     address = models.TextField()
#     phone = models.CharField(max_length=20)
#     email = models.EmailField(blank=True)

#     # Operational hours
#     opening_time = models.TimeField()
#     closing_time = models.TimeField()

#     is_active = models.BooleanField(default=True)

#     # =========================
#     # EOD (End Of Day) Lock
#     # =========================
#     is_eod_locked = models.BooleanField(default=False)
#     eod_locked_at = models.DateTimeField(null=True, blank=True)
#     eod_locked_by = models.ForeignKey(
#         "accounts.User",
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name="eod_locked_branches",
#     )

#     class Meta:
#         db_table = "branches"
#         verbose_name_plural = "Branches"
#         ordering = ["name"]

#     def __str__(self):
#         return f"{self.name} ({self.code})"

#     # =========================
#     # EOD domain logic
#     # =========================
#     def lock_eod(self, *, user):
#         """
#         Irreversible EOD lock.
#         Must be called ONLY from service layer.
#         """
#         if self.is_eod_locked:
#             raise RuntimeError("EOD already locked for this branch")

#         self.is_eod_locked = True
#         self.eod_locked_at = timezone.now()
#         self.eod_locked_by = user

#         self.save(update_fields=[
#             "is_eod_locked",
#             "eod_locked_at",
#             "eod_locked_by",
#         ])

# class Counter(AuditFieldsMixin, SoftDeleteMixin, models.Model):
#     """Physical counter at branch (for cashier binding)"""
#     branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='counters')
#     counter_number = models.PositiveIntegerField()
#     name = models.CharField(max_length=100)
#     device_id = models.CharField(max_length=255, unique=True, blank=True, null=True)
#     is_active = models.BooleanField(default=True)

  
#     class Meta:
#         db_table = 'counters'
#         unique_together = ['branch', 'counter_number']
#         ordering = ['branch', 'counter_number']
    
#     def __str__(self):
#         return f"{self.branch.code}-Counter{self.counter_number}"





## New
# from django.db import models
# from django.utils import timezone
# from django.core.exceptions import ValidationError

# from core.mixins.audit_fields import AuditFieldsMixin
# from core.mixins.soft_delete import SoftDeleteMixin


# # =====================================================
# # Branch Model
# # =====================================================

# class Branch(AuditFieldsMixin, SoftDeleteMixin, models.Model):
#     """
#     Clinic branch / physical location.

#     Responsibilities:
#     - Operational identity
#     - EOD (End of Day) locking
#     - Parent entity for counters, appointments, payments
#     """

#     # =========================
#     # Identity & Contact
#     # =========================
#     name = models.CharField(
#         max_length=200,
#         help_text="Human readable branch name"
#     )
#     code = models.CharField(
#         max_length=20,
#         unique=True,
#         help_text="Unique short branch code"
#     )
#     address = models.TextField()
#     phone = models.CharField(max_length=20)
#     email = models.EmailField(blank=True)

#     # =========================
#     # Operational Hours
#     # =========================
#     opening_time = models.TimeField(
#         help_text="Branch opening time"
#     )
#     closing_time = models.TimeField(
#         help_text="Branch closing time"
#     )

#     # =========================
#     # Status Flags
#     # =========================
#     is_active = models.BooleanField(
#         default=True,
#         help_text="Whether branch is operational"
#     )

#     # =========================
#     # EOD (End Of Day) Locking
#     # =========================
#     is_eod_locked = models.BooleanField(
#         default=False,
#         help_text="Indicates whether EOD is locked"
#     )
#     eod_locked_at = models.DateTimeField(
#         null=True,
#         blank=True
#     )
#     eod_locked_by = models.ForeignKey(
#         "accounts.User",
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name="eod_locked_branches",
#     )

#     # =========================
#     # Django Meta
#     # =========================
#     class Meta:
#         db_table = "branches"
#         verbose_name = "Branch"
#         verbose_name_plural = "Branches"
#         ordering = ["name"]
#         indexes = [
#             models.Index(fields=["code"]),
#             models.Index(fields=["is_active"]),
#         ]

#     # =========================
#     # String Representation
#     # =========================
#     def __str__(self):
#         return f"{self.name} ({self.code})"

#     # =========================
#     # Validation
#     # =========================
#     def clean(self):
#         if self.opening_time >= self.closing_time:
#             raise ValidationError(
#                 "Opening time must be before closing time."
#             )

#     # =========================
#     # Domain Logic (EOD)
#     # =========================
#     def lock_eod(self, *, user):
#         """
#         Perform irreversible End-Of-Day lock.

#         Rules:
#         - Can only be executed once
#         - Must be called by authorized service / view
#         """
#         if self.is_eod_locked:
#             raise RuntimeError("EOD already locked for this branch")

#         self.is_eod_locked = True
#         self.eod_locked_at = timezone.now()
#         self.eod_locked_by = user

#         self.save(update_fields=[
#             "is_eod_locked",
#             "eod_locked_at",
#             "eod_locked_by",
#             "updated_at",
#         ])

#     @property
#     def is_open_now(self):
#         """Runtime check for branch open status"""
#         now = timezone.localtime().time()
#         return (
#             self.is_active
#             and not self.is_eod_locked
#             and self.opening_time <= now <= self.closing_time
#         )


# # =====================================================
# # Counter Model
# # =====================================================

# class Counter(AuditFieldsMixin, SoftDeleteMixin, models.Model):
#     """
#     Physical counter within a branch.

#     Responsibilities:
#     - Device binding
#     - Cashier assignment
#     - Transaction source tracking
#     """

#     # =========================
#     # Relationships
#     # =========================
#     branch = models.ForeignKey(
#         Branch,
#         on_delete=models.CASCADE,
#         related_name="counters"
#     )

#     # =========================
#     # Identity
#     # =========================
#     counter_number = models.PositiveIntegerField(
#         help_text="Sequential counter number per branch"
#     )
#     name = models.CharField(
#         max_length=100,
#         help_text="Display name for counter"
#     )

#     # =========================
#     # Device Binding
#     # =========================
#     device_id = models.CharField(
#         max_length=255,
#         unique=True,
#         null=True,
#         blank=True,
#         help_text="Bound hardware / device identifier"
#     )

#     # =========================
#     # Status
#     # =========================
#     is_active = models.BooleanField(
#         default=True,
#         help_text="Whether counter is operational"
#     )

#     # =========================
#     # Django Meta
#     # =========================
#     class Meta:
#         db_table = "counters"
#         verbose_name = "Counter"
#         verbose_name_plural = "Counters"
#         ordering = ["branch", "counter_number"]
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["branch", "counter_number"],
#                 name="unique_counter_per_branch"
#             )
#         ]
#         indexes = [
#             models.Index(fields=["branch"]),
#             models.Index(fields=["device_id"]),
#             models.Index(fields=["is_active"]),
#         ]

#     # =========================
#     # String Representation
#     # =========================
#     def __str__(self):
#         return f"{self.branch.code}-C{self.counter_number}"

#     # =========================
#     # Domain Helpers
#     # =========================
#     def assign_device(self, device_id: str):
#         if not self.is_active:
#             raise ValidationError("Cannot assign device to inactive counter")
#         self.device_id = device_id
#         self.save(update_fields=["device_id", "updated_at"])

#     def unassign_device(self):
#         self.device_id = None
#         self.save(update_fields=["device_id", "updated_at"])
