from apps.audit.models import AuditLog
from django.forms.models import model_to_dict
import datetime

def log_action(user, branch, instance, action, device_id=None, ip_address=None, duration=None):
    """
    Centralized audit logging.
    """
    before = getattr(instance, "_pre_save_snapshot", None)
    after = model_to_dict(instance)

    AuditLog.objects.create(
        branch=branch,
        user=user,
        device_id=device_id,
        ip_address=ip_address,
        action=action,
        model_name=instance.__class__.__name__,
        object_id=str(instance.pk),
        before=before,
        after=after,
        duration=duration,
    )

def snapshot(instance):
    """
    Capture a pre-save snapshot for diff.
    """
    instance._pre_save_snapshot = model_to_dict(instance)
