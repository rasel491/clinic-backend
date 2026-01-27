# apps/settings_core/services.py

from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    SystemSetting, BranchSetting, ClinicConfiguration,
    Holiday, TaxConfiguration, NotificationTemplate
)
from apps.clinics.models import Branch


class SettingsService:
    """Service for managing system and branch settings"""
    
    @staticmethod
    def get_setting(key, branch=None, default=None):
        """
        Get a setting value with branch override support
        """
        if branch:
            # Try branch setting first
            value = BranchSetting.get_branch_setting(branch, key, None)
            if value is not None:
                return value
        
        # Fall back to system setting
        return SystemSetting.get_setting(key, default)
    
    @staticmethod
    def set_setting(key, value, branch=None, user=None, override_system=True):
        """
        Set a setting value
        """
        if branch:
            BranchSetting.set_branch_setting(
                branch=branch,
                key=key,
                value=value,
                override_system=override_system
            )
        else:
            SystemSetting.set_setting(key, value, user)
    
    @staticmethod
    def get_clinic_configuration(branch):
        """
        Get clinic configuration for a branch
        """
        try:
            return ClinicConfiguration.objects.get(branch=branch)
        except ClinicConfiguration.DoesNotExist:
            # Create default configuration
            return ClinicConfiguration.objects.create(
                branch=branch,
                clinic_name=f"{branch.name} Dental Clinic",
                clinic_address=branch.address if hasattr(branch, 'address') else "",
                clinic_phone=branch.phone if hasattr(branch, 'phone') else "",
                clinic_email=branch.email if hasattr(branch, 'email') else "",
                created_by=None,  # Will be set by system
                updated_by=None
            )
    
    @staticmethod
    def is_working_day(branch, date):
        """
        Check if a date is a working day for a branch
        """
        config = SettingsService.get_clinic_configuration(branch)
        
        # Check if it's a holiday
        holidays = Holiday.objects.filter(branch=branch)
        for holiday in holidays:
            if holiday.is_holiday(date):
                return False
        
        # Check if it's a working day
        return config.is_working_day(date)
    
    @staticmethod
    def get_working_hours(branch, date=None):
        """
        Get working hours for a branch
        """
        config = SettingsService.get_clinic_configuration(branch)
        return config.get_working_hours(date)
    
    @staticmethod
    def calculate_tax(branch, amount, tax_type='default'):
        """
        Calculate tax for an amount
        """
        try:
            if tax_type == 'default':
                config = SettingsService.get_clinic_configuration(branch)
                tax_rate = config.default_tax_rate
            else:
                tax_config = TaxConfiguration.objects.get(
                    branch=branch,
                    code=tax_type,
                    is_active=True,
                    applicable_from__lte=timezone.now().date(),
                    applicable_to__gte=timezone.now().date()
                )
                tax_rate = tax_config.rate
            
            return (amount * tax_rate) / Decimal('100.00')
            
        except (TaxConfiguration.DoesNotExist, ClinicConfiguration.DoesNotExist):
            return Decimal('0.00')
    
    @staticmethod
    def get_notification_template(branch, trigger):
        """
        Get notification template for a trigger
        """
        try:
            # Try branch-specific template
            return NotificationTemplate.objects.get(
                branch=branch,
                trigger=trigger,
                is_active=True
            )
        except NotificationTemplate.DoesNotExist:
            # Try system-wide template (branch=None)
            try:
                return NotificationTemplate.objects.get(
                    branch=None,
                    trigger=trigger,
                    is_active=True
                )
            except NotificationTemplate.DoesNotExist:
                return None
    
    @staticmethod
    def render_notification(template, context, notification_type=None):
        """
        Render notification template with context
        """
        if not template:
            return None
        
        return template.render_template(context, notification_type)
    
    @staticmethod
    def get_available_time_slots(branch, date, doctor=None, duration=30):
        """
        Get available time slots for appointments
        """
        from apps.visits.models import Appointment
        from datetime import datetime, time
        
        config = SettingsService.get_clinic_configuration(branch)
        
        if not SettingsService.is_working_day(branch, date):
            return []
        
        working_hours = SettingsService.get_working_hours(branch, date)
        
        # Convert times to datetime objects for calculation
        start_dt = datetime.combine(date, working_hours['opening_time'])
        end_dt = datetime.combine(date, working_hours['closing_time'])
        
        # Generate time slots
        slots = []
        current = start_dt
        
        while current + timedelta(minutes=duration) <= end_dt:
            # Check lunch break
            lunch_start = datetime.combine(date, config.lunch_start)
            lunch_end = datetime.combine(date, config.lunch_end)
            
            if not (lunch_start <= current < lunch_end):
                # Check if slot is available
                appointments = Appointment.objects.filter(
                    branch=branch,
                    appointment_date=date,
                    start_time__lt=current.time(),
                    end_time__gt=current.time(),
                    status__in=['SCHEDULED', 'CONFIRMED']
                )
                
                if doctor:
                    appointments = appointments.filter(doctor=doctor)
                
                if appointments.count() < config.max_appointments_per_slot:
                    slots.append(current.time())
            
            current += timedelta(minutes=config.buffer_time + duration)
        
        return slots
    
    @staticmethod
    def initialize_default_settings():
        """
        Initialize default system settings
        """
        default_settings = [
            {
                'key': 'SYSTEM_NAME',
                'name': 'System Name',
                'category': SystemSetting.GENERAL,
                'data_type': SystemSetting.STRING,
                'string_value': 'Dental Clinic Management System',
                'description': 'Name of the dental clinic management system',
            },
            {
                'key': 'SYSTEM_VERSION',
                'name': 'System Version',
                'category': SystemSetting.GENERAL,
                'data_type': SystemSetting.STRING,
                'string_value': '1.0.0',
                'description': 'Current system version',
            },
            {
                'key': 'MAINTENANCE_MODE',
                'name': 'Maintenance Mode',
                'category': SystemSetting.MAINTENANCE,
                'data_type': SystemSetting.BOOLEAN,
                'boolean_value': False,
                'description': 'Enable maintenance mode',
            },
            {
                'key': 'ALLOW_REGISTRATION',
                'name': 'Allow New Registrations',
                'category': SystemSetting.SECURITY,
                'data_type': SystemSetting.BOOLEAN,
                'boolean_value': True,
                'description': 'Allow new patient registrations',
            },
            {
                'key': 'SESSION_TIMEOUT_MINUTES',
                'name': 'Session Timeout (minutes)',
                'category': SystemSetting.SECURITY,
                'data_type': SystemSetting.INTEGER,
                'integer_value': 30,
                'description': 'User session timeout in minutes',
            },
            {
                'key': 'MAX_LOGIN_ATTEMPTS',
                'name': 'Maximum Login Attempts',
                'category': SystemSetting.SECURITY,
                'data_type': SystemSetting.INTEGER,
                'integer_value': 5,
                'description': 'Maximum failed login attempts before lockout',
            },
            {
                'key': 'AUTO_LOGOUT_ENABLED',
                'name': 'Auto Logout Enabled',
                'category': SystemSetting.SECURITY,
                'data_type': SystemSetting.BOOLEAN,
                'boolean_value': True,
                'description': 'Enable automatic logout on inactivity',
            },
            {
                'key': 'BACKUP_ENABLED',
                'name': 'Automatic Backup Enabled',
                'category': SystemSetting.BACKUP,
                'data_type': SystemSetting.BOOLEAN,
                'boolean_value': True,
                'description': 'Enable automatic database backups',
            },
            {
                'key': 'BACKUP_RETENTION_DAYS',
                'name': 'Backup Retention Days',
                'category': SystemSetting.BACKUP,
                'data_type': SystemSetting.INTEGER,
                'integer_value': 30,
                'description': 'Number of days to keep backups',
            },
            {
                'key': 'SMS_NOTIFICATIONS_ENABLED',
                'name': 'SMS Notifications Enabled',
                'category': SystemSetting.NOTIFICATION,
                'data_type': SystemSetting.BOOLEAN,
                'boolean_value': True,
                'description': 'Enable SMS notifications',
            },
            {
                'key': 'EMAIL_NOTIFICATIONS_ENABLED',
                'name': 'Email Notifications Enabled',
                'category': SystemSetting.NOTIFICATION,
                'data_type': SystemSetting.BOOLEAN,
                'boolean_value': True,
                'description': 'Enable email notifications',
            },
            {
                'key': 'DEFAULT_CURRENCY',
                'name': 'Default Currency',
                'category': SystemSetting.FINANCIAL,
                'data_type': SystemSetting.STRING,
                'string_value': 'INR',
                'description': 'Default currency code',
            },
            {
                'key': 'DEFAULT_TAX_RATE',
                'name': 'Default Tax Rate',
                'category': SystemSetting.FINANCIAL,
                'data_type': SystemSetting.DECIMAL,
                'decimal_value': Decimal('18.00'),
                'description': 'Default tax rate percentage',
            },
            {
                'key': 'AUTO_INVOICE_NUMBERING',
                'name': 'Auto Invoice Numbering',
                'category': SystemSetting.FINANCIAL,
                'data_type': SystemSetting.BOOLEAN,
                'boolean_value': True,
                'description': 'Enable automatic invoice numbering',
            },
            {
                'key': 'ALLOW_DISCOUNTS',
                'name': 'Allow Discounts',
                'category': SystemSetting.FINANCIAL,
                'data_type': SystemSetting.BOOLEAN,
                'boolean_value': True,
                'description': 'Allow discounts on invoices',
            },
            {
                'key': 'MAX_DISCOUNT_PERCENTAGE',
                'name': 'Maximum Discount Percentage',
                'category': SystemSetting.FINANCIAL,
                'data_type': SystemSetting.DECIMAL,
                'decimal_value': Decimal('20.00'),
                'description': 'Maximum discount percentage allowed',
            },
            {
                'key': 'REQUIRE_DISCOUNT_APPROVAL',
                'name': 'Require Discount Approval',
                'category': SystemSetting.FINANCIAL,
                'data_type': SystemSetting.BOOLEAN,
                'boolean_value': True,
                'description': 'Require approval for discounts above threshold',
            },
            {
                'key': 'DISCOUNT_APPROVAL_THRESHOLD',
                'name': 'Discount Approval Threshold',
                'category': SystemSetting.FINANCIAL,
                'data_type': SystemSetting.DECIMAL,
                'decimal_value': Decimal('10.00'),
                'description': 'Discount percentage requiring approval',
            },
            {
                'key': 'AUTO_FOLLOWUP_DAYS',
                'name': 'Auto Follow-up Days',
                'category': SystemSetting.CLINICAL,
                'data_type': SystemSetting.INTEGER,
                'integer_value': 7,
                'description': 'Default follow-up days after treatment',
            },
            {
                'key': 'ENABLE_WAITLIST',
                'name': 'Enable Waitlist',
                'category': SystemSetting.CLINICAL,
                'data_type': SystemSetting.BOOLEAN,
                'boolean_value': True,
                'description': 'Enable waitlist for fully booked appointments',
            },
            {
                'key': 'MAX_WAITLIST_SIZE',
                'name': 'Maximum Waitlist Size',
                'category': SystemSetting.CLINICAL,
                'data_type': SystemSetting.INTEGER,
                'integer_value': 10,
                'description': 'Maximum number of patients on waitlist',
            },
        ]
        
        for setting_data in default_settings:
            SystemSetting.objects.get_or_create(
                key=setting_data['key'],
                defaults=setting_data
            )