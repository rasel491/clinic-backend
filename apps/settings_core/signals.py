# apps/settings_core/signals.py

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache
import logging

from apps.audit.models import AuditLog
from .models import (
    SystemSetting, BranchSetting, ClinicConfiguration,
    Holiday, TaxConfiguration, NotificationTemplate,
    SMSConfiguration, EmailConfiguration
)

logger = logging.getLogger(__name__)

# Cache keys
SETTINGS_CACHE_PREFIX = 'settings:'
SYSTEM_SETTINGS_CACHE_KEY = 'system_settings_all'
BRANCH_SETTINGS_CACHE_PREFIX = 'branch_settings:'


def clear_settings_cache(branch_id=None):
    """Clear settings cache"""
    cache.delete(SYSTEM_SETTINGS_CACHE_KEY)
    
    if branch_id:
        cache_key = f"{BRANCH_SETTINGS_CACHE_PREFIX}{branch_id}"
        cache.delete(cache_key)
    else:
        # Clear all branch settings cache
        cache.delete_pattern(f"{BRANCH_SETTINGS_CACHE_PREFIX}*")


@receiver(post_save, sender=SystemSetting)
def system_setting_changed(sender, instance, created, **kwargs):
    """Handle system setting changes"""
    # Clear cache
    clear_settings_cache()
    
    # Log the change
    action = 'CREATED' if created else 'UPDATED'
    
    AuditLog.objects.create(
        user=instance.last_modified_by,
        action=f'SYSTEM_SETTING_{action}',
        model_name='SystemSetting',
        object_id=str(instance.id),
        details={
            'key': instance.key,
            'name': instance.name,
            'category': instance.category,
            'data_type': instance.data_type,
            'old_value': None,  # We don't have old value here
            'new_value': instance.get_value(),
            'requires_restart': instance.requires_restart
        },
        ip_address=None,  # Will be captured by middleware
        user_agent=None
    )
    
    logger.info(f"System setting {instance.key} {action.lower()}")


@receiver(post_save, sender=BranchSetting)
def branch_setting_changed(sender, instance, created, **kwargs):
    """Handle branch setting changes"""
    # Clear cache for this branch
    clear_settings_cache(instance.branch_id)
    
    # Log the change
    action = 'CREATED' if created else 'UPDATED'
    
    AuditLog.objects.create(
        user=instance.updated_by,
        action=f'BRANCH_SETTING_{action}',
        model_name='BranchSetting',
        object_id=str(instance.id),
        details={
            'branch_id': str(instance.branch_id),
            'branch_name': instance.branch.name,
            'key': instance.key,
            'name': instance.name,
            'override_system': instance.override_system,
            'value': instance.get_value()
        },
        ip_address=None,
        user_agent=None
    )


@receiver(post_save, sender=ClinicConfiguration)
def clinic_configuration_changed(sender, instance, created, **kwargs):
    """Handle clinic configuration changes"""
    # Clear cache for this branch
    clear_settings_cache(instance.branch_id)
    
    action = 'CREATED' if created else 'UPDATED'
    
    AuditLog.objects.create(
        user=instance.updated_by,
        action=f'CLINIC_CONFIG_{action}',
        model_name='ClinicConfiguration',
        object_id=str(instance.id),
        details={
            'branch_id': str(instance.branch_id),
            'branch_name': instance.branch.name,
            'clinic_name': instance.clinic_name,
            'changes': {
                'working_days': instance.working_days,
                'opening_time': str(instance.opening_time),
                'closing_time': str(instance.closing_time)
            }
        },
        ip_address=None,
        user_agent=None
    )


@receiver(post_save, sender=Holiday)
def holiday_changed(sender, instance, created, **kwargs):
    """Handle holiday changes"""
    clear_settings_cache(instance.branch_id)
    
    action = 'CREATED' if created else 'UPDATED'
    
    AuditLog.objects.create(
        user=instance.updated_by,
        action=f'HOLIDAY_{action}',
        model_name='Holiday',
        object_id=str(instance.id),
        details={
            'branch_id': str(instance.branch_id),
            'branch_name': instance.branch.name,
            'name': instance.name,
            'date': str(instance.date),
            'is_recurring': instance.is_recurring
        },
        ip_address=None,
        user_agent=None
    )


@receiver(post_save, sender=TaxConfiguration)
def tax_configuration_changed(sender, instance, created, **kwargs):
    """Handle tax configuration changes"""
    clear_settings_cache(instance.branch_id)
    
    action = 'CREATED' if created else 'UPDATED'
    
    AuditLog.objects.create(
        user=instance.updated_by,
        action=f'TAX_CONFIG_{action}',
        model_name='TaxConfiguration',
        object_id=str(instance.id),
        details={
            'branch_id': str(instance.branch_id),
            'branch_name': instance.branch.name,
            'name': instance.name,
            'code': instance.code,
            'rate': float(instance.rate),
            'is_active': instance.is_active
        },
        ip_address=None,
        user_agent=None
    )


@receiver(post_save, sender=SMSConfiguration)
def sms_configuration_changed(sender, instance, created, **kwargs):
    """Handle SMS configuration changes"""
    if instance.is_active:
        # Deactivate other SMS configurations for this branch
        SMSConfiguration.objects.filter(
            branch=instance.branch,
            is_active=True
        ).exclude(pk=instance.pk).update(is_active=False)
    
    action = 'CREATED' if created else 'UPDATED'
    
    AuditLog.objects.create(
        user=instance.updated_by,
        action=f'SMS_CONFIG_{action}',
        model_name='SMSConfiguration',
        object_id=str(instance.id),
        details={
            'branch_id': str(instance.branch_id),
            'branch_name': instance.branch.name,
            'provider': instance.provider,
            'is_active': instance.is_active
        },
        ip_address=None,
        user_agent=None
    )


@receiver(post_save, sender=EmailConfiguration)
def email_configuration_changed(sender, instance, created, **kwargs):
    """Handle email configuration changes"""
    if instance.is_active:
        # Deactivate other email configurations for this branch
        EmailConfiguration.objects.filter(
            branch=instance.branch,
            is_active=True
        ).exclude(pk=instance.pk).update(is_active=False)
    
    action = 'CREATED' if created else 'UPDATED'
    
    AuditLog.objects.create(
        user=instance.updated_by,
        action=f'EMAIL_CONFIG_{action}',
        model_name='EmailConfiguration',
        object_id=str(instance.id),
        details={
            'branch_id': str(instance.branch_id),
            'branch_name': instance.branch.name,
            'provider': instance.provider,
            'is_active': instance.is_active
        },
        ip_address=None,
        user_agent=None
    )


@receiver(pre_save, sender=NotificationTemplate)
def validate_notification_template(sender, instance, **kwargs):
    """Validate notification template before saving"""
    if instance.notification_type == 'SMS' and not instance.sms_template:
        raise ValueError("SMS template is required for SMS notification type")
    
    if instance.notification_type == 'EMAIL' and not instance.email_template:
        raise ValueError("Email template is required for Email notification type")
    
    if instance.notification_type == 'BOTH' and (not instance.sms_template or not instance.email_template):
        raise ValueError("Both SMS and email templates are required for BOTH notification type")


@receiver(post_save, sender=NotificationTemplate)
def notification_template_changed(sender, instance, created, **kwargs):
    """Handle notification template changes"""
    action = 'CREATED' if created else 'UPDATED'
    
    AuditLog.objects.create(
        user=instance.updated_by,
        action=f'NOTIFICATION_TEMPLATE_{action}',
        model_name='NotificationTemplate',
        object_id=str(instance.id),
        details={
            'branch_id': str(instance.branch_id) if instance.branch else None,
            'branch_name': instance.branch.name if instance.branch else 'System',
            'name': instance.name,
            'trigger': instance.trigger,
            'notification_type': instance.notification_type,
            'is_active': instance.is_active
        },
        ip_address=None,
        user_agent=None
    )


@receiver(post_delete, sender=SystemSetting)
def system_setting_deleted(sender, instance, **kwargs):
    """Handle system setting deletion"""
    clear_settings_cache()
    
    AuditLog.objects.create(
        user=None,  # System action
        action='SYSTEM_SETTING_DELETED',
        model_name='SystemSetting',
        object_id=str(instance.id),
        details={
            'key': instance.key,
            'name': instance.name,
            'category': instance.category
        },
        ip_address=None,
        user_agent=None
    )


@receiver(post_delete, sender=BranchSetting)
def branch_setting_deleted(sender, instance, **kwargs):
    """Handle branch setting deletion"""
    clear_settings_cache(instance.branch_id)
    
    AuditLog.objects.create(
        user=None,
        action='BRANCH_SETTING_DELETED',
        model_name='BranchSetting',
        object_id=str(instance.id),
        details={
            'branch_id': str(instance.branch_id),
            'branch_name': instance.branch.name,
            'key': instance.key,
            'name': instance.name
        },
        ip_address=None,
        user_agent=None
    )