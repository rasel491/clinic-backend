# # apps/visits/signals.py - SIMPLIFIED VERSION (no notifications)
# from django.db.models.signals import post_save, pre_save
# from django.dispatch import receiver
# from django.utils import timezone
# from datetime import timedelta
# import logging

# from .models import Visit, Appointment, Queue

# logger = logging.getLogger(__name__)


# @receiver(post_save, sender=Visit)
# def visit_post_save(sender, instance, created, **kwargs):
#     """Handle post-save operations for Visit"""
#     if created:
#         logger.info(f"New visit created: {instance.visit_id}")
        
#         # Create queue entry for walk-ins (NO NOTIFICATION)
#         if instance.appointment_source == 'WALK_IN' and instance.queue_number:
#             Queue.objects.create(
#                 visit=instance,
#                 branch=instance.branch,
#                 doctor=instance.doctor,
#                 queue_number=instance.queue_number,
#                 status='WAITING'
#             )
#             logger.info(f"Queue entry created for visit {instance.visit_id}")


# @receiver(pre_save, sender=Appointment)
# def appointment_pre_save(sender, instance, **kwargs):
#     """Handle pre-save for appointment (NO AUTO-REMINDERS)"""
#     # Just log changes, no auto-reminders
#     if instance.pk:
#         try:
#             old_instance = sender.objects.get(pk=instance.pk)
#             if old_instance.status != instance.status:
#                 logger.info(f"Appointment {instance.appointment_id} status changed from {old_instance.status} to {instance.status}")
#         except sender.DoesNotExist:
#             pass


# @receiver(post_save, sender=Doctor)
# def doctor_post_save(sender, instance, created, **kwargs):
#     """Handle doctor status changes"""
#     if not created:
#         # Check if doctor's active status changed
#         if 'update_fields' in kwargs and kwargs['update_fields'] is not None:
#             old_instance = sender.objects.get(pk=instance.pk)
#             if old_instance.is_active != instance.is_active:
                
#                 if not instance.is_active:
#                     # Cancel future appointments if doctor becomes inactive
#                     future_appointments = Appointment.objects.filter(
#                         doctor=instance,
#                         appointment_date__gte=timezone.now().date(),
#                         status__in=['SCHEDULED', 'CONFIRMED']
#                     )
                    
#                     for appointment in future_appointments:
#                         appointment.status = 'CANCELLED'
#                         appointment.cancellation_reason = 'Doctor unavailable'
#                         appointment.cancelled_at = timezone.now()
#                         appointment.save()
                    
#                     logger.info(f"Cancelled {future_appointments.count()} appointments for doctor {instance.user.get_full_name()}")