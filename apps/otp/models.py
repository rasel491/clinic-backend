# apps/otp/models.py
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
import random
from datetime import timedelta

from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin


class OTPType:
    """OTP types for different purposes"""
    LOGIN = 'LOGIN'
    REGISTRATION = 'REGISTRATION'
    FORGOT_PASSWORD = 'FORGOT_PASSWORD'
    PHONE_VERIFICATION = 'PHONE_VERIFICATION'
    EMAIL_VERIFICATION = 'EMAIL_VERIFICATION'
    TRANSACTION = 'TRANSACTION'
    APPOINTMENT_CONFIRMATION = 'APPOINTMENT_CONFIRMATION'
    PAYMENT_VERIFICATION = 'PAYMENT_VERIFICATION'
    STAFF_INVITATION = 'STAFF_INVITATION'
    PATIENT_INVITATION = 'PATIENT_INVITATION'


class OTPChannel:
    """OTP delivery channels"""
    SMS = 'SMS'
    EMAIL = 'EMAIL'
    WHATSAPP = 'WHATSAPP'
    VOICE_CALL = 'VOICE_CALL'
    PUSH_NOTIFICATION = 'PUSH_NOTIFICATION'


class OTPPurpose:
    """Common OTP purposes with default settings"""
    PURPOSES = {
        'LOGIN': {
            'length': 6,
            'expiry_minutes': 5,
            'max_attempts': 3,
            'channels': ['SMS', 'EMAIL'],
            'template': 'login_otp'
        },
        'REGISTRATION': {
            'length': 6,
            'expiry_minutes': 10,
            'max_attempts': 3,
            'channels': ['SMS', 'EMAIL'],
            'template': 'registration_otp'
        },
        'FORGOT_PASSWORD': {
            'length': 6,
            'expiry_minutes': 10,
            'max_attempts': 3,
            'channels': ['SMS', 'EMAIL'],
            'template': 'forgot_password_otp'
        },
        'PHONE_VERIFICATION': {
            'length': 6,
            'expiry_minutes': 10,
            'max_attempts': 3,
            'channels': ['SMS', 'VOICE_CALL'],
            'template': 'phone_verification_otp'
        },
        'EMAIL_VERIFICATION': {
            'length': 6,
            'expiry_minutes': 30,
            'max_attempts': 3,
            'channels': ['EMAIL'],
            'template': 'email_verification_otp'
        },
        'TRANSACTION': {
            'length': 6,
            'expiry_minutes': 5,
            'max_attempts': 3,
            'channels': ['SMS', 'EMAIL'],
            'template': 'transaction_otp'
        },
        'APPOINTMENT_CONFIRMATION': {
            'length': 4,
            'expiry_minutes': 60,
            'max_attempts': 3,
            'channels': ['SMS', 'WHATSAPP'],
            'template': 'appointment_confirmation_otp'
        },
        'PAYMENT_VERIFICATION': {
            'length': 6,
            'expiry_minutes': 5,
            'max_attempts': 3,
            'channels': ['SMS', 'EMAIL'],
            'template': 'payment_verification_otp'
        }
    }


class OTPConfig(AuditFieldsMixin, SoftDeleteMixin):
    """Configuration for OTP settings per branch"""
    branch = models.ForeignKey('clinics.Branch', on_delete=models.CASCADE, related_name='otp_configs')
    
    # OTP Settings
    default_otp_length = models.PositiveIntegerField(default=6, validators=[MinValueValidator(4), MaxValueValidator(10)])
    default_expiry_minutes = models.PositiveIntegerField(default=5)
    max_attempts_per_otp = models.PositiveIntegerField(default=3)
    max_otp_per_day = models.PositiveIntegerField(default=10, help_text="Maximum OTPs per recipient per day")
    cool_down_period = models.PositiveIntegerField(default=60, help_text="Seconds between OTP requests")
    
    # Security
    enable_anti_spam = models.BooleanField(default=True)
    block_after_failed_attempts = models.PositiveIntegerField(default=5, help_text="Block after X failed attempts")
    block_duration_minutes = models.PositiveIntegerField(default=1440, help_text="Block duration in minutes (24 hours)")
    
    # Delivery
    default_channel = models.CharField(max_length=20, default=OTPChannel.SMS, choices=[
        (OTPChannel.SMS, 'SMS'),
        (OTPChannel.EMAIL, 'Email'),
        (OTPChannel.WHATSAPP, 'WhatsApp'),
        (OTPChannel.VOICE_CALL, 'Voice Call'),
        (OTPChannel.PUSH_NOTIFICATION, 'Push Notification'),
    ])
    fallback_channel = models.CharField(max_length=20, blank=True, choices=[
        ('', 'No Fallback'),
        (OTPChannel.SMS, 'SMS'),
        (OTPChannel.EMAIL, 'Email'),
        (OTPChannel.WHATSAPP, 'WhatsApp'),
        (OTPChannel.VOICE_CALL, 'Voice Call'),
    ])
    
    # Templates
    sms_template = models.TextField(default='Your OTP is {{otp}}. Valid for {{expiry}} minutes.')
    email_subject = models.CharField(max_length=200, default='Your OTP Code')
    email_template = models.TextField(default='<p>Your OTP is <strong>{{otp}}</strong></p><p>Valid for {{expiry}} minutes.</p>')
    
    # Verification
    auto_verify_on_match = models.BooleanField(default=True)
    require_captcha = models.BooleanField(default=False, help_text="Require CAPTCHA for OTP requests")
    captcha_threshold = models.PositiveIntegerField(default=3, help_text="Require CAPTCHA after X OTP requests")
    
    # Analytics
    total_otp_sent = models.PositiveIntegerField(default=0)
    total_verified = models.PositiveIntegerField(default=0)
    total_failed = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = "OTP Configuration"
        verbose_name_plural = "OTP Configurations"
        unique_together = ['branch']
    
    def __str__(self):
        return f"OTP Config - {self.branch.name}"
    
    def get_purpose_config(self, purpose):
        """Get configuration for specific purpose"""
        purpose_config = OTPPurpose.PURPOSES.get(purpose, {})
        return {
            'length': purpose_config.get('length', self.default_otp_length),
            'expiry_minutes': purpose_config.get('expiry_minutes', self.default_expiry_minutes),
            'max_attempts': purpose_config.get('max_attempts', self.max_attempts_per_otp),
            'channels': purpose_config.get('channels', [self.default_channel]),
            'template': purpose_config.get('template', 'default')
        }


class OTPRequest(AuditFieldsMixin):
    """OTP requests and verifications"""
    # Identification
    otp_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    reference_id = models.CharField(max_length=100, blank=True, help_text="External reference ID")
    
    # Recipient
    recipient_type = models.CharField(max_length=50, choices=[
        ('PATIENT', 'Patient'),
        ('DOCTOR', 'Doctor'),
        ('STAFF', 'Staff'),
        ('USER', 'User'),
        ('SYSTEM', 'System'),
    ])
    recipient_id = models.CharField(max_length=100, blank=True, null=True)
    recipient_contact = models.CharField(max_length=100, help_text="Email or Phone number")
    contact_type = models.CharField(max_length=10, choices=[
        ('EMAIL', 'Email'),
        ('PHONE', 'Phone'),
        ('USERNAME', 'Username'),
    ])
    
    # OTP Details
    otp_code = models.CharField(max_length=10)
    otp_type = models.CharField(max_length=50, choices=[
        (OTPType.LOGIN, 'Login'),
        (OTPType.REGISTRATION, 'Registration'),
        (OTPType.FORGOT_PASSWORD, 'Forgot Password'),
        (OTPType.PHONE_VERIFICATION, 'Phone Verification'),
        (OTPType.EMAIL_VERIFICATION, 'Email Verification'),
        (OTPType.TRANSACTION, 'Transaction'),
        (OTPType.APPOINTMENT_CONFIRMATION, 'Appointment Confirmation'),
        (OTPType.PAYMENT_VERIFICATION, 'Payment Verification'),
        (OTPType.STAFF_INVITATION, 'Staff Invitation'),
        (OTPType.PATIENT_INVITATION, 'Patient Invitation'),
    ])
    purpose = models.CharField(max_length=50, default='verification')
    
    # Channel
    channel = models.CharField(max_length=20, choices=[
        (OTPChannel.SMS, 'SMS'),
        (OTPChannel.EMAIL, 'Email'),
        (OTPChannel.WHATSAPP, 'WhatsApp'),
        (OTPChannel.VOICE_CALL, 'Voice Call'),
        (OTPChannel.PUSH_NOTIFICATION, 'Push Notification'),
    ])
    
    # Status
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('SENT', 'Sent'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Failed'),
        ('EXPIRED', 'Expired'),
        ('VERIFIED', 'Verified'),
        ('BLOCKED', 'Blocked'),
    ], default='PENDING')
    
    # Timing
    expires_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Attempts
    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    
    # Security
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_id = models.CharField(max_length=255, blank=True)
    
    # Related Object
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.CharField(max_length=100, blank=True)
    
    # Branch context
    branch = models.ForeignKey('clinics.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='otp_requests')
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['otp_id']),
            models.Index(fields=['recipient_contact', 'status']),
            models.Index(fields=['otp_type', 'status']),
            models.Index(fields=['expires_at', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.otp_type} - {self.recipient_contact} - {self.status}"
    
    def is_valid(self):
        """Check if OTP is valid for verification"""
        if self.status in ['VERIFIED', 'EXPIRED', 'BLOCKED']:
            return False
        
        if timezone.now() > self.expires_at:
            self.status = 'EXPIRED'
            self.save()
            return False
        
        if self.attempt_count >= self.max_attempts:
            self.status = 'BLOCKED'
            self.save()
            return False
        
        return True
    
    def verify(self, otp_code, increment_attempt=True):
        """Verify OTP code"""
        if not self.is_valid():
            return False
        
        if increment_attempt:
            self.attempt_count += 1
        
        if self.otp_code == otp_code:
            self.status = 'VERIFIED'
            self.verified_at = timezone.now()
            self.save()
            return True
        
        if self.attempt_count >= self.max_attempts:
            self.status = 'BLOCKED'
        
        self.save()
        return False
    
    def mark_sent(self):
        """Mark OTP as sent"""
        self.status = 'SENT'
        self.sent_at = timezone.now()
        self.save()
    
    def mark_delivered(self):
        """Mark OTP as delivered"""
        self.status = 'DELIVERED'
        self.delivered_at = timezone.now()
        self.save()
    
    def mark_failed(self, reason=''):
        """Mark OTP as failed"""
        self.status = 'FAILED'
        if reason:
            self.metadata['failure_reason'] = reason
        self.save()


class OTPBlacklist(AuditFieldsMixin):
    """Blacklist for suspicious/fraudulent activities"""
    TYPE_CHOICES = [
        ('IP', 'IP Address'),
        ('DEVICE', 'Device ID'),
        ('CONTACT', 'Contact (Email/Phone)'),
        ('USER', 'User Account'),
    ]
    
    REASON_CHOICES = [
        ('TOO_MANY_ATTEMPTS', 'Too many failed attempts'),
        ('SPAM', 'Suspected spam'),
        ('FRAUD', 'Suspected fraud'),
        ('ABUSE', 'System abuse'),
        ('SECURITY_BREACH', 'Security breach'),
        ('OTHER', 'Other'),
    ]
    
    blacklist_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    identifier = models.CharField(max_length=255, help_text="IP, Device ID, Email, Phone, or User ID")
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    description = models.TextField(blank=True)
    
    # Duration
    blocked_until = models.DateTimeField(null=True, blank=True)
    is_permanent = models.BooleanField(default=False)
    
    # Context
    branch = models.ForeignKey('clinics.Branch', on_delete=models.CASCADE, null=True, blank=True, related_name='otp_blacklists')
    
    # Stats
    attempt_count = models.PositiveIntegerField(default=0)
    last_attempt = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "OTP Blacklist"
        verbose_name_plural = "OTP Blacklists"
        unique_together = ['blacklist_type', 'identifier', 'branch']
        indexes = [
            models.Index(fields=['blacklist_type', 'identifier']),
            models.Index(fields=['blocked_until', 'is_permanent']),
        ]
    
    def __str__(self):
        return f"{self.blacklist_type}: {self.identifier}"
    
    def is_blocked(self):
        """Check if still blocked"""
        if self.is_permanent:
            return True
        
        if self.blocked_until:
            return timezone.now() < self.blocked_until
        
        return False


class OTPRateLimit(AuditFieldsMixin):
    """Rate limiting for OTP requests"""
    identifier = models.CharField(max_length=255, help_text="IP, Device ID, or User ID")
    identifier_type = models.CharField(max_length=20, choices=[
        ('IP', 'IP Address'),
        ('DEVICE', 'Device ID'),
        ('USER', 'User ID'),
    ])
    
    # Counters
    request_count = models.PositiveIntegerField(default=0)
    successful_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    
    # Time windows
    last_request = models.DateTimeField()
    daily_reset = models.DateField(auto_now_add=True)
    
    # Branch context
    branch = models.ForeignKey('clinics.Branch', on_delete=models.CASCADE, null=True, blank=True, related_name='otp_rate_limits')
    
    class Meta:
        verbose_name = "OTP Rate Limit"
        verbose_name_plural = "OTP Rate Limits"
        unique_together = ['identifier', 'identifier_type', 'branch']
        indexes = [
            models.Index(fields=['identifier', 'identifier_type']),
            models.Index(fields=['last_request']),
        ]
    
    def __str__(self):
        return f"{self.identifier_type}: {self.identifier}"
    
    def reset_daily_counters(self):
        """Reset daily counters if date changed"""
        today = timezone.now().date()
        if self.daily_reset != today:
            self.request_count = 0
            self.successful_count = 0
            self.failed_count = 0
            self.daily_reset = today
            self.save()


class OTPTemplate(AuditFieldsMixin, SoftDeleteMixin):
    """Templates for OTP messages"""
    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=20, choices=[
        ('SMS', 'SMS'),
        ('EMAIL', 'Email'),
        ('WHATSAPP', 'WhatsApp'),
        ('VOICE', 'Voice'),
    ])
    
    # Template content
    subject = models.CharField(max_length=200, blank=True, help_text="For email only")
    content = models.TextField(help_text="Template with {{variables}}")
    
    # Variables
    variables = models.JSONField(
        default=list,
        help_text="List of available variables: ['otp', 'expiry', 'name', 'clinic', etc.]"
    )
    
    # Purpose mapping
    purposes = models.JSONField(
        default=list,
        help_text="List of OTP purposes this template applies to"
    )
    
    # Branch specific
    branch = models.ForeignKey('clinics.Branch', on_delete=models.CASCADE, null=True, blank=True, related_name='otp_templates')
    is_default = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "OTP Template"
        verbose_name_plural = "OTP Templates"
        ordering = ['name']
        indexes = [
            models.Index(fields=['template_type', 'is_default']),
            models.Index(fields=['branch', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"
    
    def render(self, context):
        """Render template with context"""
        from django.template import Template, Context
        template = Template(self.content)
        return template.render(Context(context))