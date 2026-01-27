# apps/visits/signals.py
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
import logging

from ..notifications.services import NotificationService 
from .models import Visit, Appointment, Queue
from apps.doctors.models import Doctor

logger = logging.getLogger(__name__)


# ===========================================
# VISIT SIGNALS
# ===========================================
@receiver(post_save, sender=Visit)
def visit_post_save(sender, instance, created, **kwargs):
    """Handle post-save operations for Visit"""
    
    if created:
        logger.info(f"New visit created: {instance.visit_id}")
        
        # Create queue entry for walk-ins
        if instance.appointment_source == 'WALK_IN' and instance.queue_number:
            Queue.objects.create(
                visit=instance,
                branch=instance.branch,
                doctor=instance.doctor,
                queue_number=instance.queue_number,
                status='WAITING'
            )
            logger.info(f"Queue entry created for visit {instance.visit_id}")
        
        # Send visit confirmation
        try:
            if instance.patient.user.email or instance.patient.user.phone:
                NotificationService.send_visit_confirmation(instance)
        except Exception as e:
            logger.error(f"Failed to send visit confirmation: {e}")
    
    # Update associated appointment if exists
    if hasattr(instance, 'appointment') and instance.appointment:
        appointment = instance.appointment
        if appointment.status != 'CHECKED_IN':
            appointment.status = 'CHECKED_IN'
            appointment.save()
            logger.info(f"Appointment {appointment.appointment_id} updated to CHECKED_IN")


@receiver(pre_save, sender=Visit)
def visit_pre_save(sender, instance, **kwargs):
    """Handle pre-save operations for Visit"""
    
    # Auto-calculate wait duration if checked in
    if instance.actual_checkin and not instance.wait_duration:
        if instance.scheduled_date and instance.scheduled_time:
            scheduled_dt = timezone.make_aware(
                timezone.datetime.combine(
                    instance.scheduled_date, 
                    instance.scheduled_time
                )
            )
            if instance.actual_checkin > scheduled_dt:
                instance.wait_duration = instance.actual_checkin - scheduled_dt
    
    # Auto-calculate consultation duration if checked out
    if (instance.actual_checkout and instance.actual_checkin 
            and not instance.consultation_duration):
        if instance.actual_checkout > instance.actual_checkin:
            instance.consultation_duration = instance.actual_checkout - instance.actual_checkin


# ===========================================
# APPOINTMENT SIGNALS
# ===========================================
@receiver(post_save, sender=Appointment)
def appointment_post_save(sender, instance, created, **kwargs):
    """Handle post-save operations for Appointment"""
    
    if created:
        logger.info(f"New appointment created: {instance.appointment_id}")
        
        # Send initial confirmation if patient has contact info
        try:
            if (instance.patient.user.email or instance.patient.user.phone) and instance.status == 'CONFIRMED':
                NotificationService.send_appointment_reminder(instance)
        except Exception as e:
            logger.error(f"Failed to send appointment confirmation: {e}")
    
    # Handle status changes
    elif 'update_fields' in kwargs and kwargs['update_fields'] is not None:
        if 'status' in [field.name for field in sender._meta.fields]:
            old_instance = sender.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                logger.info(f"Appointment {instance.appointment_id} status changed from {old_instance.status} to {instance.status}")


@receiver(pre_save, sender=Appointment)
def appointment_pre_save(sender, instance, **kwargs):
    """Handle pre-save operations for Appointment"""
    
    # Auto-send reminders 24 hours before appointment
    if (instance.appointment_date and instance.start_time 
            and not instance.reminder_sent):
        appointment_datetime = timezone.make_aware(
            timezone.datetime.combine(
                instance.appointment_date, 
                instance.start_time
            )
        )
        
        # If appointment is within 24 hours and not yet reminded
        time_until_appointment = appointment_datetime - timezone.now()
        if (timedelta(hours=0) < time_until_appointment <= timedelta(hours=24)
                and instance.status in ['SCHEDULED', 'CONFIRMED']):
            
            try:
                if NotificationService.send_appointment_reminder(instance):
                    instance.reminder_sent = True
                    instance.reminder_sent_at = timezone.now()
                    logger.info(f"Auto-reminder sent for appointment {instance.appointment_id}")
            except Exception as e:
                logger.error(f"Failed to send auto-reminder: {e}")


# ===========================================
# QUEUE SIGNALS
# ===========================================
@receiver(post_save, sender=Queue)
def queue_post_save(sender, instance, created, **kwargs):
    """Handle post-save operations for Queue"""
    
    if created:
        logger.info(f"New queue entry created: #{instance.queue_number} for visit {instance.visit.visit_id}")
    
    # Handle status changes
    elif 'update_fields' in kwargs and kwargs['update_fields'] is not None:
        if 'status' in [field.name for field in sender._meta.fields]:
            old_instance = sender.objects.get(pk=instance.pk)
            if old_instance.status != instance.status:
                logger.info(f"Queue #{instance.queue_number} status changed from {old_instance.status} to {instance.status}")
                
                # Send notification for certain status changes
                if instance.status == 'IN_PROGRESS':
                    try:
                        NotificationService.send_queue_update(instance)
                    except Exception as e:
                        logger.error(f"Failed to send queue update: {e}")


# ===========================================
# DOCTOR AVAILABILITY SIGNALS
# ===========================================
@receiver(post_save, sender=Doctor)
def doctor_post_save(sender, instance, created, **kwargs):
    """Handle post-save operations for Doctor"""
    
    if not created:
        # Check if doctor's active status changed
        if 'update_fields' in kwargs and kwargs['update_fields'] is not None:
            old_instance = sender.objects.get(pk=instance.pk)
            if old_instance.is_active != instance.is_active:
                
                if not instance.is_active:
                    # Cancel future appointments if doctor becomes inactive
                    future_appointments = Appointment.objects.filter(
                        doctor=instance,
                        appointment_date__gte=timezone.now().date(),
                        status__in=['SCHEDULED', 'CONFIRMED']
                    )
                    
                    for appointment in future_appointments:
                        appointment.status = 'CANCELLED'
                        appointment.cancellation_reason = 'Doctor unavailable'
                        appointment.cancelled_at = timezone.now()
                        appointment.save()
                    
                    logger.info(f"Cancelled {future_appointments.count()} appointments for doctor {instance.user.get_full_name()}")


# ===========================================
# APPOINTMENT CANCELLATION SIGNAL
# ===========================================
@receiver(pre_save, sender=Appointment)
def handle_appointment_cancellation(sender, instance, **kwargs):
    """Handle appointment cancellation"""
    
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            if (old_instance.status != 'CANCELLED' 
                    and instance.status == 'CANCELLED'):
                
                # Log cancellation
                logger.info(f"Appointment {instance.appointment_id} cancelled by {instance.cancelled_by}")
                
                # Free up the time slot for other appointments
                # (The availability check in serializer will handle this)
                
                # Send cancellation notification if patient has contact info
                try:
                    patient = instance.patient
                    if patient.user.email or patient.user.phone:
                        message = (
                            f"Your appointment with Dr. {instance.doctor.user.get_full_name()} "
                            f"scheduled for {instance.appointment_date.strftime('%A, %B %d, %Y')} "
                            f"at {instance.start_time.strftime('%I:%M %p')} has been cancelled.\n"
                            f"Reason: {instance.cancellation_reason or 'No reason provided'}"
                        )
                        
                        if patient.user.phone:
                            NotificationService.send_sms(patient.user.phone, message)
                        
                        if patient.user.email:
                            subject = f"Appointment Cancellation - {instance.appointment_date}"
                            NotificationService.send_email(patient.user.email, subject, message)
                            
                except Exception as e:
                    logger.error(f"Failed to send cancellation notification: {e}")
                    
        except sender.DoesNotExist:
            pass


# ===========================================
# NO-SHOW APPOINTMENT HANDLER (Cron/Scheduled Task)
# ===========================================
def handle_no_show_appointments():
    """Mark appointments as no-show if patient didn't show up"""
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.now().date()
    cutoff_time = timezone.now() - timedelta(minutes=30)  # 30 minutes grace period
    
    # Find appointments from today that haven't been converted to visits
    no_show_appointments = Appointment.objects.filter(
        appointment_date=today,
        start_time__lt=cutoff_time.time(),
        status__in=['SCHEDULED', 'CONFIRMED'],
        visit__isnull=True  # Not converted to visit
    )
    
    for appointment in no_show_appointments:
        appointment.status = 'NO_SHOW'
        appointment.save()
        
        # Update associated visit if exists
        if hasattr(appointment, 'visit') and appointment.visit:
            visit = appointment.visit
            if visit.status == 'REGISTERED':
                visit.status = 'NO_SHOW'
                visit.save()
    
    logger.info(f"Marked {no_show_appointments.count()} appointments as no-show")


# ===========================================
# AUTO-CLEANUP OF OLD QUEUE ENTRIES (Cron/Scheduled Task)
# ===========================================
def cleanup_old_queue_entries(days=30):
    """Archive or delete old queue entries"""
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=days)
    
    # Archive completed queue entries older than cutoff
    old_queues = Queue.objects.filter(
        status='COMPLETED',
        completed_at__lt=cutoff_date
    )
    
    count = old_queues.count()
    old_queues.delete()  # Or update to status='ARCHIVED' if you want to keep
    
    logger.info(f"Cleaned up {count} old queue entries older than {days} days")


# ===========================================
# APPOINTMENT REMINDER BATCH (Cron/Scheduled Task)
# ===========================================
def send_batch_appointment_reminders():
    """Send reminders for tomorrow's appointments"""
    from django.utils import timezone
    from datetime import timedelta
    
    tomorrow = timezone.now().date() + timedelta(days=1)
    
    # Get appointments for tomorrow that haven't been reminded
    tomorrow_appointments = Appointment.objects.filter(
        appointment_date=tomorrow,
        status__in=['SCHEDULED', 'CONFIRMED'],
        reminder_sent=False
    ).select_related('patient', 'patient__user', 'doctor', 'doctor__user', 'branch')
    
    sent_count = 0
    for appointment in tomorrow_appointments:
        try:
            if NotificationService.send_appointment_reminder(appointment):
                appointment.reminder_sent = True
                appointment.reminder_sent_at = timezone.now()
                appointment.save()
                sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send batch reminder for appointment {appointment.appointment_id}: {e}")
    
    logger.info(f"Sent batch reminders for {sent_count} appointments for {tomorrow}")


# ===========================================
# SIGNAL REGISTRATION
# ===========================================
def ready():
    """Import this function in apps.py to connect signals"""
    pass


# For Django 3.2+ and 4.x, connect signals in AppConfig
# Add to apps/visits/apps.py:
"""
from django.apps import AppConfig

class VisitsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.visits'
    
    def ready(self):
        import apps.visits.signals
"""