from django.db.models.signals import pre_save, post_save, pre_delete
from django.dispatch import receiver
from apps.audit.services import snapshot, log_action

TRACKED_MODELS = [
    "visits.Visit",
    "billing.Invoice",
    "payments.Payment",
    "eod.EndOfDay",
    "patients.Patient",
    "prescriptions.Prescription",
]

# Pre-save: capture old state
@receiver(pre_save)
def pre_save_audit(sender, instance, **kwargs):
    if f"{sender._meta.app_label}.{sender.__name__}" in TRACKED_MODELS:
        snapshot(instance)

# Post-save: log create/update
@receiver(post_save)
def post_save_audit(sender, instance, created, **kwargs):
    if f"{sender._meta.app_label}.{sender.__name__}" in TRACKED_MODELS:
        action = "create" if created else "update"
        log_action(
            user=getattr(instance, "_current_user", None),
            branch=getattr(instance, "branch", None),
            instance=instance,
            action=action,
            device_id=getattr(instance, "_current_device", None),
            ip_address=getattr(instance, "_current_ip", None),
        )

# Pre-delete: log deletion
@receiver(pre_delete)
def pre_delete_audit(sender, instance, **kwargs):
    if f"{sender._meta.app_label}.{sender.__name__}" in TRACKED_MODELS:
        log_action(
            user=getattr(instance, "_current_user", None),
            branch=getattr(instance, "branch", None),
            instance=instance,
            action="delete",
            device_id=getattr(instance, "_current_device", None),
            ip_address=getattr(instance, "_current_ip", None),
        )
