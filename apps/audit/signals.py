# # Backend/apps/audit/signals.py
# """
# Signals for automatic audit logging.
# Connect these to your models for automatic auditing.
# """
# from django.db.models.signals import pre_save, post_save, pre_delete, post_delete
# from django.dispatch import receiver
# from django.contrib.auth import get_user_model
# from django.utils import timezone

# from .services import (
#     snapshot_before,
#     log_action,
#     attach_audit_context,
    
# )

# User = get_user_model()


# def register_model_for_auditing(model_class):
#     """
#     Decorator to register a model for automatic auditing.
    
#     Usage:
#         @register_model_for_auditing
#         class MyModel(models.Model):
#             ...
#     """
#     model_name = model_class.__name__
   
#     def get_audit_context(instance):
#         return getattr(instance, "_audit_context", {})
    
#     @receiver(pre_save, sender=model_class)
#     def capture_before_state(sender, instance, **kwargs):
#         """Capture state before save"""
#         snapshot_before(instance)
    
#     @receiver(post_save, sender=model_class)
#     def log_create_or_update(sender, instance, created, **kwargs):
#         """Log creation or update"""
#         context = get_audit_context(instance)
        
#         if created:
#             action = 'CREATE'
#         else:
#             action = 'UPDATE'
        
#         log_action(
#             instance=instance,
#             action=action,
#             user=context.get('user'),
#             branch=context.get('branch'),
#             device_id=context.get('device_id'),
#             ip_address=context.get('ip_address'),
#         )
    
#     @receiver(pre_delete, sender=model_class)
#     def capture_before_delete(sender, instance, **kwargs):
#         """Capture state before delete"""
#         snapshot_before(instance)
    
#     @receiver(post_delete, sender=model_class)
#     def log_delete(sender, instance, **kwargs):
#         """Log deletion"""
#         context = get_audit_context(instance)
        
#         log_action(
#             instance=instance,
#             action='DELETE',
#             user=context.get('user'),
#             branch=context.get('branch'),
#             device_id=context.get('device_id'),
#             ip_address=context.get('ip_address'),
#         )
    
#     return model_class


# # Example usage in other apps:
# """
# from apps.audit.signals import register_model_for_auditing

# @register_model_for_auditing
# class Patient(models.Model):
#     # Your model fields
#     pass
# """


# # Signal for request audit logging
# @receiver(pre_save, sender=User)
# def audit_user_changes(sender, instance, **kwargs):
#     """Audit user model changes"""
#     snapshot_before(instance)


# @receiver(post_save, sender=User)
# def log_user_activity(sender, instance, created, **kwargs):
#     """Log user creation and updates"""
#     from .services import log_action
    
#     if created:
#         action = 'USER_CREATE'
#     else:
#         action = 'USER_UPDATE'
    
#     # Log without context (will be captured by middleware)
#     log_action(
#         instance=instance,
#         action=action,
#         user=instance,  # Self-action
#     )


# @receiver(post_delete, sender=User)
# def log_user_deletion(sender, instance, **kwargs):
#     """Log user deletion"""
#     from .services import log_action
    
#     log_action(
#         instance=instance,
#         action='USER_DELETE',
#         user=instance,
#     )



# Backend/apps/audit/signals.py
"""
Audit signals for automatic, immutable audit logging.

Rules:
- Signals NEVER write business logic
- Signals NEVER assume request existence
- Signals ONLY call audit services
"""

from django.db.models.signals import pre_save, post_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .services import (
    snapshot_before,
    log_create,
    log_update,
    log_delete,
)

User = get_user_model()


# ======================================================
# GENERIC MODEL REGISTRATION
# ======================================================

def register_model_for_auditing(model_class):
    """
    Decorator to enable automatic auditing for a model.

    Usage:
        @register_model_for_auditing
        class Patient(models.Model):
            ...
    """

    # ------------------------------
    # PRE SAVE → SNAPSHOT
    # ------------------------------
    @receiver(
        pre_save,
        sender=model_class,
        dispatch_uid=f"audit_pre_save_{model_class.__name__}",
    )
    def _audit_pre_save(sender, instance, raw=False, **kwargs):
        """
        Capture BEFORE state.
        """
        if raw:
            return
        snapshot_before(instance)

    # ------------------------------
    # POST SAVE → CREATE / UPDATE
    # ------------------------------
    @receiver(
        post_save,
        sender=model_class,
        dispatch_uid=f"audit_post_save_{model_class.__name__}",
    )
    def _audit_post_save(sender, instance, created, raw=False, **kwargs):
        """
        Log CREATE or UPDATE.
        """
        if raw:
            return

        if created:
            log_create(instance=instance)
        else:
            log_update(instance=instance)

    # ------------------------------
    # PRE DELETE → SNAPSHOT + DELETE
    # ------------------------------
    @receiver(
        pre_delete,
        sender=model_class,
        dispatch_uid=f"audit_pre_delete_{model_class.__name__}",
    )
    def _audit_pre_delete(sender, instance, using=None, **kwargs):
        """
        Log DELETE while PK still exists.
        """
        snapshot_before(instance)
        log_delete(instance=instance)

    return model_class


# ======================================================
# USER MODEL AUDIT (STRICT & SAFE)
# ======================================================

@receiver(
    pre_save,
    sender=User,
    dispatch_uid="audit_user_pre_save",
)
def audit_user_pre_save(sender, instance, raw=False, **kwargs):
    """
    Capture BEFORE state for User changes.
    """
    if raw:
        return
    snapshot_before(instance)


@receiver(
    post_save,
    sender=User,
    dispatch_uid="audit_user_post_save",
)
def audit_user_post_save(sender, instance, created, raw=False, **kwargs):
    """
    Audit User CREATE / UPDATE.
    """
    if raw:
        return

    if created:
        log_create(instance=instance, user=instance)
    else:
        log_update(instance=instance, user=instance)


@receiver(
    pre_delete,
    sender=User,
    dispatch_uid="audit_user_pre_delete",
)
def audit_user_pre_delete(sender, instance, using=None, **kwargs):
    """
    Audit User DELETE.
    """
    snapshot_before(instance)
    log_delete(instance=instance, user=instance)
