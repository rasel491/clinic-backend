# # apps/notifications/services.py
# import logging
# from django.utils import timezone
# from django.template import Template, Context
# from django.core.mail import send_mail
# from django.conf import settings
# import requests
# import json
# from datetime import timedelta

# from .models import (
#     NotificationTemplate, NotificationLog, SMSProvider,
#     EmailProvider, NotificationSetting, NotificationQueue
# )

# logger = logging.getLogger(__name__)


# class NotificationService:
#     """Service for handling notification operations"""
    
#     def __init__(self):
#         self.session = requests.Session()
    
#     def send_notification(self, **kwargs):
#         """Send a notification"""
#         try:
#             # Create notification log
#             notification_log = NotificationLog.objects.create(**kwargs)
            
#             # Queue for processing if scheduled for future
#             if notification_log.scheduled_for and notification_log.scheduled_for > timezone.now():
#                 NotificationQueue.objects.create(
#                     notification_log=notification_log,
#                     priority=self._get_priority_value(kwargs.get('priority', 'medium'))
#                 )
#                 return notification_log
            
#             # Process immediately
#             self._process_notification(notification_log)
#             return notification_log
            
#         except Exception as e:
#             logger.error(f"Error in send_notification: {str(e)}")
#             raise
    
#     def _process_notification(self, notification_log):
#         """Process a notification based on type"""
#         try:
#             if notification_log.notification_type == 'email':
#                 self._send_email(notification_log)
#             elif notification_log.notification_type == 'sms':
#                 self._send_sms(notification_log)
#             elif notification_log.notification_type == 'whatsapp':
#                 self._send_whatsapp(notification_log)
#             # Add other notification types as needed
            
#             notification_log.status = 'sent'
#             notification_log.sent_at = timezone.now()
            
#         except Exception as e:
#             notification_log.status = 'failed'
#             notification_log.error_message = str(e)
#             logger.error(f"Error processing notification {notification_log.id}: {str(e)}")
        
#         finally:
#             notification_log.save()
    
#     def _send_email(self, notification_log):
#         """Send email notification"""
#         try:
#             # Get default email provider for branch
#             provider = EmailProvider.objects.filter(
#                 branch=notification_log.branch,
#                 is_default=True,
#                 is_active=True
#             ).first()
            
#             if not provider:
#                 raise Exception("No active email provider configured")
            
#             # Prepare email
#             if provider.provider_type == 'smtp':
#                 self._send_smtp_email(provider, notification_log)
#             elif provider.provider_type == 'sendgrid':
#                 self._send_sendgrid_email(provider, notification_log)
#             # Add other providers as needed
            
#         except Exception as e:
#             raise Exception(f"Failed to send email: {str(e)}")
    
#     def _send_smtp_email(self, provider, notification_log):
#         """Send email via SMTP"""
#         from django.core.mail import EmailMessage
        
#         email = EmailMessage(
#             subject=notification_log.subject or '',
#             body=notification_log.message,
#             from_email=f"{provider.sender_name} <{provider.sender_email}>",
#             to=[notification_log.recipient_contact],
#         )
        
#         # Configure email backend based on provider settings
#         if provider.host:
#             settings.EMAIL_HOST = provider.host
#             settings.EMAIL_PORT = provider.port
#             settings.EMAIL_HOST_USER = provider.username
#             settings.EMAIL_HOST_PASSWORD = provider.password
#             settings.EMAIL_USE_TLS = provider.use_tls
#             settings.EMAIL_USE_SSL = provider.use_ssl
        
#         email.send()
    
#     def _send_sendgrid_email(self, provider, notification_log):
#         """Send email via SendGrid API"""
#         import sendgrid
#         from sendgrid.helpers.mail import Mail, Content
        
#         sg = sendgrid.SendGridAPIClient(api_key=provider.api_key)
        
#         message = Mail(
#             from_email=provider.sender_email,
#             to_emails=notification_log.recipient_contact,
#             subject=notification_log.subject or '',
#             html_content=notification_log.message
#         )
        
#         response = sg.client.mail.send.post(request_body=message.get())
#         if response.status_code != 202:
#             raise Exception(f"SendGrid API error: {response.status_code}")
    
#     def _send_sms(self, notification_log):
#         """Send SMS notification"""
#         try:
#             # Get default SMS provider for branch
#             provider = SMSProvider.objects.filter(
#                 branch=notification_log.branch,
#                 is_default=True,
#                 is_active=True
#             ).first()
            
#             if not provider:
#                 raise Exception("No active SMS provider configured")
            
#             if provider.provider_type == 'twilio':
#                 self._send_twilio_sms(provider, notification_log)
#             elif provider.provider_type == 'msg91':
#                 self._send_msg91_sms(provider, notification_log)
#             # Add other providers as needed
            
#         except Exception as e:
#             raise Exception(f"Failed to send SMS: {str(e)}")
    
#     def _send_twilio_sms(self, provider, notification_log):
#         """Send SMS via Twilio"""
#         from twilio.rest import Client
        
#         client = Client(provider.account_sid, provider.auth_token)
        
#         message = client.messages.create(
#             body=notification_log.message,
#             from_=provider.sender_id,
#             to=notification_log.recipient_contact
#         )
        
#         if message.error_code:
#             raise Exception(f"Twilio error: {message.error_message}")
    
#     def _send_msg91_sms(self, provider, notification_log):
#         """Send SMS via MSG91"""
#         url = provider.endpoint_url or "https://api.msg91.com/api/v2/sendsms"
        
#         payload = {
#             "sender": provider.sender_id,
#             "route": "4",
#             "country": "91",
#             "sms": [{
#                 "message": notification_log.message,
#                 "to": [notification_log.recipient_contact]
#             }]
#         }
        
#         headers = {
#             "authkey": provider.api_key,
#             "Content-Type": "application/json"
#         }
        
#         response = self.session.post(url, json=payload, headers=headers)
#         if response.status_code != 200:
#             raise Exception(f"MSG91 API error: {response.text}")
    
#     def _send_whatsapp(self, notification_log):
#         """Send WhatsApp notification"""
#         # Implement WhatsApp integration based on provider
#         pass
    
#     def process_queue(self, limit=10):
#         """Process queued notifications"""
#         queue_items = NotificationQueue.objects.filter(
#             processing=False,
#             next_retry_at__isnull=True
#         ).select_related('notification_log')[:limit]
        
#         processed = 0
#         for queue_item in queue_items:
#             queue_item.processing = True
#             queue_item.save()
            
#             try:
#                 self._process_notification(queue_item.notification_log)
#                 queue_item.processed_at = timezone.now()
#                 queue_item.delete()  # Remove from queue after processing
#                 processed += 1
                
#             except Exception as e:
#                 logger.error(f"Error processing queue item {queue_item.id}: {str(e)}")
                
#                 # Handle retries
#                 queue_item.retry_count += 1
#                 if queue_item.retry_count < queue_item.max_retries:
#                     # Schedule retry with exponential backoff
#                     backoff_minutes = 2 ** queue_item.retry_count
#                     queue_item.next_retry_at = timezone.now() + timedelta(minutes=backoff_minutes)
#                 else:
#                     # Max retries reached, mark as failed
#                     queue_item.notification_log.status = 'failed'
#                     queue_item.notification_log.error_message = f"Max retries ({queue_item.max_retries}) reached"
#                     queue_item.notification_log.save()
#                     queue_item.delete()
                
#                 queue_item.processing = False
#                 queue_item.save()
        
#         return processed
    
#     def retry_notification(self, notification_log):
#         """Retry a failed notification"""
#         try:
#             notification_log.status = 'pending'
#             notification_log.error_message = None
#             notification_log.save()
            
#             self._process_notification(notification_log)
#             return True
            
#         except Exception as e:
#             logger.error(f"Error retrying notification {notification_log.id}: {str(e)}")
#             return False
    
#     def test_sms_provider(self, provider, test_number):
#         """Test SMS provider configuration"""
#         test_message = "Test SMS from Dental Clinic System"
        
#         notification_log = NotificationLog.objects.create(
#             recipient_type='test',
#             recipient_id='test',
#             recipient_contact=test_number,
#             notification_type='sms',
#             message=test_message,
#             status='pending',
#             branch=provider.branch
#         )
        
#         try:
#             if provider.provider_type == 'twilio':
#                 self._send_twilio_sms(provider, notification_log)
#             elif provider.provider_type == 'msg91':
#                 self._send_msg91_sms(provider, notification_log)
#             else:
#                 raise Exception(f"Unsupported provider type: {provider.provider_type}")
            
#             notification_log.status = 'sent'
#             notification_log.sent_at = timezone.now()
#             notification_log.save()
#             return True
            
#         except Exception as e:
#             notification_log.status = 'failed'
#             notification_log.error_message = str(e)
#             notification_log.save()
#             return False
    
#     def test_email_provider(self, provider, test_email):
#         """Test Email provider configuration"""
#         test_subject = "Test Email from Dental Clinic System"
#         test_message = "This is a test email from the Dental Clinic Management System."
        
#         notification_log = NotificationLog.objects.create(
#             recipient_type='test',
#             recipient_id='test',
#             recipient_contact=test_email,
#             notification_type='email',
#             subject=test_subject,
#             message=test_message,
#             status='pending',
#             branch=provider.branch
#         )
        
#         try:
#             if provider.provider_type == 'smtp':
#                 self._send_smtp_email(provider, notification_log)
#             elif provider.provider_type == 'sendgrid':
#                 self._send_sendgrid_email(provider, notification_log)
#             else:
#                 raise Exception(f"Unsupported provider type: {provider.provider_type}")
            
#             notification_log.status = 'sent'
#             notification_log.sent_at = timezone.now()
#             notification_log.save()
#             return True
            
#         except Exception as e:
#             notification_log.status = 'failed'
#             notification_log.error_message = str(e)
#             notification_log.save()
#             return False
    
#     def _get_priority_value(self, priority_str):
#         """Convert priority string to integer value"""
#         priority_map = {
#             'lowest': 1,
#             'low': 2,
#             'medium': 3,
#             'high': 4,
#             'highest': 5,
#             'urgent': 5
#         }
#         return priority_map.get(priority_str.lower(), 3)
    
#     def render_template(self, template, variables):
#         """Render template with variables"""
#         try:
#             template_obj = Template(template)
#             context = Context(variables)
#             return template_obj.render(context)
#         except Exception as e:
#             logger.error(f"Error rendering template: {str(e)}")
#             raise Exception(f"Template rendering error: {str(e)}")


# apps/notifications/services.py
import logging
from django.utils import timezone
from django.template import Template, Context
from django.core.mail import EmailMessage
from django.conf import settings
import requests
import json
from datetime import timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .models import (
    NotificationTemplate, NotificationLog, SMSProvider,
    EmailProvider, NotificationSetting, NotificationQueue
)

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for handling notification operations"""
    
    def __init__(self):
        self.session = requests.Session()
    
    def send_notification(self, **kwargs):
        """Send a notification"""
        try:
            # Extract user if provided
            user = kwargs.pop('user', None)
            branch_id = kwargs.get('branch_id')
            
            if not branch_id:
                raise ValueError("branch_id is required")
            
            # Get branch
            from apps.clinics.models import Branch
            branch = Branch.objects.get(id=branch_id)
            
            # Create notification log
            notification_log = NotificationLog.objects.create(
                **kwargs,
                branch=branch,
                created_by=user,
                updated_by=user
            )
            
            # Queue for processing if scheduled for future
            if notification_log.scheduled_for and notification_log.scheduled_for > timezone.now():
                NotificationQueue.objects.create(
                    notification_log=notification_log,
                    priority=self._get_priority_value(kwargs.get('priority', 'medium'))
                )
                return notification_log
            
            # Process immediately
            self._process_notification(notification_log)
            return notification_log
            
        except Exception as e:
            logger.error(f"Error in send_notification: {str(e)}")
            raise
    
    def _process_notification(self, notification_log):
        """Process a notification based on type"""
        try:
            if notification_log.notification_type == 'email':
                self._send_email(notification_log)
            elif notification_log.notification_type == 'sms':
                self._send_sms(notification_log)
            elif notification_log.notification_type == 'whatsapp':
                self._send_whatsapp(notification_log)
            # Add other notification types as needed
            
            notification_log.status = 'sent'
            notification_log.sent_at = timezone.now()
            
        except Exception as e:
            notification_log.status = 'failed'
            notification_log.error_message = str(e)
            logger.error(f"Error processing notification {notification_log.id}: {str(e)}")
        
        finally:
            notification_log.save()
    
    def _send_email(self, notification_log):
        """Send email notification"""
        try:
            # Get default email provider for branch
            provider = EmailProvider.objects.filter(
                branch=notification_log.branch,
                is_default=True,
                is_active=True
            ).first()
            
            if not provider:
                raise Exception("No active email provider configured")
            
            # Prepare email
            if provider.provider_type == 'smtp':
                self._send_smtp_email(provider, notification_log)
            elif provider.provider_type == 'sendgrid':
                self._send_sendgrid_email(provider, notification_log)
            # Add other providers as needed
            
        except Exception as e:
            raise Exception(f"Failed to send email: {str(e)}")
    
    def _send_smtp_email(self, provider, notification_log):
        """Send email via SMTP (thread-safe implementation)"""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = notification_log.subject or 'No Subject'
            msg['From'] = f"{provider.sender_name or 'Dental Clinic'} <{provider.sender_email}>"
            msg['To'] = notification_log.recipient_contact
            
            # Add text/plain part
            text_part = MIMEText(notification_log.message, 'plain')
            msg.attach(text_part)
            
            # Connect to SMTP server
            if provider.use_ssl:
                server = smtplib.SMTP_SSL(provider.host, provider.port)
            else:
                server = smtplib.SMTP(provider.host, provider.port)
            
            if provider.use_tls and not provider.use_ssl:
                server.starttls()
            
            # Login if credentials provided
            if provider.username and provider.password:
                server.login(provider.username, provider.password)
            
            # Send email
            server.send_message(msg)
            server.quit()
            
        except Exception as e:
            raise Exception(f"SMTP error: {str(e)}")
    
    def _send_sendgrid_email(self, provider, notification_log):
        """Send email via SendGrid API"""
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Content
            
            sg = sendgrid.SendGridAPIClient(api_key=provider.api_key)
            
            message = Mail(
                from_email=provider.sender_email,
                to_emails=notification_log.recipient_contact,
                subject=notification_log.subject or '',
                html_content=notification_log.message
            )
            
            response = sg.client.mail.send.post(request_body=message.get())
            if response.status_code != 202:
                raise Exception(f"SendGrid API error: {response.status_code}")
                
        except ImportError:
            raise Exception("SendGrid library not installed. Install with: pip install sendgrid")
        except Exception as e:
            raise Exception(f"SendGrid error: {str(e)}")
    
    def _send_sms(self, notification_log):
        """Send SMS notification"""
        try:
            # Get default SMS provider for branch
            provider = SMSProvider.objects.filter(
                branch=notification_log.branch,
                is_default=True,
                is_active=True
            ).first()
            
            if not provider:
                raise Exception("No active SMS provider configured")
            
            if provider.provider_type == 'twilio':
                self._send_twilio_sms(provider, notification_log)
            elif provider.provider_type == 'msg91':
                self._send_msg91_sms(provider, notification_log)
            # Add other providers as needed
            
        except Exception as e:
            raise Exception(f"Failed to send SMS: {str(e)}")
    
    def _send_twilio_sms(self, provider, notification_log):
        """Send SMS via Twilio"""
        try:
            from twilio.rest import Client
            
            client = Client(provider.account_sid, provider.auth_token)
            
            message = client.messages.create(
                body=notification_log.message,
                from_=provider.sender_id or provider.account_sid[:12],
                to=notification_log.recipient_contact
            )
            
            if message.error_code:
                raise Exception(f"Twilio error: {message.error_message}")
                
        except ImportError:
            raise Exception("Twilio library not installed. Install with: pip install twilio")
        except Exception as e:
            raise Exception(f"Twilio error: {str(e)}")
    
    def _send_msg91_sms(self, provider, notification_log):
        """Send SMS via MSG91"""
        try:
            url = provider.endpoint_url or "https://api.msg91.com/api/v2/sendsms"
            
            payload = {
                "sender": provider.sender_id or "DENTAL",
                "route": "4",
                "country": "91",
                "sms": [{
                    "message": notification_log.message,
                    "to": [notification_log.recipient_contact]
                }]
            }
            
            headers = {
                "authkey": provider.api_key,
                "Content-Type": "application/json"
            }
            
            response = self.session.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise Exception(f"MSG91 API error: {response.text}")
                
        except Exception as e:
            raise Exception(f"MSG91 error: {str(e)}")
    
    def _send_whatsapp(self, notification_log):
        """Send WhatsApp notification"""
        # Implement WhatsApp integration based on provider
        # This is a placeholder - implement based on your WhatsApp provider
        raise Exception("WhatsApp notifications not yet implemented")
    
    def process_queue(self, limit=10):
        """Process queued notifications"""
        from django.db import transaction
        
        queue_items = NotificationQueue.objects.filter(
            processing=False,
            next_retry_at__isnull=True
        ).select_related('notification_log')[:limit]
        
        processed = 0
        for queue_item in queue_items:
            with transaction.atomic():
                # Mark as processing
                NotificationQueue.objects.filter(
                    id=queue_item.id,
                    processing=False
                ).update(processing=True)
                
                updated = NotificationQueue.objects.filter(
                    id=queue_item.id,
                    processing=True
                ).first()
                
                if not updated:
                    continue  # Another process picked it up
                
                try:
                    self._process_notification(updated.notification_log)
                    updated.delete()  # Remove from queue after processing
                    processed += 1
                    
                except Exception as e:
                    logger.error(f"Error processing queue item {updated.id}: {str(e)}")
                    
                    # Handle retries
                    updated.retry_count += 1
                    if updated.retry_count < updated.max_retries:
                        # Schedule retry with exponential backoff
                        backoff_minutes = 2 ** updated.retry_count
                        updated.next_retry_at = timezone.now() + timedelta(minutes=backoff_minutes)
                        updated.processing = False
                        updated.save()
                    else:
                        # Max retries reached, mark as failed
                        updated.notification_log.status = 'failed'
                        updated.notification_log.error_message = f"Max retries ({updated.max_retries}) reached"
                        updated.notification_log.save()
                        updated.delete()
        
        return processed
    
    def retry_notification(self, notification_log):
        """Retry a failed notification"""
        try:
            notification_log.status = 'pending'
            notification_log.error_message = None
            notification_log.save()
            
            self._process_notification(notification_log)
            return True
            
        except Exception as e:
            logger.error(f"Error retrying notification {notification_log.id}: {str(e)}")
            return False
    
    def test_sms_provider(self, provider, test_number):
        """Test SMS provider configuration"""
        test_message = "Test SMS from Dental Clinic System - This is a test message to verify SMS provider configuration."
        
        # Create a test notification log
        notification_log = NotificationLog.objects.create(
            recipient_type='test',
            recipient_id='test',
            recipient_contact=test_number,
            notification_type='sms',
            message=test_message,
            status='pending',
            branch=provider.branch,
            subject='Test SMS'
        )
        
        try:
            if provider.provider_type == 'twilio':
                self._send_twilio_sms(provider, notification_log)
            elif provider.provider_type == 'msg91':
                self._send_msg91_sms(provider, notification_log)
            else:
                raise Exception(f"Unsupported provider type: {provider.provider_type}")
            
            notification_log.status = 'sent'
            notification_log.sent_at = timezone.now()
            notification_log.save()
            return True
            
        except Exception as e:
            notification_log.status = 'failed'
            notification_log.error_message = str(e)
            notification_log.save()
            return False
    
    def test_email_provider(self, provider, test_email):
        """Test Email provider configuration"""
        test_subject = "Test Email from Dental Clinic System"
        test_message = "This is a test email from the Dental Clinic Management System to verify email provider configuration."
        
        notification_log = NotificationLog.objects.create(
            recipient_type='test',
            recipient_id='test',
            recipient_contact=test_email,
            notification_type='email',
            subject=test_subject,
            message=test_message,
            status='pending',
            branch=provider.branch
        )
        
        try:
            if provider.provider_type == 'smtp':
                self._send_smtp_email(provider, notification_log)
            elif provider.provider_type == 'sendgrid':
                self._send_sendgrid_email(provider, notification_log)
            else:
                raise Exception(f"Unsupported provider type: {provider.provider_type}")
            
            notification_log.status = 'sent'
            notification_log.sent_at = timezone.now()
            notification_log.save()
            return True
            
        except Exception as e:
            notification_log.status = 'failed'
            notification_log.error_message = str(e)
            notification_log.save()
            return False
    
    def _get_priority_value(self, priority_str):
        """Convert priority string to integer value"""
        priority_map = {
            'lowest': 1,
            'low': 2,
            'medium': 3,
            'high': 4,
            'highest': 5,
            'urgent': 5
        }
        return priority_map.get(priority_str.lower(), 3)
    
    def render_template(self, template, variables):
        """Render template with variables"""
        try:
            template_obj = Template(template)
            context = Context(variables)
            return template_obj.render(context)
        except Exception as e:
            logger.error(f"Error rendering template: {str(e)}")
            raise Exception(f"Template rendering error: {str(e)}")