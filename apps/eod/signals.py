# # apps/eod/signals.py
# from django.db.models.signals import post_save, pre_save
# from django.dispatch import receiver
# from django.utils import timezone
# from django.contrib.auth import get_user_model

# from .models import EodLock

# User = get_user_model()


# @receiver(pre_save, sender=EodLock)
# def eod_lock_pre_save(sender, instance, **kwargs):
#     """
#     Pre-save signal for EodLock
#     - Generate lock number if not set
#     - Validate EOD transitions
#     """
#     if not instance.lock_number:
#         instance.lock_number = instance.generate_lock_number()
    
#     # Validate state transitions
#     if instance.pk:
#         try:
#             old_instance = EodLock.objects.get(pk=instance.pk)
            
#             # Prevent modifying locked EODs
#             if old_instance.status == EodLock.LOCKED and instance.status != EodLock.LOCKED:
#                 raise ValueError("Cannot modify a locked EOD")
            
#             # Validate transitions
#             valid_transitions = {
#                 EodLock.PREPARED: [EodLock.REVIEWED, EodLock.CANCELLED],
#                 EodLock.REVIEWED: [EodLock.LOCKED, EodLock.PREPARED],
#                 EodLock.LOCKED: [EodLock.REVERSED],
#                 EodLock.REVERSED: []
#             }
            
#             if instance.status not in valid_transitions.get(old_instance.status, []):
#                 raise ValueError(f"Invalid transition from {old_instance.status} to {instance.status}")
                
#         except EodLock.DoesNotExist:
#             pass


# @receiver(post_save, sender=EodLock)
# def eod_lock_post_save(sender, instance, created, **kwargs):
#     """
#     Post-save signal for EodLock
#     - Auto-lock related transactions when EOD is locked
#     - Send notifications for EOD status changes
#     """
#     if instance.status == EodLock.LOCKED and not created:
#         # This is handled in the lock() method, but kept here for completeness
#         pass
    
#     # TODO: Implement notification system when ready
#     # if not created and instance.status_changed():
#     #     send_eod_status_notification(instance)


# apps/eod/signals.py - Add notification placeholder

# @receiver(post_save, sender=EodLock)
# def send_eod_notifications(sender, instance, created, **kwargs):
#     """
#     Send notifications for EOD status changes
#     """
#     # TODO: Integrate with your notification system
#     notifications_to_send = {
#         EodLock.PREPARED: {
#             'recipients': ['clinic_manager', 'super_admin'],
#             'message': f'EOD prepared for {instance.lock_date} by {instance.prepared_by}'
#         },
#         EodLock.REVIEWED: {
#             'recipients': ['clinic_manager', 'cashier'],
#             'message': f'EOD reviewed for {instance.lock_date}'
#         },
#         EodLock.LOCKED: {
#             'recipients': ['all_managers', 'accounting'],
#             'message': f'EOD locked for {instance.lock_date}. No further modifications allowed.'
#         }
#     }






# # apps/eod/signals.py

# from django.db.models.signals import post_save, pre_save, post_delete, pre_delete, m2m_changed
# from django.dispatch import receiver
# from django.utils import timezone
# from django.contrib.auth import get_user_model
# from django.core.exceptions import ValidationError
# from datetime import datetime, timedelta
# import logging

# from .models import EodLock, DailySummary, CashReconciliation, EodException
# from apps.audit.services import log_action
# from apps.notifications.services import NotificationService  
# User = get_user_model()
# logger = logging.getLogger(__name__)
# notification_service = NotificationService()


# # ===========================================
# # EOD LOCK SIGNALS
# # ===========================================

# @receiver(pre_save, sender=EodLock)
# def eod_lock_pre_save(sender, instance, **kwargs):
#     """
#     Pre-save signal for EodLock
#     - Generate lock number if not set
#     - Validate EOD transitions
#     - Set calculated fields
#     """
#     # Generate lock number if not set
#     if not instance.lock_number:
#         instance.lock_number = instance.generate_lock_number()
    
#     # Calculate net cash position
#     if hasattr(instance, 'total_cash_collected') and hasattr(instance, 'total_cash_refunded'):
#         instance.net_cash_position = instance.total_cash_collected - instance.total_cash_refunded
    
#     # Set expected cash if opening cash is set
#     if instance.opening_cash and not instance.expected_cash:
#         instance.expected_cash = instance.opening_cash + instance.total_cash_collected - instance.total_cash_refunded
    
#     # Calculate cash difference if actual cash is provided
#     if instance.actual_cash is not None and instance.expected_cash is not None:
#         instance.cash_difference = instance.actual_cash - instance.expected_cash
        
#         # Check for discrepancies
#         if abs(instance.cash_difference) > 0.50:  # 50 paise tolerance
#             instance.has_discrepancies = True
#             if not instance.discrepancy_notes:
#                 sign = "over" if instance.cash_difference > 0 else "under"
#                 instance.discrepancy_notes = f"Cash {sign} by ₹{abs(instance.cash_difference):.2f}"
    
#     # Validate state transitions
#     if instance.pk:
#         try:
#             old_instance = EodLock.objects.get(pk=instance.pk)
            
#             # Prevent modifying locked EODs
#             if old_instance.status == EodLock.LOCKED and instance.status != EodLock.LOCKED:
#                 raise ValidationError("Cannot modify a locked EOD")
            
#             # Validate transitions
#             valid_transitions = {
#                 EodLock.PREPARED: [EodLock.REVIEWED, EodLock.PREPARED],  # Can stay in PREPARED
#                 EodLock.REVIEWED: [EodLock.LOCKED, EodLock.PREPARED],
#                 EodLock.LOCKED: [EodLock.REVERSED],
#                 EodLock.REVERSED: []
#             }
            
#             old_status = old_instance.status
#             new_status = instance.status
            
#             if old_status != new_status and new_status not in valid_transitions.get(old_status, []):
#                 raise ValidationError(
#                     f"Invalid EOD transition from '{old_status}' to '{new_status}'. "
#                     f"Valid transitions: {valid_transitions.get(old_status, [])}"
#                 )
            
#             # Set timestamps for status changes
#             if old_status != new_status:
#                 if new_status == EodLock.REVIEWED:
#                     instance.reviewed_at = timezone.now()
#                 elif new_status == EodLock.LOCKED:
#                     instance.locked_at = timezone.now()
#                 elif new_status == EodLock.REVERSED:
#                     instance.reversed_at = timezone.now()
                    
#         except EodLock.DoesNotExist:
#             pass
    
#     # Auto-set prepared_by if not set
#     if not instance.prepared_by and hasattr(instance, '_prepared_by_user'):
#         instance.prepared_by = instance._prepared_by_user
    
#     # Validate lock date is not in future
#     if instance.lock_date and instance.lock_date > timezone.now().date():
#         raise ValidationError("Cannot create EOD for future date")


# @receiver(post_save, sender=EodLock)
# def eod_lock_post_save(sender, instance, created, **kwargs):
#     """
#     Post-save signal for EodLock
#     - Auto-create audit logs
#     - Send notifications
#     - Update related records
#     """
#     # Log the action
#     action = 'EOD_CREATED' if created else 'EOD_UPDATED'
    
#     # Determine if status changed
#     if not created and instance.tracker.has_changed('status'):
#         old_status = instance.tracker.previous('status')
#         new_status = instance.status
#         action = f'EOD_STATUS_CHANGED_{old_status}_TO_{new_status}'
        
#         # Send notifications for status changes
#         send_eod_status_notification(instance, old_status, new_status)
    
#     # Create audit log
#     try:
#         # Get user from request context or use prepared_by
#         user = getattr(instance, '_updated_by', instance.prepared_by)
        
#         log_action(
#             user=user,
#             branch=instance.branch,
#             instance=instance,
#             action=action,
#             device_id=getattr(instance, '_device_id', None),
#             ip_address=getattr(instance, '_ip_address', None),
#             metadata={
#                 'lock_number': instance.lock_number,
#                 'lock_date': str(instance.lock_date),
#                 'status': instance.status,
#                 'has_discrepancies': instance.has_discrepancies,
#                 'cash_difference': str(instance.cash_difference) if instance.cash_difference else None
#             }
#         )
#     except Exception as e:
#         logger.error(f"Failed to log EOD action: {str(e)}")
    
#     # Update branch EOD status
#     if instance.status == EodLock.LOCKED:
#         try:
#             # Lock all transactions for this date
#             from ..billing.models import Invoice
#             from ..payments.models import Payment, Refund
            
#             # Update invoices
#             Invoice.objects.filter(
#                 branch=instance.branch,
#                 invoice_date=instance.lock_date,
#                 eod_locked=False
#             ).update(eod_locked=True, locked_eod=instance)
            
#             # Update payments
#             Payment.objects.filter(
#                 branch=instance.branch,
#                 payment_date__date=instance.lock_date,
#                 eod_locked=False
#             ).update(eod_locked=True, locked_eod=instance)
            
#             # Update refunds
#             Refund.objects.filter(
#                 branch=instance.branch,
#                 requested_at__date=instance.lock_date,
#                 eod_locked=False
#             ).update(eod_locked=True)
            
#             logger.info(f"Locked transactions for EOD {instance.lock_number}")
            
#         except Exception as e:
#             logger.error(f"Failed to lock transactions for EOD {instance.lock_number}: {str(e)}")
    
#     elif instance.status == EodLock.REVERSED:
#         try:
#             # Unlock all transactions for this date
#             from ..billing.models import Invoice
#             from ..payments.models import Payment, Refund
            
#             # Update invoices
#             Invoice.objects.filter(
#                 branch=instance.branch,
#                 invoice_date=instance.lock_date,
#                 eod_locked=True,
#                 locked_eod=instance
#             ).update(eod_locked=False, locked_eod=None)
            
#             # Update payments
#             Payment.objects.filter(
#                 branch=instance.branch,
#                 payment_date__date=instance.lock_date,
#                 eod_locked=True,
#                 locked_eod=instance
#             ).update(eod_locked=False, locked_eod=None)
            
#             # Update refunds
#             Refund.objects.filter(
#                 branch=instance.branch,
#                 requested_at__date=instance.lock_date,
#                 eod_locked=True
#             ).update(eod_locked=False)
            
#             logger.info(f"Unlocked transactions for reversed EOD {instance.lock_number}")
            
#         except Exception as e:
#             logger.error(f"Failed to unlock transactions for reversed EOD {instance.lock_number}: {str(e)}")


# @receiver(pre_delete, sender=EodLock)
# def eod_lock_pre_delete(sender, instance, **kwargs):
#     """
#     Prevent deletion of locked EODs
#     """
#     if instance.status == EodLock.LOCKED:
#         raise ValidationError("Cannot delete a locked EOD")
    
#     # Check if EOD is referenced by other records
#     if instance.daily_summaries.exists():
#         raise ValidationError("Cannot delete EOD with associated daily summaries")
    
#     if instance.cash_reconciliations.exists():
#         raise ValidationError("Cannot delete EOD with associated cash reconciliations")
    
#     if instance.exceptions.exists():
#         raise ValidationError("Cannot delete EOD with associated exceptions")


# # ===========================================
# # DAILY SUMMARY SIGNALS
# # ===========================================

# @receiver(pre_save, sender=DailySummary)
# def daily_summary_pre_save(sender, instance, **kwargs):
#     """
#     Pre-save signal for DailySummary
#     """
#     # Generate summary number if not set
#     if not instance.summary_number:
#         instance.summary_number = instance.generate_summary_number()
    
#     # Validate period
#     if instance.period_start and instance.period_end:
#         if instance.period_start >= instance.period_end:
#             raise ValidationError("Period start must be before period end")
        
#         # Ensure summary date matches period
#         if instance.summary_date and instance.summary_date != instance.period_start.date():
#             instance.summary_date = instance.period_start.date()
    
#     # Calculate duration in hours
#     if instance.period_start and instance.period_end:
#         duration = instance.period_end - instance.period_start
#         instance.metadata['duration_hours'] = duration.total_seconds() / 3600


# @receiver(post_save, sender=DailySummary)
# def daily_summary_post_save(sender, instance, created, **kwargs):
#     """
#     Post-save signal for DailySummary
#     """
#     action = 'DAILY_SUMMARY_CREATED' if created else 'DAILY_SUMMARY_UPDATED'
    
#     try:
#         user = getattr(instance, '_updated_by', instance.generated_by)
        
#         log_action(
#             user=user,
#             branch=instance.branch,
#             instance=instance,
#             action=action,
#             metadata={
#                 'summary_number': instance.summary_number,
#                 'summary_type': instance.summary_type,
#                 'summary_date': str(instance.summary_date),
#                 'period': f"{instance.period_start} to {instance.period_end}"
#             }
#         )
#     except Exception as e:
#         logger.error(f"Failed to log daily summary action: {str(e)}")


# # ===========================================
# # CASH RECONCILIATION SIGNALS
# # ===========================================

# @receiver(pre_save, sender=CashReconciliation)
# def cash_reconciliation_pre_save(sender, instance, **kwargs):
#     """
#     Pre-save signal for CashReconciliation
#     """
#     # Generate reconciliation number if not set
#     if not instance.reconciliation_number:
#         instance.reconciliation_number = instance.generate_reconciliation_number()
    
#     # Calculate difference if counted cash is provided
#     if instance.counted_cash is not None and instance.declared_cash is not None:
#         instance.difference = instance.counted_cash - instance.declared_cash
    
#     # Validate cash amounts
#     if instance.declared_cash < 0:
#         raise ValidationError("Declared cash cannot be negative")
    
#     if instance.counted_cash is not None and instance.counted_cash < 0:
#         raise ValidationError("Counted cash cannot be negative")
    
#     # Validate counter belongs to branch
#     if instance.counter and instance.branch and instance.counter.branch != instance.branch:
#         raise ValidationError("Counter does not belong to the specified branch")


# @receiver(post_save, sender=CashReconciliation)
# def cash_reconciliation_post_save(sender, instance, created, **kwargs):
#     """
#     Post-save signal for CashReconciliation
#     """
#     action = 'CASH_RECONCILIATION_CREATED' if created else 'CASH_RECONCILIATION_UPDATED'
    
#     # If verified status changed
#     if not created and instance.tracker.has_changed('verified'):
#         if instance.verified:
#             action = 'CASH_RECONCILIATION_VERIFIED'
#         else:
#             action = 'CASH_RECONCILIATION_UNVERIFIED'
    
#     try:
#         user = getattr(instance, '_updated_by', instance.cashier)
        
#         log_action(
#             user=user,
#             branch=instance.branch,
#             instance=instance,
#             action=action,
#             metadata={
#                 'reconciliation_number': instance.reconciliation_number,
#                 'type': instance.reconciliation_type,
#                 'declared_cash': str(instance.declared_cash),
#                 'counted_cash': str(instance.counted_cash) if instance.counted_cash else None,
#                 'difference': str(instance.difference) if instance.difference else None,
#                 'verified': instance.verified
#             }
#         )
#     except Exception as e:
#         logger.error(f"Failed to log cash reconciliation action: {str(e)}")
    
#     # Link to EOD if not already linked
#     if instance.eod_lock is None and instance.reconciliation_date:
#         try:
#             eod = EodLock.objects.filter(
#                 branch=instance.branch,
#                 lock_date=instance.reconciliation_date,
#                 status=EodLock.LOCKED
#             ).first()
            
#             if eod:
#                 instance.eod_lock = eod
#                 instance.save(update_fields=['eod_lock'])
#                 logger.info(f"Linked cash reconciliation {instance.reconciliation_number} to EOD {eod.lock_number}")
#         except Exception as e:
#             logger.error(f"Failed to link cash reconciliation to EOD: {str(e)}")


# # ===========================================
# # EOD EXCEPTION SIGNALS
# # ===========================================

# @receiver(pre_save, sender=EodException)
# def eod_exception_pre_save(sender, instance, **kwargs):
#     """
#     Pre-save signal for EodException
#     """
#     # Generate exception number if not set
#     if not instance.exception_number:
#         instance.exception_number = instance.generate_exception_number()
    
#     # Set exception date from EOD if not set
#     if not instance.exception_date and instance.eod_lock:
#         instance.exception_date = instance.eod_lock.lock_date
    
#     # Auto-assign high severity exceptions
#     if instance.severity in [EodException.HIGH, EodException.CRITICAL] and not instance.assigned_to:
#         # Find available manager
#         try:
#             managers = User.objects.filter(
#                 role__in=['clinic_manager', 'super_admin'],
#                 is_active=True
#             ).order_by('?').first()  # Random manager
            
#             if managers:
#                 instance.assigned_to = managers
#                 instance.assigned_at = timezone.now()
#                 instance.status = EodException.IN_PROGRESS
#         except Exception as e:
#             logger.error(f"Failed to auto-assign exception: {str(e)}")


# @receiver(post_save, sender=EodException)
# def eod_exception_post_save(sender, instance, created, **kwargs):
#     """
#     Post-save signal for EodException
#     """
#     action = 'EOD_EXCEPTION_CREATED' if created else 'EOD_EXCEPTION_UPDATED'
    
#     # Track status changes
#     if not created and instance.tracker.has_changed('status'):
#         old_status = instance.tracker.previous('status')
#         new_status = instance.status
        
#         if new_status == EodException.RESOLVED:
#             action = 'EOD_EXCEPTION_RESOLVED'
#         elif new_status == EodException.CANCELLED:
#             action = 'EOD_EXCEPTION_CANCELLED'
#         elif new_status == EodException.IN_PROGRESS:
#             action = 'EOD_EXCEPTION_ASSIGNED'
        
#         # Send notification for high severity exceptions
#         if instance.severity in [EodException.HIGH, EodException.CRITICAL]:
#             send_exception_notification(instance, old_status, new_status)
    
#     # Track assignment changes
#     if not created and instance.tracker.has_changed('assigned_to'):
#         action = 'EOD_EXCEPTION_REASSIGNED'
    
#     try:
#         user = getattr(instance, '_updated_by', None)
#         if not user and instance.assigned_to:
#             user = instance.assigned_to
        
#         log_action(
#             user=user,
#             branch=instance.branch,
#             instance=instance,
#             action=action,
#             metadata={
#                 'exception_number': instance.exception_number,
#                 'exception_type': instance.exception_type,
#                 'severity': instance.severity,
#                 'status': instance.status,
#                 'amount_involved': str(instance.amount_involved) if instance.amount_involved else None,
#                 'assigned_to': str(instance.assigned_to) if instance.assigned_to else None
#             }
#         )
#     except Exception as e:
#         logger.error(f"Failed to log exception action: {str(e)}")
    
#     # Update EOD lock if exception is resolved
#     if instance.status == EodException.RESOLVED and instance.eod_lock:
#         try:
#             # Check if all exceptions for this EOD are resolved
#             unresolved_count = EodException.objects.filter(
#                 eod_lock=instance.eod_lock,
#                 status__in=[EodException.OPEN, EodException.IN_PROGRESS]
#             ).count()
            
#             if unresolved_count == 0:
#                 instance.eod_lock.discrepancy_resolved = True
#                 instance.eod_lock.discrepancy_resolved_by = instance.resolved_by
#                 instance.eod_lock.discrepancy_resolved_at = timezone.now()
#                 instance.eod_lock.resolution_notes = f"All exceptions resolved via exception {instance.exception_number}"
#                 instance.eod_lock.save()
                
#                 logger.info(f"Marked EOD {instance.eod_lock.lock_number} discrepancies as resolved")
#         except Exception as e:
#             logger.error(f"Failed to update EOD lock status: {str(e)}")


# # ===========================================
# # NOTIFICATION FUNCTIONS
# # ===========================================

# def send_eod_status_notification(eod_lock, old_status, new_status):
#     """
#     Send notifications for EOD status changes
#     """
#     try:
#         # Notification configurations
#         notifications_config = {
#             EodLock.PREPARED: {
#                 'recipient_roles': ['clinic_manager', 'super_admin'],
#                 'title': f'EOD Prepared - {eod_lock.branch.name}',
#                 'message': f'EOD {eod_lock.lock_number} prepared for {eod_lock.lock_date} by {eod_lock.prepared_by}',
#                 'priority': 'medium'
#             },
#             EodLock.REVIEWED: {
#                 'recipient_roles': ['clinic_manager', 'cashier'],
#                 'title': f'EOD Reviewed - {eod_lock.branch.name}',
#                 'message': f'EOD {eod_lock.lock_number} reviewed for {eod_lock.lock_date}. Ready for locking.',
#                 'priority': 'medium'
#             },
#             EodLock.LOCKED: {
#                 'recipient_roles': ['clinic_manager', 'super_admin', 'cashier'],
#                 'title': f'EOD Locked - {eod_lock.branch.name}',
#                 'message': f'EOD {eod_lock.lock_number} locked for {eod_lock.lock_date}. No further modifications allowed.',
#                 'priority': 'high'
#             },
#             EodLock.REVERSED: {
#                 'recipient_roles': ['super_admin'],
#                 'title': f'EOD Reversed - {eod_lock.branch.name}',
#                 'message': f'EOD {eod_lock.lock_number} reversed for {eod_lock.lock_date}. Reason: {eod_lock.reversal_reason}',
#                 'priority': 'critical'
#             }
#         }
        
#         config = notifications_config.get(new_status)
#         if not config:
#             return
        
#         # Get recipients
#         recipients = User.objects.filter(
#             role__in=config['recipient_roles'],
#             is_active=True,
#             user_branches__branch=eod_lock.branch
#         ).distinct()
        
#         # Send notifications (assuming NotificationService exists)
#         for recipient in recipients:
#             try:
#                 notification_service.create_notification(
#                     user=recipient,
#                     title=config['title'],
#                     message=config['message'],
#                     notification_type='EOD_STATUS_CHANGE',
#                     priority=config['priority'],
#                     data={
#                         'eod_lock_id': str(eod_lock.id),
#                         'lock_number': eod_lock.lock_number,
#                         'lock_date': str(eod_lock.lock_date),
#                         'old_status': old_status,
#                         'new_status': new_status,
#                         'branch_id': str(eod_lock.branch.id),
#                         'branch_name': eod_lock.branch.name
#                     }
#                 )
#                 logger.info(f"Sent EOD notification to {recipient.email}")
#             except Exception as e:
#                 logger.error(f"Failed to send notification to {recipient.email}: {str(e)}")
        
#         # Also log to audit
#         log_action(
#             user=eod_lock.updated_by or eod_lock.prepared_by,
#             branch=eod_lock.branch,
#             instance=eod_lock,
#             action='EOD_NOTIFICATION_SENT',
#             metadata={
#                 'old_status': old_status,
#                 'new_status': new_status,
#                 'notification_type': 'status_change',
#                 'recipient_count': recipients.count()
#             }
#         )
        
#     except Exception as e:
#         logger.error(f"Failed to send EOD notifications: {str(e)}")


# def send_exception_notification(exception, old_status, new_status):
#     """
#     Send notifications for exception status changes
#     """
#     try:
#         # Only send for high/critical severity
#         if exception.severity not in [EodException.HIGH, EodException.CRITICAL]:
#             return
        
#         # Notification configurations
#         notifications_config = {
#             EodException.CREATED: {
#                 'title': f'New EOD Exception - {exception.severity}',
#                 'message': f'New exception {exception.exception_number}: {exception.title}',
#                 'priority': 'high' if exception.severity == EodException.HIGH else 'critical'
#             },
#             EodException.ASSIGNED: {
#                 'title': f'EOD Exception Assigned',
#                 'message': f'Exception {exception.exception_number} assigned to you',
#                 'priority': 'medium'
#             },
#             EodException.RESOLVED: {
#                 'title': f'EOD Exception Resolved',
#                 'message': f'Exception {exception.exception_number} has been resolved',
#                 'priority': 'low'
#             }
#         }
        
#         config_key = None
#         if new_status == EodException.IN_PROGRESS and old_status == EodException.OPEN:
#             config_key = 'ASSIGNED'
#         elif new_status == EodException.RESOLVED:
#             config_key = 'RESOLVED'
#         elif old_status is None:  # Newly created
#             config_key = 'CREATED'
        
#         if not config_key:
#             return
        
#         config = notifications_config.get(config_key)
#         if not config:
#             return
        
#         # Determine recipients
#         recipients = []
#         if config_key == 'CREATED':
#             # Send to managers
#             recipients = User.objects.filter(
#                 role__in=['clinic_manager', 'super_admin'],
#                 is_active=True,
#                 user_branches__branch=exception.branch
#             )
#         elif config_key == 'ASSIGNED' and exception.assigned_to:
#             # Send to assigned user
#             recipients = [exception.assigned_to]
#         elif config_key == 'RESOLVED' and exception.eod_lock:
#             # Send to EOD preparer and reviewer
#             recipients = User.objects.filter(
#                 id__in=[exception.eod_lock.prepared_by_id, exception.eod_lock.reviewed_by_id]
#             ).distinct()
        
#         # Send notifications
#         for recipient in recipients:
#             try:
#                 notification_service.create_notification(
#                     user=recipient,
#                     title=config['title'],
#                     message=config['message'],
#                     notification_type='EOD_EXCEPTION',
#                     priority=config['priority'],
#                     data={
#                         'exception_id': str(exception.id),
#                         'exception_number': exception.exception_number,
#                         'exception_type': exception.exception_type,
#                         'severity': exception.severity,
#                         'status': exception.status,
#                         'assigned_to': str(exception.assigned_to) if exception.assigned_to else None,
#                         'eod_lock_id': str(exception.eod_lock.id) if exception.eod_lock else None
#                     }
#                 )
#                 logger.info(f"Sent exception notification to {recipient.email}")
#             except Exception as e:
#                 logger.error(f"Failed to send exception notification: {str(e)}")
        
#     except Exception as e:
#         logger.error(f"Failed to send exception notifications: {str(e)}")


# # ===========================================
# # BULK UPDATE SIGNALS
# # ===========================================

# @receiver(m2m_changed, sender=EodLock.exceptions.through)
# def eod_lock_exceptions_changed(sender, instance, action, **kwargs):
#     """
#     Handle changes to EOD lock exceptions
#     """
#     if action in ['post_add', 'post_remove']:
#         # Update EOD lock discrepancy status
#         try:
#             has_unresolved = instance.exceptions.filter(
#                 status__in=[EodException.OPEN, EodException.IN_PROGRESS]
#             ).exists()
            
#             instance.has_discrepancies = has_unresolved
#             if not has_unresolved and instance.discrepancy_resolved:
#                 instance.discrepancy_resolved = True
#                 instance.discrepancy_resolved_at = timezone.now()
            
#             instance.save(update_fields=['has_discrepancies', 'discrepancy_resolved', 'discrepancy_resolved_at'])
            
#         except Exception as e:
#             logger.error(f"Failed to update EOD lock discrepancy status: {str(e)}")


# # ===========================================
# # MODEL TRACKER SETUP
# # ===========================================

# def init_model_trackers():
#     """
#     Initialize model trackers for change detection
#     This should be called in AppConfig.ready()
#     """
#     from django.db import models
    
#     # Add tracker to models
#     for model in [EodLock, DailySummary, CashReconciliation, EodException]:
#         if not hasattr(model, 'tracker'):
#             model.add_to_class('tracker', models.FieldTracker())


# # ===========================================
# # APP CONFIG INTEGRATION
# # ===========================================

# class EodSignalsConfig:
#     """
#     Configuration for EOD signals
#     """
#     @classmethod
#     def ready(cls):
#         """Initialize signals when app is ready"""
#         init_model_trackers()
#         logger.info("EOD signals initialized")





# apps/eod/signals.py

from django.db.models.signals import post_save, pre_save, post_delete, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import logging

from .models import EodLock, DailySummary, CashReconciliation, EodException
from apps.audit.services import log_action

User = get_user_model()
logger = logging.getLogger(__name__)


# ===========================================
# EOD LOCK SIGNALS
# ===========================================

@receiver(pre_save, sender=EodLock)
def eod_lock_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal for EodLock
    - Generate lock number if not set
    - Validate EOD transitions
    - Set calculated fields
    """
    # Generate lock number if not set
    if not instance.lock_number:
        instance.lock_number = instance.generate_lock_number()
    
    # Calculate net cash position
    if hasattr(instance, 'total_cash_collected') and hasattr(instance, 'total_cash_refunded'):
        instance.net_cash_position = instance.total_cash_collected - instance.total_cash_refunded
    
    # Set expected cash if opening cash is set
    if instance.opening_cash and not instance.expected_cash:
        instance.expected_cash = instance.opening_cash + instance.total_cash_collected - instance.total_cash_refunded
    
    # Calculate cash difference if actual cash is provided
    if instance.actual_cash is not None and instance.expected_cash is not None:
        instance.cash_difference = instance.actual_cash - instance.expected_cash
        
        # Check for discrepancies
        if abs(instance.cash_difference) > 0.50:  # 50 paise tolerance
            instance.has_discrepancies = True
            if not instance.discrepancy_notes:
                sign = "over" if instance.cash_difference > 0 else "under"
                instance.discrepancy_notes = f"Cash {sign} by ₹{abs(instance.cash_difference):.2f}"
    
    # Validate state transitions
    if instance.pk:
        try:
            old_instance = EodLock.objects.get(pk=instance.pk)
            
            # Prevent modifying locked EODs
            if old_instance.status == EodLock.LOCKED and instance.status != EodLock.LOCKED:
                raise ValidationError("Cannot modify a locked EOD")
            
            # Validate transitions
            valid_transitions = {
                EodLock.PREPARED: [EodLock.REVIEWED, EodLock.PREPARED],  # Can stay in PREPARED
                EodLock.REVIEWED: [EodLock.LOCKED, EodLock.PREPARED],
                EodLock.LOCKED: [EodLock.REVERSED],
                EodLock.REVERSED: []
            }
            
            old_status = old_instance.status
            new_status = instance.status
            
            if old_status != new_status and new_status not in valid_transitions.get(old_status, []):
                raise ValidationError(
                    f"Invalid EOD transition from '{old_status}' to '{new_status}'. "
                    f"Valid transitions: {valid_transitions.get(old_status, [])}"
                )
            
            # Set timestamps for status changes
            if old_status != new_status:
                if new_status == EodLock.REVIEWED:
                    instance.reviewed_at = timezone.now()
                elif new_status == EodLock.LOCKED:
                    instance.locked_at = timezone.now()
                elif new_status == EodLock.REVERSED:
                    instance.reversed_at = timezone.now()
                    
        except EodLock.DoesNotExist:
            pass
    
    # Auto-set prepared_by if not set
    if not instance.prepared_by and hasattr(instance, '_prepared_by_user'):
        instance.prepared_by = instance._prepared_by_user
    
    # Validate lock date is not in future
    if instance.lock_date and instance.lock_date > timezone.now().date():
        raise ValidationError("Cannot create EOD for future date")


@receiver(post_save, sender=EodLock)
def eod_lock_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for EodLock
    - Auto-create audit logs
    - Update related records
    """
    # Log the action
    action = 'EOD_CREATED' if created else 'EOD_UPDATED'
    
    # Track status changes (simple version without tracker)
    if not created and instance.pk:
        try:
            old_instance = EodLock.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                action = f'EOD_STATUS_CHANGED_{old_instance.status}_TO_{instance.status}'
                # Send notifications for status changes
                send_eod_status_notification(instance, old_instance.status, instance.status)
        except EodLock.DoesNotExist:
            pass
    
    # Create audit log
    try:
        # Get user from request context or use prepared_by
        user = getattr(instance, '_updated_by', instance.prepared_by)
        
        log_action(
            user=user,
            branch=instance.branch,
            instance=instance,
            action=action,
            device_id=getattr(instance, '_device_id', None),
            ip_address=getattr(instance, '_ip_address', None),
            metadata={
                'lock_number': instance.lock_number,
                'lock_date': str(instance.lock_date),
                'status': instance.status,
                'has_discrepancies': instance.has_discrepancies,
                'cash_difference': str(instance.cash_difference) if instance.cash_difference else None
            }
        )
    except Exception as e:
        logger.error(f"Failed to log EOD action: {str(e)}")
    
    # Update branch EOD status
    if instance.status == EodLock.LOCKED:
        try:
            # Lock all transactions for this date
            from apps.billing.models import Invoice
            from apps.payments.models import Payment, Refund
            
            # Update invoices
            Invoice.objects.filter(
                branch=instance.branch,
                invoice_date=instance.lock_date,
                eod_locked=False
            ).update(eod_locked=True, locked_eod=instance)
            
            # Update payments
            Payment.objects.filter(
                branch=instance.branch,
                payment_date__date=instance.lock_date,
                eod_locked=False
            ).update(eod_locked=True, locked_eod=instance)
            
            # Update refunds
            Refund.objects.filter(
                branch=instance.branch,
                requested_at__date=instance.lock_date,
                eod_locked=False
            ).update(eod_locked=True)
            
            logger.info(f"Locked transactions for EOD {instance.lock_number}")
            
        except Exception as e:
            logger.error(f"Failed to lock transactions for EOD {instance.lock_number}: {str(e)}")
    
    elif instance.status == EodLock.REVERSED:
        try:
            # Unlock all transactions for this date
            from apps.billing.models import Invoice
            from apps.payments.models import Payment, Refund
            
            # Update invoices
            Invoice.objects.filter(
                branch=instance.branch,
                invoice_date=instance.lock_date,
                eod_locked=True,
                locked_eod=instance
            ).update(eod_locked=False, locked_eod=None)
            
            # Update payments
            Payment.objects.filter(
                branch=instance.branch,
                payment_date__date=instance.lock_date,
                eod_locked=True,
                locked_eod=instance
            ).update(eod_locked=False, locked_eod=None)
            
            # Update refunds
            Refund.objects.filter(
                branch=instance.branch,
                requested_at__date=instance.lock_date,
                eod_locked=True
            ).update(eod_locked=False)
            
            logger.info(f"Unlocked transactions for reversed EOD {instance.lock_number}")
            
        except Exception as e:
            logger.error(f"Failed to unlock transactions for reversed EOD {instance.lock_number}: {str(e)}")


@receiver(pre_delete, sender=EodLock)
def eod_lock_pre_delete(sender, instance, **kwargs):
    """
    Prevent deletion of locked EODs
    """
    if instance.status == EodLock.LOCKED:
        raise ValidationError("Cannot delete a locked EOD")
    
    # Check if EOD is referenced by other records
    if instance.daily_summaries.exists():
        raise ValidationError("Cannot delete EOD with associated daily summaries")
    
    if instance.cash_reconciliations.exists():
        raise ValidationError("Cannot delete EOD with associated cash reconciliations")
    
    if instance.exceptions.exists():
        raise ValidationError("Cannot delete EOD with associated exceptions")


@receiver(post_delete, sender=EodLock)
def eod_lock_post_delete(sender, instance, **kwargs):
    """
    Post-delete signal for EODLock
    """
    try:
        user = getattr(instance, '_deleted_by', None)
        
        log_action(
            user=user,
            branch=instance.branch,
            instance=None,
            action='EOD_DELETED',
            metadata={
                'lock_number': instance.lock_number,
                'lock_date': str(instance.lock_date),
                'status': instance.status
            }
        )
    except Exception as e:
        logger.error(f"Failed to log EOD deletion: {str(e)}")


# ===========================================
# DAILY SUMMARY SIGNALS
# ===========================================

@receiver(pre_save, sender=DailySummary)
def daily_summary_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal for DailySummary
    """
    # Generate summary number if not set
    if not instance.summary_number:
        instance.summary_number = instance.generate_summary_number()
    
    # Validate period
    if instance.period_start and instance.period_end:
        if instance.period_start >= instance.period_end:
            raise ValidationError("Period start must be before period end")
        
        # Ensure summary date matches period
        if instance.summary_date and instance.summary_date != instance.period_start.date():
            instance.summary_date = instance.period_start.date()


@receiver(post_save, sender=DailySummary)
def daily_summary_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for DailySummary
    """
    action = 'DAILY_SUMMARY_CREATED' if created else 'DAILY_SUMMARY_UPDATED'
    
    try:
        user = getattr(instance, '_updated_by', instance.generated_by)
        
        log_action(
            user=user,
            branch=instance.branch,
            instance=instance,
            action=action,
            metadata={
                'summary_number': instance.summary_number,
                'summary_type': instance.summary_type,
                'summary_date': str(instance.summary_date),
                'period': f"{instance.period_start} to {instance.period_end}"
            }
        )
    except Exception as e:
        logger.error(f"Failed to log daily summary action: {str(e)}")


@receiver(pre_delete, sender=DailySummary)
def daily_summary_pre_delete(sender, instance, **kwargs):
    """
    Prevent deletion of summaries linked to locked EODs
    """
    if instance.eod_lock and instance.eod_lock.status == EodLock.LOCKED:
        raise ValidationError("Cannot delete summary linked to locked EOD")


# ===========================================
# CASH RECONCILIATION SIGNALS
# ===========================================

@receiver(pre_save, sender=CashReconciliation)
def cash_reconciliation_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal for CashReconciliation
    """
    # Generate reconciliation number if not set
    if not instance.reconciliation_number:
        instance.reconciliation_number = instance.generate_reconciliation_number()
    
    # Calculate difference if counted cash is provided
    if instance.counted_cash is not None and instance.declared_cash is not None:
        instance.difference = instance.counted_cash - instance.declared_cash
    
    # Validate cash amounts
    if instance.declared_cash < 0:
        raise ValidationError("Declared cash cannot be negative")
    
    if instance.counted_cash is not None and instance.counted_cash < 0:
        raise ValidationError("Counted cash cannot be negative")
    
    # Validate counter belongs to branch
    if instance.counter and instance.branch and instance.counter.branch != instance.branch:
        raise ValidationError("Counter does not belong to the specified branch")


@receiver(post_save, sender=CashReconciliation)
def cash_reconciliation_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for CashReconciliation
    """
    action = 'CASH_RECONCILIATION_CREATED' if created else 'CASH_RECONCILIATION_UPDATED'
    
    # Track verified status changes
    if not created and instance.pk:
        try:
            old_instance = CashReconciliation.objects.get(pk=instance.pk)
            if old_instance.verified != instance.verified:
                if instance.verified:
                    action = 'CASH_RECONCILIATION_VERIFIED'
                else:
                    action = 'CASH_RECONCILIATION_UNVERIFIED'
        except CashReconciliation.DoesNotExist:
            pass
    
    try:
        user = getattr(instance, '_updated_by', instance.cashier)
        
        log_action(
            user=user,
            branch=instance.branch,
            instance=instance,
            action=action,
            metadata={
                'reconciliation_number': instance.reconciliation_number,
                'type': instance.reconciliation_type,
                'declared_cash': str(instance.declared_cash),
                'counted_cash': str(instance.counted_cash) if instance.counted_cash else None,
                'difference': str(instance.difference) if instance.difference else None,
                'verified': instance.verified
            }
        )
    except Exception as e:
        logger.error(f"Failed to log cash reconciliation action: {str(e)}")
    
    # Link to EOD if not already linked
    if instance.eod_lock is None and instance.reconciliation_date:
        try:
            eod = EodLock.objects.filter(
                branch=instance.branch,
                lock_date=instance.reconciliation_date,
                status=EodLock.LOCKED
            ).first()
            
            if eod:
                instance.eod_lock = eod
                instance.save(update_fields=['eod_lock'])
                logger.info(f"Linked cash reconciliation {instance.reconciliation_number} to EOD {eod.lock_number}")
        except Exception as e:
            logger.error(f"Failed to link cash reconciliation to EOD: {str(e)}")


# ===========================================
# EOD EXCEPTION SIGNALS
# ===========================================

@receiver(pre_save, sender=EodException)
def eod_exception_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal for EodException
    """
    # Generate exception number if not set
    if not instance.exception_number:
        instance.exception_number = instance.generate_exception_number()
    
    # Set exception date from EOD if not set
    if not instance.exception_date and instance.eod_lock:
        instance.exception_date = instance.eod_lock.lock_date
    
    # Auto-assign high severity exceptions
    if instance.severity in [EodException.HIGH, EodException.CRITICAL] and not instance.assigned_to:
        # Find available manager
        try:
            managers = User.objects.filter(
                role__in=['clinic_manager', 'super_admin'],
                is_active=True
            ).order_by('?').first()  # Random manager
            
            if managers:
                instance.assigned_to = managers
                instance.assigned_at = timezone.now()
                instance.status = EodException.IN_PROGRESS
        except Exception as e:
            logger.error(f"Failed to auto-assign exception: {str(e)}")


@receiver(post_save, sender=EodException)
def eod_exception_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for EodException
    """
    action = 'EOD_EXCEPTION_CREATED' if created else 'EOD_EXCEPTION_UPDATED'
    
    # Track status changes
    if not created and instance.pk:
        try:
            old_instance = EodException.objects.get(pk=instance.pk)
            old_status = old_instance.status
            new_status = instance.status
            
            if old_status != new_status:
                if new_status == EodException.RESOLVED:
                    action = 'EOD_EXCEPTION_RESOLVED'
                elif new_status == EodException.CANCELLED:
                    action = 'EOD_EXCEPTION_CANCELLED'
                elif new_status == EodException.IN_PROGRESS:
                    action = 'EOD_EXCEPTION_ASSIGNED'
                
                # Send notification for high severity exceptions
                if instance.severity in [EodException.HIGH, EodException.CRITICAL]:
                    send_exception_notification(instance, old_status, new_status)
        except EodException.DoesNotExist:
            pass
    
    # Track assignment changes
    if not created and instance.pk:
        try:
            old_instance = EodException.objects.get(pk=instance.pk)
            if old_instance.assigned_to != instance.assigned_to:
                action = 'EOD_EXCEPTION_REASSIGNED'
        except EodException.DoesNotExist:
            pass
    
    try:
        user = getattr(instance, '_updated_by', None)
        if not user and instance.assigned_to:
            user = instance.assigned_to
        
        log_action(
            user=user,
            branch=instance.branch,
            instance=instance,
            action=action,
            metadata={
                'exception_number': instance.exception_number,
                'exception_type': instance.exception_type,
                'severity': instance.severity,
                'status': instance.status,
                'amount_involved': str(instance.amount_involved) if instance.amount_involved else None,
                'assigned_to': str(instance.assigned_to) if instance.assigned_to else None
            }
        )
    except Exception as e:
        logger.error(f"Failed to log exception action: {str(e)}")
    
    # Update EOD lock if exception is resolved
    if instance.status == EodException.RESOLVED and instance.eod_lock:
        try:
            # Check if all exceptions for this EOD are resolved
            unresolved_count = EodException.objects.filter(
                eod_lock=instance.eod_lock,
                status__in=[EodException.OPEN, EodException.IN_PROGRESS]
            ).count()
            
            if unresolved_count == 0:
                instance.eod_lock.discrepancy_resolved = True
                instance.eod_lock.discrepancy_resolved_by = instance.resolved_by
                instance.eod_lock.discrepancy_resolved_at = timezone.now()
                instance.eod_lock.resolution_notes = f"All exceptions resolved via exception {instance.exception_number}"
                instance.eod_lock.save()
                
                logger.info(f"Marked EOD {instance.eod_lock.lock_number} discrepancies as resolved")
        except Exception as e:
            logger.error(f"Failed to update EOD lock status: {str(e)}")


# ===========================================
# NOTIFICATION FUNCTIONS
# ===========================================

def send_eod_status_notification(eod_lock, old_status, new_status):
    """
    Send notifications for EOD status changes
    """
    try:
        # Notification configurations
        notifications_config = {
            EodLock.PREPARED: {
                'recipient_roles': ['clinic_manager', 'super_admin'],
                'title': f'EOD Prepared - {eod_lock.branch.name}',
                'message': f'EOD {eod_lock.lock_number} prepared for {eod_lock.lock_date} by {eod_lock.prepared_by}',
                'priority': 'medium'
            },
            EodLock.REVIEWED: {
                'recipient_roles': ['clinic_manager', 'cashier'],
                'title': f'EOD Reviewed - {eod_lock.branch.name}',
                'message': f'EOD {eod_lock.lock_number} reviewed for {eod_lock.lock_date}. Ready for locking.',
                'priority': 'medium'
            },
            EodLock.LOCKED: {
                'recipient_roles': ['clinic_manager', 'super_admin', 'cashier'],
                'title': f'EOD Locked - {eod_lock.branch.name}',
                'message': f'EOD {eod_lock.lock_number} locked for {eod_lock.lock_date}. No further modifications allowed.',
                'priority': 'high'
            },
            EodLock.REVERSED: {
                'recipient_roles': ['super_admin'],
                'title': f'EOD Reversed - {eod_lock.branch.name}',
                'message': f'EOD {eod_lock.lock_number} reversed for {eod_lock.lock_date}. Reason: {eod_lock.reversal_reason}',
                'priority': 'critical'
            }
        }
        
        config = notifications_config.get(new_status)
        if not config:
            return
        
        # Get recipients
        recipients = User.objects.filter(
            role__in=config['recipient_roles'],
            is_active=True
        ).distinct()
        
        # Filter by branch access if user has branch relationship
        if hasattr(eod_lock.branch, 'users'):
            recipients = recipients.filter(user_branches__branch=eod_lock.branch)
        
        # Send notifications (assuming NotificationService exists)
        for recipient in recipients:
            try:
                # This would use your actual notification service
                # For now, just log
                logger.info(f"Would send notification to {recipient.email}: {config['title']} - {config['message']}")
            except Exception as e:
                logger.error(f"Failed to send notification to {recipient.email}: {str(e)}")
        
        # Also log to audit
        log_action(
            user=eod_lock.updated_by or eod_lock.prepared_by,
            branch=eod_lock.branch,
            instance=eod_lock,
            action='EOD_NOTIFICATION_SENT',
            metadata={
                'old_status': old_status,
                'new_status': new_status,
                'notification_type': 'status_change',
                'recipient_count': recipients.count()
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to send EOD notifications: {str(e)}")


def send_exception_notification(exception, old_status, new_status):
    """
    Send notifications for exception status changes
    """
    try:
        # Only send for high/critical severity
        if exception.severity not in [EodException.HIGH, EodException.CRITICAL]:
            return
        
        # Notification configurations
        notifications_config = {
            'CREATED': {
                'title': f'New EOD Exception - {exception.severity}',
                'message': f'New exception {exception.exception_number}: {exception.title}',
                'priority': 'high' if exception.severity == EodException.HIGH else 'critical'
            },
            'ASSIGNED': {
                'title': f'EOD Exception Assigned',
                'message': f'Exception {exception.exception_number} assigned to you',
                'priority': 'medium'
            },
            'RESOLVED': {
                'title': f'EOD Exception Resolved',
                'message': f'Exception {exception.exception_number} has been resolved',
                'priority': 'low'
            }
        }
        
        config_key = None
        if new_status == EodException.IN_PROGRESS and old_status == EodException.OPEN:
            config_key = 'ASSIGNED'
        elif new_status == EodException.RESOLVED:
            config_key = 'RESOLVED'
        elif old_status is None:  # Newly created
            config_key = 'CREATED'
        
        if not config_key:
            return
        
        config = notifications_config.get(config_key)
        if not config:
            return
        
        # Determine recipients
        recipients = []
        if config_key == 'CREATED':
            # Send to managers
            recipients = User.objects.filter(
                role__in=['clinic_manager', 'super_admin'],
                is_active=True
            )
            if exception.branch and hasattr(exception.branch, 'users'):
                recipients = recipients.filter(user_branches__branch=exception.branch)
        elif config_key == 'ASSIGNED' and exception.assigned_to:
            # Send to assigned user
            recipients = [exception.assigned_to]
        elif config_key == 'RESOLVED' and exception.eod_lock:
            # Send to EOD preparer and reviewer
            recipients = User.objects.filter(
                id__in=[exception.eod_lock.prepared_by_id, exception.eod_lock.reviewed_by_id]
            ).distinct()
        
        # Send notifications
        for recipient in recipients:
            try:
                # This would use your actual notification service
                # For now, just log
                logger.info(f"Would send exception notification to {recipient.email}: {config['title']} - {config['message']}")
            except Exception as e:
                logger.error(f"Failed to send exception notification: {str(e)}")
        
    except Exception as e:
        logger.error(f"Failed to send exception notifications: {str(e)}")


# ===========================================
# SIMPLIFIED APP CONFIG
# ===========================================

def register_signals():
    """
    Register all signals
    This function is called from apps.py
    """
    # All signals are registered with @receiver decorators
    # This function just ensures signals are loaded
    logger.info("EOD signals registered")