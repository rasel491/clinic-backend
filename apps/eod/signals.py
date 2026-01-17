# apps/eod/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import EodLock

User = get_user_model()


@receiver(pre_save, sender=EodLock)
def eod_lock_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal for EodLock
    - Generate lock number if not set
    - Validate EOD transitions
    """
    if not instance.lock_number:
        instance.lock_number = instance.generate_lock_number()
    
    # Validate state transitions
    if instance.pk:
        try:
            old_instance = EodLock.objects.get(pk=instance.pk)
            
            # Prevent modifying locked EODs
            if old_instance.status == EodLock.LOCKED and instance.status != EodLock.LOCKED:
                raise ValueError("Cannot modify a locked EOD")
            
            # Validate transitions
            valid_transitions = {
                EodLock.PREPARED: [EodLock.REVIEWED, EodLock.CANCELLED],
                EodLock.REVIEWED: [EodLock.LOCKED, EodLock.PREPARED],
                EodLock.LOCKED: [EodLock.REVERSED],
                EodLock.REVERSED: []
            }
            
            if instance.status not in valid_transitions.get(old_instance.status, []):
                raise ValueError(f"Invalid transition from {old_instance.status} to {instance.status}")
                
        except EodLock.DoesNotExist:
            pass


@receiver(post_save, sender=EodLock)
def eod_lock_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for EodLock
    - Auto-lock related transactions when EOD is locked
    - Send notifications for EOD status changes
    """
    if instance.status == EodLock.LOCKED and not created:
        # This is handled in the lock() method, but kept here for completeness
        pass
    
    # TODO: Implement notification system when ready
    # if not created and instance.status_changed():
    #     send_eod_status_notification(instance)