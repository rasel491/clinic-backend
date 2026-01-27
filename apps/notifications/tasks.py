# # apps/notifications/tasks.py (for Celery)
# from celery import shared_task
# from django.utils import timezone
# from datetime import timedelta
# from .services import NotificationService
# from .models import NotificationSetting, Appointment

# @shared_task
# def send_appointment_reminders():
#     """Send appointment reminders (run daily)"""
#     notification_service = NotificationService()
    
#     # Get tomorrow's appointments
#     tomorrow = timezone.now().date() + timedelta(days=1)
#     appointments = Appointment.objects.filter(
#         appointment_date=tomorrow,
#         status__in=['SCHEDULED', 'CONFIRMED'],
#         reminder_sent=False
#     )
    
#     for appointment in appointments:
#         # Check if reminder should be sent
#         setting = NotificationSetting.objects.filter(
#             category='appointment_reminder',
#             is_active=True
#         ).first()
        
#         if setting and setting.send_email:
#             # Send notification manually
#             notification_service.send_notification(
#                 recipient_type='patient',
#                 recipient_id=str(appointment.patient.id),
#                 recipient_contact=appointment.patient.user.email,
#                 notification_type='email',
#                 subject=f"Appointment Reminder - {appointment.appointment_date}",
#                 message=f"Reminder for your appointment with Dr. {appointment.doctor.user.get_full_name()}",
#                 branch=appointment.branch,
#                 related_object_type='appointment',
#                 related_object_id=appointment.appointment_id
#             )
            
#             appointment.reminder_sent = True
#             appointment.save()