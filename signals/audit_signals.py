# # core/signals/audit_signals.py (apps base signal.py)

# from django.db.models.signals import pre_save, post_save, pre_delete
# from django.dispatch import receiver
# from django.apps import apps

# from apps.audit.models import AuditLog
# from apps.audit.services import snapshot, log_action


# # ==========================
# # Tracked models (resolved once)
# # ==========================

# TRACKED_MODELS = {
#     apps.get_model("visits", "Visit"),
#     apps.get_model("billing", "Invoice"),
#     apps.get_model("payments", "Payment"),
#     apps.get_model("eod", "EndOfDay"),
#     apps.get_model("patients", "Patient"),
#     apps.get_model("prescriptions", "Prescription"),
# }


# def is_tracked_model(sender):
#     return sender in TRACKED_MODELS


# # ==========================
# # PRE-SAVE (snapshot before update)
# # ==========================

# @receiver(pre_save)
# def audit_pre_save(sender, instance, **kwargs):
#     if not is_tracked_model(sender):
#         return

#     # Skip create
#     if instance._state.adding:
#         return

#     # Capture "before" state
#     snapshot(instance)


# # ==========================
# # POST-SAVE (create / update)
# # ==========================

# @receiver(post_save)
# def audit_post_save(sender, instance, created, **kwargs):
#     if not is_tracked_model(sender):
#         return

#     action = "CREATE" if created else "UPDATE"

#     log_action(
#         user=getattr(instance, "_current_user", None),
#         branch=getattr(instance, "branch", None),
#         instance=instance,
#         action=action,
#         device_id=getattr(instance, "_current_device", None),
#         ip_address=getattr(instance, "_current_ip", None),
#     )


# # ==========================
# # PRE-DELETE (delete with snapshot)
# # ==========================

# @receiver(pre_delete)
# def audit_pre_delete(sender, instance, **kwargs):
#     if not is_tracked_model(sender):
#         return

#     # Capture state before delete
#     snapshot(instance)

#     log_action(
#         user=getattr(instance, "_current_user", None),
#         branch=getattr(instance, "branch", None),
#         instance=instance,
#         action="DELETE",
#         device_id=getattr(instance, "_current_device", None),
#         ip_address=getattr(instance, "_current_ip", None),
#     )
