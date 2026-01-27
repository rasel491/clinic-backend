# # apps/notifications/models.py
# from django.db import models
# from django.utils import timezone
# from django.core.validators import MinValueValidator, MaxValueValidator
# from django.contrib.postgres.fields import JSONField
# from core.mixins.audit_fields import AuditFieldsMixin
# from core.mixins.soft_delete import SoftDeleteMixin


# class NotificationTemplate(AuditFieldsMixin, SoftDeleteMixin):
#     """Template for notifications with placeholders"""
#     NOTIFICATION_TYPES = [
#         ('sms', 'SMS'),
#         ('email', 'Email'),
#         ('push', 'Push Notification'),
#         ('whatsapp', 'WhatsApp'),
#     ]
    
#     CATEGORIES = [
#         ('appointment', 'Appointment'),
#         ('payment', 'Payment'),
#         ('prescription', 'Prescription'),
#         ('reminder', 'Reminder'),
#         ('alert', 'System Alert'),
#         ('marketing', 'Marketing'),
#     ]
    
#     name = models.CharField(max_length=100)
#     notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
#     category = models.CharField(max_length=20, choices=CATEGORIES)
#     subject = models.CharField(max_length=200, blank=True, null=True)  # For email
#     body = models.TextField()  # Template with {placeholders}
#     variables = models.JSONField(default=dict, help_text="Available variables for this template")
#     is_active = models.BooleanField(default=True)
#     branch = models.ForeignKey('clinics.Branch', on_delete=models.CASCADE, related_name='notification_templates')
    
#     class Meta:
#         ordering = ['name']
#         unique_together = ['name', 'branch']
    
#     def __str__(self):
#         return f"{self.name} ({self.get_notification_type_display()})"


# class NotificationLog(AuditFieldsMixin):
#     """Log of all notifications sent"""
#     STATUS_CHOICES = [
#         ('pending', 'Pending'),
#         ('sent', 'Sent'),
#         ('delivered', 'Delivered'),
#         ('failed', 'Failed'),
#         ('read', 'Read'),
#     ]
    
#     PRIORITY_CHOICES = [
#         ('low', 'Low'),
#         ('medium', 'Medium'),
#         ('high', 'High'),
#         ('urgent', 'Urgent'),
#     ]
    
#     recipient_type = models.CharField(max_length=50)  # patient, doctor, staff, etc.
#     recipient_id = models.CharField(max_length=100)  # ID of recipient
#     recipient_contact = models.CharField(max_length=100, help_text="Phone/Email")
#     notification_type = models.CharField(max_length=20, choices=NotificationTemplate.NOTIFICATION_TYPES)
#     template = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, null=True, blank=True)
#     subject = models.CharField(max_length=200, blank=True, null=True)
#     message = models.TextField()
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
#     priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
#     scheduled_for = models.DateTimeField(null=True, blank=True)
#     sent_at = models.DateTimeField(null=True, blank=True)
#     delivered_at = models.DateTimeField(null=True, blank=True)
#     read_at = models.DateTimeField(null=True, blank=True)
#     error_message = models.TextField(blank=True, null=True)
#     metadata = models.JSONField(default=dict)
#     branch = models.ForeignKey('clinics.Branch', on_delete=models.CASCADE, related_name='notification_logs')
#     related_object_type = models.CharField(max_length=50, blank=True, null=True)  # appointment, payment, etc.
#     related_object_id = models.CharField(max_length=100, blank=True, null=True)
    
#     class Meta:
#         ordering = ['-created_at']
#         indexes = [
#             models.Index(fields=['recipient_contact', 'status']),
#             models.Index(fields=['branch', 'created_at']),
#             models.Index(fields=['status', 'scheduled_for']),
#         ]
    
#     def __str__(self):
#         return f"{self.notification_type} to {self.recipient_contact} ({self.status})"


# class SMSProvider(AuditFieldsMixin, SoftDeleteMixin):
#     """Configuration for SMS providers"""
#     PROVIDERS = [
#         ('twilio', 'Twilio'),
#         ('plivo', 'Plivo'),
#         ('msg91', 'MSG91'),
#         ('nexmo', 'Nexmo'),
#         ('custom', 'Custom API'),
#     ]
    
#     name = models.CharField(max_length=100)
#     provider_type = models.CharField(max_length=20, choices=PROVIDERS)
#     is_default = models.BooleanField(default=False)
#     account_sid = models.CharField(max_length=200, blank=True, null=True)
#     auth_token = models.CharField(max_length=200, blank=True, null=True)
#     api_key = models.CharField(max_length=200, blank=True, null=True)
#     api_secret = models.CharField(max_length=200, blank=True, null=True)
#     sender_id = models.CharField(max_length=20, blank=True, null=True)
#     endpoint_url = models.URLField(blank=True, null=True)
#     is_active = models.BooleanField(default=True)
#     branch = models.ForeignKey('clinics.Branch', on_delete=models.CASCADE, related_name='sms_providers')
    
#     class Meta:
#         ordering = ['-is_default', 'name']
    
#     def __str__(self):
#         return f"{self.name} ({self.get_provider_type_display()})"


# class EmailProvider(AuditFieldsMixin, SoftDeleteMixin):
#     """Configuration for Email providers"""
#     PROVIDERS = [
#         ('smtp', 'SMTP'),
#         ('sendgrid', 'SendGrid'),
#         ('mailgun', 'Mailgun'),
#         ('amazon_ses', 'Amazon SES'),
#         ('custom', 'Custom API'),
#     ]
    
#     name = models.CharField(max_length=100)
#     provider_type = models.CharField(max_length=20, choices=PROVIDERS)
#     is_default = models.BooleanField(default=False)
#     host = models.CharField(max_length=200, blank=True, null=True)
#     port = models.IntegerField(default=587)
#     username = models.CharField(max_length=200, blank=True, null=True)
#     password = models.CharField(max_length=200, blank=True, null=True)
#     use_tls = models.BooleanField(default=True)
#     use_ssl = models.BooleanField(default=False)
#     api_key = models.CharField(max_length=200, blank=True, null=True)
#     sender_email = models.EmailField()
#     sender_name = models.CharField(max_length=100, blank=True, null=True)
#     is_active = models.BooleanField(default=True)
#     branch = models.ForeignKey('clinics.Branch', on_delete=models.CASCADE, related_name='email_providers')
    
#     class Meta:
#         ordering = ['-is_default', 'name']
    
#     def __str__(self):
#         return f"{self.name} ({self.get_provider_type_display()})"


# class NotificationSetting(AuditFieldsMixin):
#     """Settings for notification delivery"""
#     CATEGORIES = [
#         ('appointment_confirmation', 'Appointment Confirmation'),
#         ('appointment_reminder', 'Appointment Reminder'),
#         ('appointment_cancellation', 'Appointment Cancellation'),
#         ('payment_receipt', 'Payment Receipt'),
#         ('prescription_ready', 'Prescription Ready'),
#         ('followup_reminder', 'Follow-up Reminder'),
#         ('birthday_wish', 'Birthday Wish'),
#         ('system_alert', 'System Alert'),
#     ]
    
#     category = models.CharField(max_length=50, choices=CATEGORIES, unique=True)
#     send_sms = models.BooleanField(default=True)
#     send_email = models.BooleanField(default=True)
#     send_whatsapp = models.BooleanField(default=False)
#     hours_before = models.IntegerField(default=24, help_text="Hours before event to send reminder")
#     is_active = models.BooleanField(default=True)
#     template_sms = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, 
#                                      null=True, blank=True, related_name='sms_settings')
#     template_email = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, 
#                                        null=True, blank=True, related_name='email_settings')
    
#     class Meta:
#         ordering = ['category']
    
#     def __str__(self):
#         return self.get_category_display()


# class NotificationQueue(AuditFieldsMixin):
#     """Queue for scheduled notifications"""
#     PRIORITY_CHOICES = [
#         (1, 'Lowest'),
#         (2, 'Low'),
#         (3, 'Normal'),
#         (4, 'High'),
#         (5, 'Highest'),
#     ]
    
#     notification_log = models.OneToOneField(NotificationLog, on_delete=models.CASCADE, related_name='queue_entry')
#     priority = models.IntegerField(choices=PRIORITY_CHOICES, default=3)
#     retry_count = models.IntegerField(default=0)
#     max_retries = models.IntegerField(default=3)
#     next_retry_at = models.DateTimeField(null=True, blank=True)
#     processing = models.BooleanField(default=False)
#     processed_at = models.DateTimeField(null=True, blank=True)
    
#     class Meta:
#         ordering = ['-priority', 'created_at']
#         indexes = [
#             models.Index(fields=['processing', 'next_retry_at']),
#         ]
    
#     def __str__(self):
#         return f"Queue for {self.notification_log}"



# apps/notifications/models.py
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin


class NotificationTemplate(AuditFieldsMixin, SoftDeleteMixin):
    """Template for notifications with placeholders"""
    NOTIFICATION_TYPES = [
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('push', 'Push Notification'),
        ('whatsapp', 'WhatsApp'),
    ]
    
    CATEGORIES = [
        ('appointment', 'Appointment'),
        ('payment', 'Payment'),
        ('prescription', 'Prescription'),
        ('reminder', 'Reminder'),
        ('alert', 'System Alert'),
        ('marketing', 'Marketing'),
    ]
    
    name = models.CharField(max_length=100)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    subject = models.CharField(max_length=200, blank=True, null=True)  # For email
    body = models.TextField()  # Template with {placeholders}
    variables = models.JSONField(default=dict, help_text="Available variables for this template")
    is_active = models.BooleanField(default=True)
    branch = models.ForeignKey('clinics.Branch', on_delete=models.CASCADE, related_name='notification_templates')
    
    class Meta:
        ordering = ['name']
        unique_together = ['name', 'branch']
    
    def __str__(self):
        return f"{self.name} ({self.get_notification_type_display()})"


class NotificationLog(AuditFieldsMixin):
    """Log of all notifications sent"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('read', 'Read'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    recipient_type = models.CharField(max_length=50)  # patient, doctor, staff, etc.
    recipient_id = models.CharField(max_length=100)  # ID of recipient
    recipient_contact = models.CharField(max_length=100, help_text="Phone/Email")
    notification_type = models.CharField(max_length=20, choices=NotificationTemplate.NOTIFICATION_TYPES)
    template = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    subject = models.CharField(max_length=200, blank=True, null=True)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict)
    branch = models.ForeignKey('clinics.Branch', on_delete=models.CASCADE, related_name='notification_logs')
    related_object_type = models.CharField(max_length=50, blank=True, null=True)  # appointment, payment, etc.
    related_object_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient_contact', 'status']),
            models.Index(fields=['branch', 'created_at']),
            models.Index(fields=['status', 'scheduled_for']),
        ]
    
    def __str__(self):
        return f"{self.notification_type} to {self.recipient_contact} ({self.status})"


class SMSProvider(AuditFieldsMixin, SoftDeleteMixin):
    """Configuration for SMS providers"""
    PROVIDERS = [
        ('twilio', 'Twilio'),
        ('plivo', 'Plivo'),
        ('msg91', 'MSG91'),
        ('nexmo', 'Nexmo'),
        ('custom', 'Custom API'),
    ]
    
    name = models.CharField(max_length=100)
    provider_type = models.CharField(max_length=20, choices=PROVIDERS)
    is_default = models.BooleanField(default=False)
    account_sid = models.CharField(max_length=200, blank=True, null=True)
    auth_token = models.CharField(max_length=200, blank=True, null=True)
    api_key = models.CharField(max_length=200, blank=True, null=True)
    api_secret = models.CharField(max_length=200, blank=True, null=True)
    sender_id = models.CharField(max_length=20, blank=True, null=True)
    endpoint_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    branch = models.ForeignKey('clinics.Branch', on_delete=models.CASCADE, related_name='sms_providers')
    
    class Meta:
        ordering = ['-is_default', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_provider_type_display()})"


class EmailProvider(AuditFieldsMixin, SoftDeleteMixin):
    """Configuration for Email providers"""
    PROVIDERS = [
        ('smtp', 'SMTP'),
        ('sendgrid', 'SendGrid'),
        ('mailgun', 'Mailgun'),
        ('amazon_ses', 'Amazon SES'),
        ('custom', 'Custom API'),
    ]
    
    name = models.CharField(max_length=100)
    provider_type = models.CharField(max_length=20, choices=PROVIDERS)
    is_default = models.BooleanField(default=False)
    host = models.CharField(max_length=200, blank=True, null=True)
    port = models.IntegerField(default=587)
    username = models.CharField(max_length=200, blank=True, null=True)
    password = models.CharField(max_length=200, blank=True, null=True)
    use_tls = models.BooleanField(default=True)
    use_ssl = models.BooleanField(default=False)
    api_key = models.CharField(max_length=200, blank=True, null=True)
    sender_email = models.EmailField()
    sender_name = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    branch = models.ForeignKey('clinics.Branch', on_delete=models.CASCADE, related_name='email_providers')
    
    class Meta:
        ordering = ['-is_default', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_provider_type_display()})"


class NotificationSetting(AuditFieldsMixin):
    """Settings for notification delivery"""
    CATEGORIES = [
        ('appointment_confirmation', 'Appointment Confirmation'),
        ('appointment_reminder', 'Appointment Reminder'),
        ('appointment_cancellation', 'Appointment Cancellation'),
        ('payment_receipt', 'Payment Receipt'),
        ('prescription_ready', 'Prescription Ready'),
        ('followup_reminder', 'Follow-up Reminder'),
        ('birthday_wish', 'Birthday Wish'),
        ('system_alert', 'System Alert'),
    ]
    
    category = models.CharField(max_length=50, choices=CATEGORIES, unique=True)
    send_sms = models.BooleanField(default=True)
    send_email = models.BooleanField(default=True)
    send_whatsapp = models.BooleanField(default=False)
    hours_before = models.IntegerField(default=24, help_text="Hours before event to send reminder")
    is_active = models.BooleanField(default=True)
    template_sms = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, 
                                     null=True, blank=True, related_name='sms_settings')
    template_email = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, 
                                       null=True, blank=True, related_name='email_settings')
    
    class Meta:
        ordering = ['category']
    
    def __str__(self):
        return self.get_category_display()


class NotificationQueue(AuditFieldsMixin):
    """Queue for scheduled notifications"""
    PRIORITY_CHOICES = [
        (1, 'Lowest'),
        (2, 'Low'),
        (3, 'Normal'),
        (4, 'High'),
        (5, 'Highest'),
    ]
    
    notification_log = models.OneToOneField(NotificationLog, on_delete=models.CASCADE, related_name='queue_entry')
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=3)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    processing = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-priority', 'created_at']
        indexes = [
            models.Index(fields=['processing', 'next_retry_at']),
        ]
    
    def __str__(self):
        return f"Queue for {self.notification_log}"