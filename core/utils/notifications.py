# core/utils/notifications.py (updated version)
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """Handle notifications for the system"""
    
    @staticmethod
    def send_appointment_reminder(appointment):
        """Send appointment reminder to patient"""
        try:
            # Get patient details
            patient = appointment.patient
            user = patient.user
            
            # Prepare message
            message = (
                f"Reminder: Your dental appointment with Dr. {appointment.doctor.user.get_full_name()} "
                f"is scheduled for {appointment.appointment_date.strftime('%A, %B %d, %Y')} "
                f"at {appointment.start_time.strftime('%I:%M %p')}.\n"
                f"Location: {appointment.branch.name}, {appointment.branch.address}\n"
                f"Purpose: {appointment.purpose or 'Regular Checkup'}"
            )
            
            # Send SMS if phone exists
            if user.phone:
                NotificationService.send_sms(user.phone, message)
            
            # Send email if email exists
            if user.email:
                subject = f"Appointment Reminder - {appointment.appointment_date}"
                NotificationService.send_email(user.email, subject, message)
            
            # Log to notifications app if available
            NotificationService._log_notification(
                recipient_type='patient',
                recipient_id=str(patient.id),
                recipient_contact=user.phone or user.email,
                notification_type='sms' if user.phone else 'email',
                subject=subject if user.email else None,
                message=message,
                status='sent',
                branch=appointment.branch,
                related_object_type='appointment',
                related_object_id=appointment.appointment_id
            )
            
            logger.info(f"Appointment reminder sent for appointment {appointment.appointment_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send appointment reminder: {str(e)}")
            
            # Log failure
            NotificationService._log_notification(
                recipient_type='patient',
                recipient_id=str(patient.id) if 'patient' in locals() else None,
                recipient_contact=user.phone or user.email if 'user' in locals() else None,
                notification_type='sms' if user.phone else 'email' if 'user' in locals() else None,
                subject=subject if 'subject' in locals() else None,
                message=message if 'message' in locals() else None,
                status='failed',
                error_message=str(e),
                branch=appointment.branch if 'appointment' in locals() else None,
                related_object_type='appointment' if 'appointment' in locals() else None,
                related_object_id=appointment.appointment_id if 'appointment' in locals() else None
            )
            
            return False
    
    @staticmethod
    def send_visit_confirmation(visit):
        """Send visit confirmation to patient"""
        try:
            patient = visit.patient
            user = patient.user
            
            message = (
                f"Your visit to {visit.branch.name} has been confirmed.\n"
                f"Visit ID: {visit.visit_id}\n"
                f"Doctor: Dr. {visit.doctor.user.get_full_name() if visit.doctor else 'To be assigned'}\n"
                f"Time: {visit.scheduled_date.strftime('%A, %B %d, %Y')} at {visit.scheduled_time.strftime('%I:%M %p')}\n"
                f"Queue Number: {visit.queue_number or 'Not assigned yet'}\n"
                f"Status: {visit.get_status_display()}"
            )
            
            sent_sms = False
            sent_email = False
            
            if user.phone:
                sent_sms = NotificationService.send_sms(user.phone, message)
            
            if user.email:
                subject = f"Visit Confirmation - {visit.visit_id}"
                sent_email = NotificationService.send_email(user.email, subject, message)
            
            # Log notification
            if sent_sms or sent_email:
                NotificationService._log_notification(
                    recipient_type='patient',
                    recipient_id=str(patient.id),
                    recipient_contact=user.phone or user.email,
                    notification_type='sms' if sent_sms else 'email',
                    subject=subject if sent_email else None,
                    message=message,
                    status='sent',
                    branch=visit.branch,
                    related_object_type='visit',
                    related_object_id=visit.visit_id
                )
            
            logger.info(f"Visit confirmation sent for visit {visit.visit_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send visit confirmation: {str(e)}")
            return False
    
    @staticmethod
    def send_queue_update(queue):
        """Send queue update to patient"""
        try:
            visit = queue.visit
            patient = visit.patient
            user = patient.user
            
            if queue.status == 'IN_PROGRESS':
                message = (
                    f"Your turn has come! Please proceed to Counter {queue.counter.number if queue.counter else 'the reception'}.\n"
                    f"Doctor: Dr. {queue.doctor.user.get_full_name() if queue.doctor else 'To be assigned'}"
                )
            elif queue.status == 'COMPLETED':
                message = "Your consultation has been completed. Please proceed to billing."
            else:
                message = (
                    f"Queue Update: You are currently number {queue.queue_number} in the queue.\n"
                    f"Estimated wait time: {queue.estimated_wait_minutes} minutes"
                )
            
            if user.phone:
                success = NotificationService.send_sms(user.phone, message)
                if success:
                    NotificationService._log_notification(
                        recipient_type='patient',
                        recipient_id=str(patient.id),
                        recipient_contact=user.phone,
                        notification_type='sms',
                        message=message,
                        status='sent',
                        branch=queue.branch,
                        related_object_type='queue',
                        related_object_id=str(queue.id)
                    )
            
            logger.info(f"Queue update sent for queue #{queue.queue_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send queue update: {str(e)}")
            return False
    
    @staticmethod
    def send_sms(phone_number, message, provider='default'):
        """Send SMS using configured provider"""
        try:
            # Check if notifications app is available
            try:
                from apps.notifications.models import SMSProvider
                sms_provider = SMSProvider.objects.filter(
                    is_default=True,
                    is_active=True
                ).first()
                
                if sms_provider:
                    # Use configured provider
                    if sms_provider.provider_type == 'twilio':
                        return NotificationService._send_sms_twilio(
                            phone_number, 
                            message, 
                            sms_provider.account_sid, 
                            sms_provider.auth_token,
                            sms_provider.sender_id
                        )
                    elif sms_provider.provider_type == 'custom':
                        # Implement custom provider logic
                        return NotificationService._send_sms_custom(
                            phone_number, 
                            message, 
                            sms_provider.endpoint_url,
                            sms_provider.api_key
                        )
                    # Add more providers as needed
            except ImportError:
                # Notifications app not available, use default
                pass
            
            # Fallback to settings-based Twilio
            if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
                logger.warning("Twilio credentials not configured")
                return False
            
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            
            client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone_number
            )
            return True
            
        except TwilioRestException as e:
            logger.error(f"Twilio error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Failed to send SMS: {str(e)}")
            return False
    
    @staticmethod
    def _send_sms_twilio(phone_number, message, account_sid, auth_token, from_number):
        """Send SMS using Twilio with custom credentials"""
        try:
            client = Client(account_sid, auth_token)
            client.messages.create(
                body=message,
                from_=from_number,
                to=phone_number
            )
            return True
        except Exception as e:
            logger.error(f"Twilio error: {str(e)}")
            return False
    
    @staticmethod
    def _send_sms_custom(phone_number, message, endpoint_url, api_key):
        """Send SMS using custom API"""
        # Implement custom SMS provider logic here
        # This is a template - you need to implement based on your provider
        try:
            import requests
            # Example for MSG91 or other providers
            headers = {
                'authkey': api_key,
                'Content-Type': 'application/json'
            }
            payload = {
                'sender': 'DENTAL',
                'route': '4',
                'country': '91',
                'sms': [{
                    'message': message,
                    'to': [phone_number]
                }]
            }
            
            response = requests.post(endpoint_url, json=payload, headers=headers)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Custom SMS provider error: {str(e)}")
            return False
    
    @staticmethod
    def send_email(to_email, subject, message, html_message=None):
        """Send email using configured provider"""
        try:
            # Check if notifications app is available
            try:
                from apps.notifications.models import EmailProvider
                email_provider = EmailProvider.objects.filter(
                    is_default=True,
                    is_active=True
                ).first()
                
                if email_provider:
                    # Use configured provider
                    if email_provider.provider_type == 'smtp':
                        return NotificationService._send_email_smtp(
                            to_email, subject, message, html_message, email_provider
                        )
                    elif email_provider.provider_type == 'sendgrid':
                        return NotificationService._send_email_sendgrid(
                            to_email, subject, message, html_message, email_provider.api_key
                        )
                    # Add more providers as needed
            except ImportError:
                # Notifications app not available, use default
                pass
            
            # Fallback to Django's default email
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                fail_silently=False,
                html_message=html_message
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False
    
    @staticmethod
    def _send_email_smtp(to_email, subject, message, html_message, provider):
        """Send email using SMTP provider"""
        try:
            from django.core.mail import send_mail as django_send_mail
            from django.conf import settings
            
            # Temporarily override settings for this provider
            old_email_settings = {
                'EMAIL_HOST': settings.EMAIL_HOST,
                'EMAIL_PORT': settings.EMAIL_PORT,
                'EMAIL_HOST_USER': settings.EMAIL_HOST_USER,
                'EMAIL_HOST_PASSWORD': settings.EMAIL_HOST_PASSWORD,
                'EMAIL_USE_TLS': settings.EMAIL_USE_TLS,
                'EMAIL_USE_SSL': settings.EMAIL_USE_SSL,
                'DEFAULT_FROM_EMAIL': settings.DEFAULT_FROM_EMAIL,
            }
            
            # Set provider settings
            import os
            os.environ['EMAIL_HOST'] = provider.host or ''
            os.environ['EMAIL_PORT'] = str(provider.port)
            os.environ['EMAIL_HOST_USER'] = provider.username or ''
            os.environ['EMAIL_HOST_PASSWORD'] = provider.password or ''
            os.environ['EMAIL_USE_TLS'] = 'True' if provider.use_tls else 'False'
            os.environ['EMAIL_USE_SSL'] = 'True' if provider.use_ssl else 'False'
            os.environ['DEFAULT_FROM_EMAIL'] = provider.sender_email
            
            # Reload settings
            from django.conf import settings
            from importlib import reload
            import sys
            if 'django.conf' in sys.modules:
                reload(sys.modules['django.conf'])
            
            # Send email
            django_send_mail(
                subject=subject,
                message=message,
                from_email=provider.sender_email,
                recipient_list=[to_email],
                fail_silently=False,
                html_message=html_message
            )
            
            # Restore old settings
            for key, value in old_email_settings.items():
                os.environ[key] = str(value) if value is not None else ''
            
            return True
        except Exception as e:
            logger.error(f"SMTP email error: {str(e)}")
            return False
    
    @staticmethod
    def _send_email_sendgrid(to_email, subject, message, html_message, api_key):
        """Send email using SendGrid"""
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Content
            
            sg = sendgrid.SendGridAPIClient(api_key=api_key)
            
            if html_message:
                content = Content("text/html", html_message)
            else:
                content = Content("text/plain", message)
            
            mail = Mail(
                from_email=settings.DEFAULT_FROM_EMAIL,
                to_emails=to_email,
                subject=subject,
                content=content
            )
            
            response = sg.client.mail.send.post(request_body=mail.get())
            return response.status_code == 202
        except Exception as e:
            logger.error(f"SendGrid error: {str(e)}")
            return False
    
    @staticmethod
    def _log_notification(
        recipient_type, recipient_id, recipient_contact, 
        notification_type, message, status, branch,
        subject=None, error_message=None,
        related_object_type=None, related_object_id=None
    ):
        """Log notification to notifications app"""
        try:
            from apps.notifications.models import NotificationLog
            
            NotificationLog.objects.create(
                recipient_type=recipient_type,
                recipient_id=recipient_id,
                recipient_contact=recipient_contact,
                notification_type=notification_type,
                subject=subject,
                message=message,
                status=status,
                sent_at=timezone.now() if status == 'sent' else None,
                error_message=error_message,
                branch=branch,
                related_object_type=related_object_type,
                related_object_id=related_object_id
            )
        except ImportError:
            # Notifications app not available
            pass
        except Exception as e:
            logger.error(f"Failed to log notification: {str(e)}")


# Convenience functions (backward compatibility)
def send_sms_reminder(phone, appointment):
    """Send SMS reminder for appointment"""
    return NotificationService.send_appointment_reminder(appointment)


def send_email_reminder(email, appointment):
    """Send email reminder for appointment"""
    return NotificationService.send_appointment_reminder(appointment)