# apps/settings_core/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import uuid

User = get_user_model()


class BaseModel(models.Model):
    """Base model with common fields"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class BranchScopedModel(models.Model):
    """Branch scoping mixin"""
    branch = models.ForeignKey('clinics.Branch', on_delete=models.PROTECT)
    
    class Meta:
        abstract = True


class AuditableModel(models.Model):
    """Audit fields mixin"""
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, editable=False,
        related_name='created_%(class)s'
    )
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, editable=False,
        related_name='updated_%(class)s'
    )
    
    class Meta:
        abstract = True


class BaseAppModel(BaseModel, AuditableModel, BranchScopedModel):
    """Combined base model for all apps"""
    class Meta:
        abstract = True


class SystemSetting(BaseModel):
    """
    Global system settings (not branch-specific)
    """
    # Setting Categories
    GENERAL = 'GENERAL'
    FINANCIAL = 'FINANCIAL'
    CLINICAL = 'CLINICAL'
    NOTIFICATION = 'NOTIFICATION'
    INTEGRATION = 'INTEGRATION'
    SECURITY = 'SECURITY'
    BACKUP = 'BACKUP'
    MAINTENANCE = 'MAINTENANCE'
    
    CATEGORY_CHOICES = [
        (GENERAL, 'General Settings'),
        (FINANCIAL, 'Financial Settings'),
        (CLINICAL, 'Clinical Settings'),
        (NOTIFICATION, 'Notification Settings'),
        (INTEGRATION, 'Integration Settings'),
        (SECURITY, 'Security Settings'),
        (BACKUP, 'Backup Settings'),
        (MAINTENANCE, 'Maintenance Settings'),
    ]
    
    # Data Types
    STRING = 'STRING'
    INTEGER = 'INTEGER'
    DECIMAL = 'DECIMAL'
    BOOLEAN = 'BOOLEAN'
    JSON = 'JSON'
    DATETIME = 'DATETIME'
    DATE = 'DATE'
    TIME = 'TIME'
    CHOICE = 'CHOICE'
    
    DATA_TYPE_CHOICES = [
        (STRING, 'String'),
        (INTEGER, 'Integer'),
        (DECIMAL, 'Decimal'),
        (BOOLEAN, 'Boolean'),
        (JSON, 'JSON'),
        (DATETIME, 'DateTime'),
        (DATE, 'Date'),
        (TIME, 'Time'),
        (CHOICE, 'Choice'),
    ]
    
    # Core fields
    key = models.CharField(max_length=200, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default=GENERAL)
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES, default=STRING)
    
    # Value storage
    string_value = models.CharField(max_length=500, blank=True)
    integer_value = models.IntegerField(null=True, blank=True)
    decimal_value = models.DecimalField(
        max_digits=15, decimal_places=4,
        null=True, blank=True
    )
    boolean_value = models.BooleanField(null=True, blank=True)
    json_value = models.JSONField(default=dict, blank=True)
    datetime_value = models.DateTimeField(null=True, blank=True)
    date_value = models.DateField(null=True, blank=True)
    time_value = models.TimeField(null=True, blank=True)
    
    # For CHOICE type
    choices = models.JSONField(
        default=list, blank=True,
        help_text="List of choices for CHOICE data type"
    )
    
    # Validation
    min_value = models.CharField(max_length=100, blank=True)
    max_value = models.CharField(max_length=100, blank=True)
    regex_pattern = models.CharField(max_length=500, blank=True)
    
    # Access control
    is_editable = models.BooleanField(default=True)
    requires_restart = models.BooleanField(default=False, help_text="Requires app restart to take effect")
    requires_superuser = models.BooleanField(default=False, help_text="Only superuser can modify")
    
    # Display
    sort_order = models.PositiveIntegerField(default=0)
    group_name = models.CharField(max_length=100, blank=True)
    help_text = models.TextField(blank=True)
    
    # Audit
    last_modified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='modified_settings'
    )
    last_modified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "System Setting"
        verbose_name_plural = "System Settings"
        ordering = ['category', 'sort_order', 'name']
        indexes = [
            models.Index(fields=['key']),
            models.Index(fields=['category', 'is_editable']),
            models.Index(fields=['requires_superuser']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.key})"
    
    def save(self, *args, **kwargs):
        # Clear other value fields based on data_type
        if self.data_type != self.STRING:
            self.string_value = ''
        if self.data_type != self.INTEGER:
            self.integer_value = None
        if self.data_type != self.DECIMAL:
            self.decimal_value = None
        if self.data_type != self.BOOLEAN:
            self.boolean_value = None
        if self.data_type != self.JSON:
            self.json_value = {}
        if self.data_type != self.DATETIME:
            self.datetime_value = None
        if self.data_type != self.DATE:
            self.date_value = None
        if self.data_type != self.TIME:
            self.time_value = None
        
        super().save(*args, **kwargs)
    
    def get_value(self):
        """Get the actual value based on data_type"""
        if self.data_type == self.STRING:
            return self.string_value
        elif self.data_type == self.INTEGER:
            return self.integer_value
        elif self.data_type == self.DECIMAL:
            return self.decimal_value
        elif self.data_type == self.BOOLEAN:
            return self.boolean_value
        elif self.data_type == self.JSON:
            return self.json_value
        elif self.data_type == self.DATETIME:
            return self.datetime_value
        elif self.data_type == self.DATE:
            return self.date_value
        elif self.data_type == self.TIME:
            return self.time_value
        elif self.data_type == self.CHOICE:
            return self.string_value
        return None
    
    def set_value(self, value, user=None):
        """Set the value based on data_type"""
        if self.data_type == self.STRING:
            self.string_value = str(value)
        elif self.data_type == self.INTEGER:
            self.integer_value = int(value)
        elif self.data_type == self.DECIMAL:
            self.decimal_value = Decimal(str(value))
        elif self.data_type == self.BOOLEAN:
            self.boolean_value = bool(value)
        elif self.data_type == self.JSON:
            self.json_value = value if isinstance(value, dict) else {}
        elif self.data_type == self.DATETIME:
            self.datetime_value = value
        elif self.data_type == self.DATE:
            self.date_value = value
        elif self.data_type == self.TIME:
            self.time_value = value
        elif self.data_type == self.CHOICE:
            self.string_value = str(value)
        
        if user:
            self.last_modified_by = user
        self.last_modified_at = timezone.now()
        self.save()
    
    @classmethod
    def get_setting(cls, key, default=None):
        """Get a system setting value"""
        try:
            setting = cls.objects.get(key=key)
            value = setting.get_value()
            return value if value is not None else default
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_setting(cls, key, value, user=None):
        """Set a system setting value"""
        try:
            setting = cls.objects.get(key=key)
            setting.set_value(value, user)
        except cls.DoesNotExist:
            # Create new setting (this shouldn't normally happen)
            setting = cls.objects.create(
                key=key,
                name=key.replace('_', ' ').title(),
                data_type=cls._infer_data_type(value)
            )
            setting.set_value(value, user)


class BranchSetting(BaseAppModel):
    """
    Branch-specific settings (overrides system settings)
    """
    # Setting Categories (similar to SystemSetting)
    CATEGORY_CHOICES = SystemSetting.CATEGORY_CHOICES
    
    # Data Types
    DATA_TYPE_CHOICES = SystemSetting.DATA_TYPE_CHOICES
    
    # Core fields
    key = models.CharField(max_length=200)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default=SystemSetting.GENERAL)
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES, default=SystemSetting.STRING)
    
    # Value storage
    string_value = models.CharField(max_length=500, blank=True)
    integer_value = models.IntegerField(null=True, blank=True)
    decimal_value = models.DecimalField(
        max_digits=15, decimal_places=4,
        null=True, blank=True
    )
    boolean_value = models.BooleanField(null=True, blank=True)
    json_value = models.JSONField(default=dict, blank=True)
    datetime_value = models.DateTimeField(null=True, blank=True)
    date_value = models.DateField(null=True, blank=True)
    time_value = models.TimeField(null=True, blank=True)
    
    # For CHOICE type
    choices = models.JSONField(default=list, blank=True)
    
    # Override control
    override_system = models.BooleanField(
        default=False,
        help_text="Override system-wide setting for this branch"
    )
    
    # Access control
    is_editable = models.BooleanField(default=True)
    requires_manager = models.BooleanField(default=False, help_text="Requires branch manager to modify")
    
    # Display
    sort_order = models.PositiveIntegerField(default=0)
    group_name = models.CharField(max_length=100, blank=True)
    help_text = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Branch Setting"
        verbose_name_plural = "Branch Settings"
        ordering = ['branch', 'category', 'sort_order', 'name']
        unique_together = ['branch', 'key']
        indexes = [
            models.Index(fields=['branch', 'key']),
            models.Index(fields=['branch', 'category']),
            models.Index(fields=['override_system']),
        ]
    
    def __str__(self):
        return f"{self.branch.name}: {self.name} ({self.key})"
    
    def get_value(self):
        """Get the actual value based on data_type"""
        if self.data_type == SystemSetting.STRING:
            return self.string_value
        elif self.data_type == SystemSetting.INTEGER:
            return self.integer_value
        elif self.data_type == SystemSetting.DECIMAL:
            return self.decimal_value
        elif self.data_type == SystemSetting.BOOLEAN:
            return self.boolean_value
        elif self.data_type == SystemSetting.JSON:
            return self.json_value
        elif self.data_type == SystemSetting.DATETIME:
            return self.datetime_value
        elif self.data_type == SystemSetting.DATE:
            return self.date_value
        elif self.data_type == SystemSetting.TIME:
            return self.time_value
        elif self.data_type == SystemSetting.CHOICE:
            return self.string_value
        return None
    
    def set_value(self, value):
        """Set the value based on data_type"""
        if self.data_type == SystemSetting.STRING:
            self.string_value = str(value)
        elif self.data_type == SystemSetting.INTEGER:
            self.integer_value = int(value)
        elif self.data_type == SystemSetting.DECIMAL:
            self.decimal_value = Decimal(str(value))
        elif self.data_type == SystemSetting.BOOLEAN:
            self.boolean_value = bool(value)
        elif self.data_type == SystemSetting.JSON:
            self.json_value = value if isinstance(value, dict) else {}
        elif self.data_type == SystemSetting.DATETIME:
            self.datetime_value = value
        elif self.data_type == SystemSetting.DATE:
            self.date_value = value
        elif self.data_type == SystemSetting.TIME:
            self.time_value = value
        elif self.data_type == SystemSetting.CHOICE:
            self.string_value = str(value)
        self.save()
    
    @classmethod
    def get_branch_setting(cls, branch, key, default=None):
        """Get a branch setting value"""
        try:
            setting = cls.objects.get(branch=branch, key=key)
            if setting.override_system:
                value = setting.get_value()
                return value if value is not None else default
        except cls.DoesNotExist:
            pass
        
        # Fall back to system setting
        return SystemSetting.get_setting(key, default)
    
    @classmethod
    def set_branch_setting(cls, branch, key, value, override_system=True):
        """Set a branch setting value"""
        setting, created = cls.objects.get_or_create(
            branch=branch,
            key=key,
            defaults={
                'name': key.replace('_', ' ').title(),
                'data_type': SystemSetting._infer_data_type(value),
                'override_system': override_system
            }
        )
        
        if not created and override_system:
            setting.override_system = True
        
        setting.set_value(value)


class ClinicConfiguration(BaseAppModel):
    """
    Clinic/Branch specific operational configuration
    """
    # Working Days
    MONDAY = 'MON'
    TUESDAY = 'TUE'
    WEDNESDAY = 'WED'
    THURSDAY = 'THU'
    FRIDAY = 'FRI'
    SATURDAY = 'SAT'
    SUNDAY = 'SUN'
    
    DAY_CHOICES = [
        (MONDAY, 'Monday'),
        (TUESDAY, 'Tuesday'),
        (WEDNESDAY, 'Wednesday'),
        (THURSDAY, 'Thursday'),
        (FRIDAY, 'Friday'),
        (SATURDAY, 'Saturday'),
        (SUNDAY, 'Sunday'),
    ]
    
    # Core configuration
    clinic_name = models.CharField(max_length=200)
    clinic_logo = models.ImageField(
        upload_to='clinic_logos/',
        null=True, blank=True
    )
    clinic_address = models.TextField()
    clinic_phone = models.CharField(max_length=20)
    clinic_email = models.EmailField()
    clinic_website = models.URLField(blank=True)
    
    # Working hours configuration
    working_days = models.JSONField(
        default=list,
        help_text="List of working days (e.g., ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'])"
    )
    opening_time = models.TimeField(default='09:00:00')
    closing_time = models.TimeField(default='18:00:00')
    lunch_start = models.TimeField(default='13:00:00')
    lunch_end = models.TimeField(default='14:00:00')
    
    # Appointment configuration
    appointment_duration = models.PositiveIntegerField(
        default=30,
        help_text="Default appointment duration in minutes"
    )
    max_appointments_per_slot = models.PositiveIntegerField(
        default=1,
        help_text="Maximum appointments per time slot"
    )
    buffer_time = models.PositiveIntegerField(
        default=15,
        help_text="Buffer time between appointments in minutes"
    )
    advance_booking_days = models.PositiveIntegerField(
        default=30,
        help_text="Maximum days in advance for booking"
    )
    
    # Financial configuration
    currency_symbol = models.CharField(max_length=5, default='₹')
    currency_code = models.CharField(max_length=3, default='INR')
    default_tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('18.00'),
        help_text="Default GST percentage"
    )
    
    # Invoice configuration
    invoice_prefix = models.CharField(max_length=10, default='INV')
    invoice_terms = models.TextField(blank=True)
    invoice_footer = models.TextField(blank=True)
    
    # Patient configuration
    default_follow_up_days = models.PositiveIntegerField(
        default=7,
        help_text="Default follow-up period in days"
    )
    send_appointment_reminders = models.BooleanField(default=True)
    reminder_hours_before = models.PositiveIntegerField(
        default=24,
        help_text="Send reminder hours before appointment"
    )
    
    # Clinical configuration
    default_consultation_fee = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=Decimal('500.00')
    )
    enable_digital_prescriptions = models.BooleanField(default=True)
    enable_treatment_plans = models.BooleanField(default=True)
    
    # Notification configuration
    send_sms_notifications = models.BooleanField(default=True)
    send_email_notifications = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Clinic Configuration"
        verbose_name_plural = "Clinic Configurations"
        constraints = [
            models.UniqueConstraint(
                fields=['branch'],
                name='unique_clinic_configuration'
            )
        ]
        indexes = [
            models.Index(fields=['branch']),
        ]
    
    def __str__(self):
        return f"Configuration for {self.clinic_name} ({self.branch})"
    
    def is_working_day(self, date):
        """Check if a date is a working day"""
        from datetime import datetime
        day_name = date.strftime('%a').upper()
        return day_name in self.working_days
    
    def get_working_hours(self, date=None):
        """Get working hours for a date"""
        return {
            'opening_time': self.opening_time,
            'closing_time': self.closing_time,
            'lunch_start': self.lunch_start,
            'lunch_end': self.lunch_end,
            'is_working_day': self.is_working_day(date) if date else True
        }


class Holiday(BaseAppModel):
    """
    Clinic holidays
    """
    name = models.CharField(max_length=200)
    date = models.DateField()
    is_recurring = models.BooleanField(
        default=True,
        help_text="Recur every year"
    )
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Holiday"
        verbose_name_plural = "Holidays"
        ordering = ['date']
        unique_together = ['branch', 'date']
        indexes = [
            models.Index(fields=['branch', 'date']),
            models.Index(fields=['is_recurring']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.date} ({self.branch})"
    
    def is_holiday(self, check_date):
        """Check if a date is a holiday"""
        if self.is_recurring:
            return check_date.month == self.date.month and check_date.day == self.date.day
        return check_date == self.date


class TaxConfiguration(BaseAppModel):
    """
    Tax rates and configurations
    """
    TAX_TYPE_CHOICES = [
        ('GST', 'Goods and Services Tax (GST)'),
        ('VAT', 'Value Added Tax (VAT)'),
        ('SALES_TAX', 'Sales Tax'),
        ('SERVICE_TAX', 'Service Tax'),
        ('OTHER', 'Other'),
    ]
    
    name = models.CharField(max_length=100)
    tax_type = models.CharField(max_length=20, choices=TAX_TYPE_CHOICES, default='GST')
    rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))]
    )
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    
    # Applicability
    applicable_from = models.DateField(default=timezone.now)
    applicable_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Scope
    apply_to_services = models.BooleanField(default=True)
    apply_to_products = models.BooleanField(default=True)
    apply_to_consultations = models.BooleanField(default=True)
    
    # GST specific
    sgst_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text="State GST rate (for GST type)"
    )
    cgst_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text="Central GST rate (for GST type)"
    )
    igst_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        help_text="Integrated GST rate (for interstate)"
    )
    
    class Meta:
        verbose_name = "Tax Configuration"
        verbose_name_plural = "Tax Configurations"
        ordering = ['name']
        indexes = [
            models.Index(fields=['code', 'is_active']),
            models.Index(fields=['tax_type', 'is_active']),
            models.Index(fields=['applicable_from', 'applicable_to']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.rate}%)"
    
    def calculate_tax(self, amount):
        """Calculate tax amount"""
        return (amount * self.rate) / Decimal('100.00')


class SMSConfiguration(BaseAppModel):
    """
    SMS gateway configuration
    """
    PROVIDER_CHOICES = [
        ('TWILIO', 'Twilio'),
        ('TEXTLOCAL', 'TextLocal'),
        ('MSG91', 'MSG91'),
        ('FAST2SMS', 'Fast2SMS'),
        ('CUSTOM', 'Custom API'),
    ]
    
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    is_active = models.BooleanField(default=True)
    
    # API Configuration
    api_key = models.CharField(max_length=500, blank=True)
    api_secret = models.CharField(max_length=500, blank=True)
    sender_id = models.CharField(max_length=20, blank=True)
    api_url = models.URLField(blank=True)
    
    # Settings
    priority = models.PositiveIntegerField(default=1, help_text="Lower number = higher priority")
    max_per_day = models.PositiveIntegerField(default=100, help_text="Maximum SMS per day")
    characters_per_sms = models.PositiveIntegerField(default=160)
    
    # Status
    total_sent = models.PositiveIntegerField(default=0)
    successful_sent = models.PositiveIntegerField(default=0)
    failed_sent = models.PositiveIntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "SMS Configuration"
        verbose_name_plural = "SMS Configurations"
        ordering = ['priority', 'provider']
        indexes = [
            models.Index(fields=['provider', 'is_active']),
            models.Index(fields=['is_active', 'priority']),
        ]
    
    def __str__(self):
        return f"{self.get_provider_display()} - {self.branch}"


class EmailConfiguration(BaseAppModel):
    """
    Email service configuration
    """
    PROVIDER_CHOICES = [
        ('SMTP', 'SMTP Server'),
        ('SENDGRID', 'SendGrid'),
        ('MAILGUN', 'Mailgun'),
        ('AWS_SES', 'Amazon SES'),
        ('GMAIL', 'Gmail API'),
    ]
    
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    is_active = models.BooleanField(default=True)
    
    # SMTP Configuration
    smtp_host = models.CharField(max_length=200, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_username = models.CharField(max_length=200, blank=True)
    smtp_password = models.CharField(max_length=500, blank=True)
    use_tls = models.BooleanField(default=True)
    use_ssl = models.BooleanField(default=False)
    
    # Email Settings
    from_email = models.EmailField()
    from_name = models.CharField(max_length=200, blank=True)
    reply_to = models.EmailField(blank=True)
    
    # API Configuration (for cloud providers)
    api_key = models.CharField(max_length=500, blank=True)
    api_secret = models.CharField(max_length=500, blank=True)
    api_url = models.URLField(blank=True)
    
    # Status
    total_sent = models.PositiveIntegerField(default=0)
    successful_sent = models.PositiveIntegerField(default=0)
    failed_sent = models.PositiveIntegerField(default=0)
    last_used = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Email Configuration"
        verbose_name_plural = "Email Configurations"
        ordering = ['provider', 'is_active']
        indexes = [
            models.Index(fields=['provider', 'is_active']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.get_provider_display()} - {self.branch}"


class NotificationTemplate(BaseAppModel):
    """
    Templates for notifications (SMS/Email)
    """
    NOTIFICATION_TYPE_CHOICES = [
        ('SMS', 'SMS'),
        ('EMAIL', 'Email'),
        ('BOTH', 'Both'),
    ]
    
    TRIGGER_CHOICES = [
        ('APPOINTMENT_REMINDER', 'Appointment Reminder'),
        ('APPOINTMENT_CONFIRMATION', 'Appointment Confirmation'),
        ('APPOINTMENT_CANCELLATION', 'Appointment Cancellation'),
        ('PAYMENT_RECEIPT', 'Payment Receipt'),
        ('INVOICE_GENERATED', 'Invoice Generated'),
        ('FOLLOW_UP_REMINDER', 'Follow-up Reminder'),
        ('BIRTHDAY_WISH', 'Birthday Wish'),
        ('NEW_PATIENT_WELCOME', 'New Patient Welcome'),
        ('LAB_RESULTS', 'Lab Results Ready'),
        ('CUSTOM', 'Custom'),
    ]
    
    # Core fields
    name = models.CharField(max_length=200)
    notification_type = models.CharField(max_length=10, choices=NOTIFICATION_TYPE_CHOICES)
    trigger = models.CharField(max_length=50, choices=TRIGGER_CHOICES)
    is_active = models.BooleanField(default=True)
    
    # Templates
    sms_template = models.TextField(blank=True, help_text="SMS template with {{variables}}")
    email_subject = models.CharField(max_length=200, blank=True)
    email_template = models.TextField(blank=True, help_text="HTML email template")
    
    # Variables
    available_variables = models.JSONField(
        default=list, blank=True,
        help_text="List of available template variables"
    )
    
    # Timing
    send_before_hours = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Send this many hours before event"
    )
    send_after_hours = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Send this many hours after event"
    )
    
    # Configuration
    is_required = models.BooleanField(
        default=False,
        help_text="This notification must be sent"
    )
    can_override = models.BooleanField(
        default=True,
        help_text="Can be overridden per branch"
    )
    
    class Meta:
        verbose_name = "Notification Template"
        verbose_name_plural = "Notification Templates"
        ordering = ['trigger', 'name']
        indexes = [
            models.Index(fields=['trigger', 'is_active']),
            models.Index(fields=['notification_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_trigger_display()})"
    
    def render_template(self, context, notification_type=None):
        """Render template with context"""
        if notification_type == 'SMS' or (not notification_type and self.notification_type in ['SMS', 'BOTH']):
            return self._render_sms_template(context)
        elif notification_type == 'EMAIL' or (not notification_type and self.notification_type in ['EMAIL', 'BOTH']):
            return self._render_email_template(context)
        return None
    
    def _render_sms_template(self, context):
        """Render SMS template"""
        from django.template import Template, Context
        template = Template(self.sms_template)
        return template.render(Context(context))
    
    def _render_email_template(self, context):
        """Render email template"""
        from django.template import Template, Context
        template = Template(self.email_template)
        return template.render(Context(context))


class RolePermission(BaseModel):
    """
    Role-based permissions configuration
    """
    role = models.ForeignKey(
        'accounts.Role',
        on_delete=models.CASCADE,
        related_name='django_permission_mappings'
    )
    permission = models.ForeignKey(
        'auth.Permission',
        on_delete=models.CASCADE,
        related_name='role_permission_mappings'
    )
    
    # Module permissions
    module = models.CharField(max_length=100)
    can_view = models.BooleanField(default=False)
    can_create = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_approve = models.BooleanField(default=False, help_text="Approval permissions")
    can_export = models.BooleanField(default=False, help_text="Export permissions")
    
    # Scope
    scope_all_branches = models.BooleanField(
        default=False,
        help_text="Can access all branches (for multi-branch roles)"
    )
    
    # Custom permissions (JSON)
    custom_permissions = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = "Role Permission"
        verbose_name_plural = "Role Permissions"
        unique_together = ['role', 'module']
        ordering = ['role', 'module']
        indexes = [
            models.Index(fields=['role', 'module']),
        ]
    
    def __str__(self):
        return f"{self.role.name} - {self.module}"
    
    def has_permission(self, action):
        """Check if role has specific permission"""
        if action == 'view':
            return self.can_view
        elif action == 'create':
            return self.can_create
        elif action == 'edit':
            return self.can_edit
        elif action == 'delete':
            return self.can_delete
        elif action == 'approve':
            return self.can_approve
        elif action == 'export':
            return self.can_export
        return False


class BackupConfiguration(BaseAppModel):
    """
    Backup and maintenance configurations
    """
    # Backup Types
    FULL = 'FULL'
    INCREMENTAL = 'INCREMENTAL'
    DIFFERENTIAL = 'DIFFERENTIAL'
    
    BACKUP_TYPE_CHOICES = [
        (FULL, 'Full Backup'),
        (INCREMENTAL, 'Incremental Backup'),
        (DIFFERENTIAL, 'Differential Backup'),
    ]
    
    # Storage Types
    LOCAL = 'LOCAL'
    AWS_S3 = 'AWS_S3'
    GOOGLE_DRIVE = 'GOOGLE_DRIVE'
    AZURE = 'AZURE'
    
    STORAGE_TYPE_CHOICES = [
        (LOCAL, 'Local Storage'),
        (AWS_S3, 'Amazon S3'),
        (GOOGLE_DRIVE, 'Google Drive'),
        (AZURE, 'Microsoft Azure'),
    ]
    
    # Core configuration
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPE_CHOICES, default=FULL)
    storage_type = models.CharField(max_length=20, choices=STORAGE_TYPE_CHOICES, default=LOCAL)
    is_active = models.BooleanField(default=True)
    
    # Schedule
    frequency = models.CharField(
        max_length=20,
        choices=[
            ('DAILY', 'Daily'),
            ('WEEKLY', 'Weekly'),
            ('MONTHLY', 'Monthly'),
        ],
        default='DAILY'
    )
    schedule_time = models.TimeField(default='02:00:00')
    retention_days = models.PositiveIntegerField(default=30, help_text="Keep backups for X days")
    
    # Storage configuration
    local_path = models.CharField(max_length=500, blank=True)
    aws_bucket = models.CharField(max_length=200, blank=True)
    aws_access_key = models.CharField(max_length=500, blank=True)
    aws_secret_key = models.CharField(max_length=500, blank=True)
    google_drive_folder = models.CharField(max_length=500, blank=True)
    azure_container = models.CharField(max_length=200, blank=True)
    
    # Notification
    notify_on_success = models.BooleanField(default=True)
    notify_on_failure = models.BooleanField(default=True)
    notify_email = models.EmailField(blank=True)
    
    # Status
    last_backup = models.DateTimeField(null=True, blank=True)
    last_backup_size = models.PositiveBigIntegerField(default=0)
    total_backups = models.PositiveIntegerField(default=0)
    successful_backups = models.PositiveIntegerField(default=0)
    failed_backups = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = "Backup Configuration"
        verbose_name_plural = "Backup Configurations"
        indexes = [
            models.Index(fields=['branch', 'is_active']),
            models.Index(fields=['frequency', 'is_active']),
        ]
    
    def __str__(self):
        return f"Backup Config - {self.branch}"


class AuditLogConfiguration(BaseAppModel):
    """
    Audit log configuration
    """
    # Log Levels
    DEBUG = 'DEBUG'
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'
    
    LOG_LEVEL_CHOICES = [
        (DEBUG, 'Debug'),
        (INFO, 'Info'),
        (WARNING, 'Warning'),
        (ERROR, 'Error'),
        (CRITICAL, 'Critical'),
    ]
    
    # Configuration
    log_level = models.CharField(max_length=10, choices=LOG_LEVEL_CHOICES, default=INFO)
    enable_login_logging = models.BooleanField(default=True)
    enable_data_change_logging = models.BooleanField(default=True)
    enable_financial_logging = models.BooleanField(default=True)
    enable_system_event_logging = models.BooleanField(default=True)
    
    # Retention
    retention_days = models.PositiveIntegerField(default=365, help_text="Keep logs for X days")
    archive_after_days = models.PositiveIntegerField(default=30, help_text="Archive logs after X days")
    
    # Export
    allow_log_export = models.BooleanField(default=True)
    export_requires_approval = models.BooleanField(default=True)
    
    # Monitoring
    enable_alerts = models.BooleanField(default=True)
    alert_on_multiple_failures = models.BooleanField(default=True)
    failure_threshold = models.PositiveIntegerField(default=5, help_text="Alert after X consecutive failures")
    
    class Meta:
        verbose_name = "Audit Log Configuration"
        verbose_name_plural = "Audit Log Configurations"
        constraints = [
            models.UniqueConstraint(
                fields=['branch'],
                name='unique_audit_log_configuration'
            )
        ]
        indexes = [
            models.Index(fields=['branch']),
        ]
    
    def __str__(self):
        return f"Audit Log Config - {self.branch}"