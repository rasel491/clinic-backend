# apps/otp/signals.py

from django.db.models.signals import post_save, pre_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
import logging

from .models import OTPConfig, OTPRequest, OTPBlacklist, OTPRateLimit, OTPTemplate
from .services import OTPService
from apps.audit.services import log_action
from apps.notifications.services import NotificationService  # Assuming you'll have notifications app

User = get_user_model()
logger = logging.getLogger(__name__)
otp_service = OTPService()


# ===========================================
# OTP CONFIG SIGNALS
# ===========================================

@receiver(pre_save, sender=OTPConfig)
def otp_config_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal for OTPConfig
    - Validate configuration values
    - Set defaults
    """
    # Validate numeric values
    if instance.default_otp_length < 4 or instance.default_otp_length > 10:
        raise ValidationError("OTP length must be between 4 and 10 digits")
    
    if instance.default_expiry_minutes < 1 or instance.default_expiry_minutes > 60:
        raise ValidationError("OTP expiry must be between 1 and 60 minutes")
    
    if instance.max_attempts_per_otp < 1 or instance.max_attempts_per_otp > 10:
        raise ValidationError("Max attempts must be between 1 and 10")
    
    if instance.max_otp_per_day < 1 or instance.max_otp_per_day > 100:
        raise ValidationError("Max OTPs per day must be between 1 and 100")
    
    if instance.cool_down_period < 0 or instance.cool_down_period > 300:
        raise ValidationError("Cool down period must be between 0 and 300 seconds")
    
    if instance.block_after_failed_attempts < 1 or instance.block_after_failed_attempts > 20:
        raise ValidationError("Block after failed attempts must be between 1 and 20")
    
    if instance.block_duration_minutes < 1 or instance.block_duration_minutes > 10080:  # 7 days max
        raise ValidationError("Block duration must be between 1 minute and 7 days")
    
    if instance.captcha_threshold < 0 or instance.captcha_threshold > 50:
        raise ValidationError("CAPTCHA threshold must be between 0 and 50")
    
    # Validate fallback channel
    if instance.fallback_channel and instance.fallback_channel == instance.default_channel:
        raise ValidationError("Fallback channel cannot be same as default channel")
    
    # Ensure at least one template field is set
    if not instance.sms_template and not instance.email_template:
        instance.sms_template = 'Your OTP is {{otp}}. Valid for {{expiry}} minutes.'
        instance.email_subject = 'Your OTP Code'
        instance.email_template = '<p>Your OTP is <strong>{{otp}}</strong></p><p>Valid for {{expiry}} minutes.</p>'


@receiver(post_save, sender=OTPConfig)
def otp_config_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for OTPConfig
    - Create audit log
    - Update related templates
    """
    action = 'OTP_CONFIG_CREATED' if created else 'OTP_CONFIG_UPDATED'
    
    try:
        user = getattr(instance, '_updated_by', None)
        if not user:
            user = instance.created_by
        
        log_action(
            user=user,
            branch=instance.branch,
            instance=instance,
            action=action,
            metadata={
                'default_channel': instance.default_channel,
                'fallback_channel': instance.fallback_channel,
                'expiry_minutes': instance.default_expiry_minutes,
                'max_attempts': instance.max_attempts_per_otp,
                'daily_limit': instance.max_otp_per_day,
                'enable_anti_spam': instance.enable_anti_spam,
                'require_captcha': instance.require_captcha
            }
        )
    except Exception as e:
        logger.error(f"Failed to log OTP config action: {str(e)}")
    
    # Create default templates if they don't exist
    if created:
        create_default_templates(instance)


def create_default_templates(config):
    """Create default OTP templates for a config"""
    try:
        # Default SMS templates
        sms_templates = [
            {
                'name': 'Login OTP',
                'template_type': 'SMS',
                'subject': '',
                'content': 'Your login OTP is {{otp}}. Valid for {{expiry}} minutes.',
                'variables': ['otp', 'expiry'],
                'purposes': ['LOGIN'],
                'is_default': True
            },
            {
                'name': 'Registration OTP',
                'template_type': 'SMS',
                'subject': '',
                'content': 'Your registration OTP is {{otp}}. Valid for {{expiry}} minutes.',
                'variables': ['otp', 'expiry'],
                'purposes': ['REGISTRATION'],
                'is_default': True
            },
            {
                'name': 'Forgot Password OTP',
                'template_type': 'SMS',
                'subject': '',
                'content': 'Your password reset OTP is {{otp}}. Valid for {{expiry}} minutes.',
                'variables': ['otp', 'expiry'],
                'purposes': ['FORGOT_PASSWORD'],
                'is_default': True
            }
        ]
        
        # Default Email templates
        email_templates = [
            {
                'name': 'Login OTP Email',
                'template_type': 'EMAIL',
                'subject': 'Your Login OTP - {{clinic_name}}',
                'content': '''
                    <h2>Your Login OTP</h2>
                    <p>Hello {{name}},</p>
                    <p>Your OTP for login is: <strong>{{otp}}</strong></p>
                    <p>This OTP is valid for {{expiry}} minutes.</p>
                    <p>If you did not request this OTP, please ignore this email.</p>
                    <br>
                    <p>Best regards,<br>{{clinic_name}} Team</p>
                ''',
                'variables': ['otp', 'expiry', 'name', 'clinic_name'],
                'purposes': ['LOGIN'],
                'is_default': True
            }
        ]
        
        # Create templates
        all_templates = sms_templates + email_templates
        
        for template_data in all_templates:
            OTPTemplate.objects.get_or_create(
                name=template_data['name'],
                template_type=template_data['template_type'],
                branch=config.branch,
                defaults={
                    'subject': template_data.get('subject', ''),
                    'content': template_data['content'],
                    'variables': template_data['variables'],
                    'purposes': template_data['purposes'],
                    'is_default': template_data['is_default'],
                    'created_by': config.created_by
                }
            )
        
        logger.info(f"Created default templates for OTP config {config.id}")
        
    except Exception as e:
        logger.error(f"Failed to create default templates: {str(e)}")


# ===========================================
# OTP REQUEST SIGNALS
# ===========================================

@receiver(pre_save, sender=OTPRequest)
def otp_request_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal for OTPRequest
    - Validate OTP code
    - Set expiry if not set
    - Validate contact format
    """
    import re
    
    # Validate OTP code format
    if instance.otp_code and not instance.otp_code.isdigit():
        raise ValidationError("OTP code must contain only digits")
    
    # Validate recipient contact based on type
    if instance.contact_type == 'EMAIL':
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, instance.recipient_contact):
            raise ValidationError("Invalid email format")
    
    elif instance.contact_type == 'PHONE':
        phone_regex = r'^\+?1?\d{9,15}$'
        if not re.match(phone_regex, instance.recipient_contact):
            raise ValidationError("Invalid phone number format")
    
    # Set expiry if not set
    if not instance.expires_at:
        # Get OTP config for branch
        try:
            config = OTPConfig.objects.get(branch=instance.branch)
            expiry_minutes = config.get_purpose_config(instance.otp_type)['expiry_minutes']
        except (OTPConfig.DoesNotExist, AttributeError):
            expiry_minutes = 5  # Default
        
        instance.expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
    
    # Validate OTP is not expired on save
    if instance.expires_at and timezone.now() > instance.expires_at:
        instance.status = 'EXPIRED'
    
    # Validate attempt count
    if instance.attempt_count >= instance.max_attempts:
        instance.status = 'BLOCKED'
        
        # Add to blacklist if too many failed attempts
        if instance.attempt_count >= 5:  # Threshold for blacklisting
            add_to_blacklist_if_needed(instance)


@receiver(post_save, sender=OTPRequest)
def otp_request_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for OTPRequest
    - Create audit log
    - Update rate limits
    - Send status notifications
    - Auto-expire old OTPs
    """
    # Log the action
    action = 'OTP_REQUEST_CREATED' if created else 'OTP_REQUEST_UPDATED'
    
    # Determine if status changed
    if not created and instance.tracker.has_changed('status'):
        old_status = instance.tracker.previous('status')
        new_status = instance.status
        action = f'OTP_STATUS_CHANGED_{old_status}_TO_{new_status}'
        
        # Send notifications for status changes
        send_otp_status_notification(instance, old_status, new_status)
    
    # Log verification events
    if instance.status == 'VERIFIED':
        action = 'OTP_VERIFIED'
    elif instance.status == 'FAILED' and instance.attempt_count > 0:
        action = 'OTP_VERIFICATION_FAILED'
    
    # Create audit log
    try:
        user = getattr(instance, '_updated_by', instance.created_by)
        
        log_action(
            user=user,
            branch=instance.branch,
            instance=instance,
            action=action,
            device_id=getattr(instance, '_device_id', None),
            ip_address=getattr(instance, '_ip_address', None),
            metadata={
                'otp_id': str(instance.otp_id),
                'recipient_contact': instance.recipient_contact,
                'contact_type': instance.contact_type,
                'otp_type': instance.otp_type,
                'channel': instance.channel,
                'status': instance.status,
                'attempt_count': instance.attempt_count,
                'expires_at': str(instance.expires_at),
                'verified_at': str(instance.verified_at) if instance.verified_at else None
            }
        )
    except Exception as e:
        logger.error(f"Failed to log OTP request action: {str(e)}")
    
    # Update OTP config counters
    if instance.status in ['SENT', 'DELIVERED']:
        update_otp_config_counter(instance.branch, 'sent')
    elif instance.status == 'VERIFIED':
        update_otp_config_counter(instance.branch, 'verified')
    elif instance.status == 'FAILED':
        update_otp_config_counter(instance.branch, 'failed')
    
    # Update rate limits
    if created:
        update_rate_limits(instance)
    
    # Auto-expire OTPs in background (can be moved to Celery task)
    if instance.status in ['PENDING', 'SENT', 'DELIVERED']:
        schedule_otp_expiry_check(instance)


@receiver(post_delete, sender=OTPRequest)
def otp_request_post_delete(sender, instance, **kwargs):
    """
    Post-delete signal for OTPRequest
    """
    try:
        user = getattr(instance, '_deleted_by', None)
        
        log_action(
            user=user,
            branch=instance.branch,
            instance=None,  # Instance is deleted
            action='OTP_REQUEST_DELETED',
            metadata={
                'otp_id': str(instance.otp_id),
                'recipient_contact': instance.recipient_contact,
                'otp_type': instance.otp_type,
                'status': instance.status
            }
        )
    except Exception as e:
        logger.error(f"Failed to log OTP request deletion: {str(e)}")


# ===========================================
# OTP BLACKLIST SIGNALS
# ===========================================

@receiver(pre_save, sender=OTPBlacklist)
def otp_blacklist_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal for OTPBlacklist
    - Validate blacklist entries
    - Set blocked_until if permanent
    """
    # Validate identifier based on type
    if instance.blacklist_type == 'IP':
        import ipaddress
        try:
            ipaddress.ip_address(instance.identifier)
        except ValueError:
            raise ValidationError("Invalid IP address format")
    
    elif instance.blacklist_type == 'EMAIL':
        import re
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, instance.identifier):
            raise ValidationError("Invalid email format")
    
    elif instance.blacklist_type == 'PHONE':
        import re
        phone_regex = r'^\+?1?\d{9,15}$'
        if not re.match(phone_regex, instance.identifier):
            raise ValidationError("Invalid phone number format")
    
    # Set blocked_until for temporary blocks
    if not instance.is_permanent and not instance.blocked_until:
        # Get block duration from config
        try:
            config = OTPConfig.objects.get(branch=instance.branch)
            block_duration = config.block_duration_minutes
        except (OTPConfig.DoesNotExist, AttributeError):
            block_duration = 1440  # 24 hours default
        
        instance.blocked_until = timezone.now() + timedelta(minutes=block_duration)
    
    # For permanent blocks, clear blocked_until
    if instance.is_permanent:
        instance.blocked_until = None


@receiver(post_save, sender=OTPBlacklist)
def otp_blacklist_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for OTPBlacklist
    - Create audit log
    - Block related OTP requests
    - Send notifications
    """
    action = 'OTP_BLACKLIST_CREATED' if created else 'OTP_BLACKLIST_UPDATED'
    
    # Log unblocking
    if not created and instance.tracker.has_changed('blocked_until'):
        if instance.blocked_until is None and not instance.is_permanent:
            action = 'OTP_BLACKLIST_UNBLOCKED'
    
    try:
        user = getattr(instance, '_updated_by', instance.created_by)
        
        log_action(
            user=user,
            branch=instance.branch,
            instance=instance,
            action=action,
            metadata={
                'blacklist_type': instance.blacklist_type,
                'identifier': instance.identifier,
                'reason': instance.reason,
                'is_permanent': instance.is_permanent,
                'blocked_until': str(instance.blocked_until) if instance.blocked_until else None,
                'attempt_count': instance.attempt_count
            }
        )
    except Exception as e:
        logger.error(f"Failed to log blacklist action: {str(e)}")
    
    # Block related OTP requests
    if created or (not created and instance.tracker.has_changed('blocked_until')):
        block_related_otp_requests(instance)


@receiver(post_delete, sender=OTPBlacklist)
def otp_blacklist_post_delete(sender, instance, **kwargs):
    """
    Post-delete signal for OTPBlacklist
    - Unblock related OTP requests
    """
    try:
        user = getattr(instance, '_deleted_by', None)
        
        log_action(
            user=user,
            branch=instance.branch,
            instance=None,
            action='OTP_BLACKLIST_DELETED',
            metadata={
                'blacklist_type': instance.blacklist_type,
                'identifier': instance.identifier,
                'reason': instance.reason
            }
        )
    except Exception as e:
        logger.error(f"Failed to log blacklist deletion: {str(e)}")
    
    # Unblock related OTP requests
    unblock_related_otp_requests(instance)


# ===========================================
# OTP RATE LIMIT SIGNALS
# ===========================================

@receiver(pre_save, sender=OTPRateLimit)
def otp_rate_limit_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal for OTPRateLimit
    - Reset daily counters if date changed
    """
    # Reset daily counters if date changed
    today = timezone.now().date()
    if instance.daily_reset != today:
        instance.request_count = 0
        instance.successful_count = 0
        instance.failed_count = 0
        instance.daily_reset = today
    
    # Update last request time
    instance.last_request = timezone.now()


@receiver(post_save, sender=OTPRateLimit)
def otp_rate_limit_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for OTPRateLimit
    - Create audit log for suspicious activity
    """
    if not created:
        return
    
    # Only log for high frequency requests
    if instance.request_count > 50:  # Threshold for suspicious activity
        try:
            log_action(
                user=None,  # System action
                branch=instance.branch,
                instance=instance,
                action='OTP_RATE_LIMIT_HIGH_FREQUENCY',
                metadata={
                    'identifier': instance.identifier,
                    'identifier_type': instance.identifier_type,
                    'request_count': instance.request_count,
                    'successful_count': instance.successful_count,
                    'failed_count': instance.failed_count,
                    'last_request': str(instance.last_request)
                }
            )
        except Exception as e:
            logger.error(f"Failed to log rate limit activity: {str(e)}")


# ===========================================
# OTP TEMPLATE SIGNALS
# ===========================================

@receiver(pre_save, sender=OTPTemplate)
def otp_template_pre_save(sender, instance, **kwargs):
    """
    Pre-save signal for OTPTemplate
    - Validate template content
    - Ensure variables are properly formatted
    """
    # Validate template content
    if not instance.content:
        raise ValidationError("Template content is required")
    
    # Validate email template has subject
    if instance.template_type == 'EMAIL' and not instance.subject:
        raise ValidationError("Email templates require a subject")
    
    # Ensure variables is a list
    if not isinstance(instance.variables, list):
        instance.variables = []
    
    # Ensure purposes is a list
    if not isinstance(instance.purposes, list):
        instance.purposes = []
    
    # If setting as default, clear other defaults
    if instance.is_default and instance.pk:
        # Clear existing default for same type and branch
        OTPTemplate.objects.filter(
            template_type=instance.template_type,
            branch=instance.branch,
            is_default=True
        ).exclude(pk=instance.pk).update(is_default=False)


@receiver(post_save, sender=OTPTemplate)
def otp_template_post_save(sender, instance, created, **kwargs):
    """
    Post-save signal for OTPTemplate
    - Create audit log
    - Clear template cache
    """
    action = 'OTP_TEMPLATE_CREATED' if created else 'OTP_TEMPLATE_UPDATED'
    
    # Log default status change
    if not created and instance.tracker.has_changed('is_default'):
        if instance.is_default:
            action = 'OTP_TEMPLATE_SET_DEFAULT'
    
    try:
        user = getattr(instance, '_updated_by', instance.created_by)
        
        log_action(
            user=user,
            branch=instance.branch,
            instance=instance,
            action=action,
            metadata={
                'name': instance.name,
                'template_type': instance.template_type,
                'is_default': instance.is_default,
                'variables': instance.variables,
                'purposes': instance.purposes
            }
        )
    except Exception as e:
        logger.error(f"Failed to log template action: {str(e)}")
    
    # Clear template cache
    clear_template_cache(instance.branch, instance.template_type)


@receiver(post_delete, sender=OTPTemplate)
def otp_template_post_delete(sender, instance, **kwargs):
    """
    Post-delete signal for OTPTemplate
    - Set new default if deleted template was default
    """
    try:
        user = getattr(instance, '_deleted_by', None)
        
        log_action(
            user=user,
            branch=instance.branch,
            instance=None,
            action='OTP_TEMPLATE_DELETED',
            metadata={
                'name': instance.name,
                'template_type': instance.template_type
            }
        )
    except Exception as e:
        logger.error(f"Failed to log template deletion: {str(e)}")
    
    # If default template was deleted, set a new default
    if instance.is_default:
        try:
            new_default = OTPTemplate.objects.filter(
                template_type=instance.template_type,
                branch=instance.branch,
                is_active=True
            ).exclude(pk=instance.pk).first()
            
            if new_default:
                new_default.is_default = True
                new_default.save()
                logger.info(f"Set new default template: {new_default.name}")
        except Exception as e:
            logger.error(f"Failed to set new default template: {str(e)}")


# ===========================================
# HELPER FUNCTIONS
# ===========================================

def add_to_blacklist_if_needed(otp_request):
    """Add identifier to blacklist after too many failed attempts"""
    try:
        # Get OTP config for threshold
        config = OTPConfig.objects.get(branch=otp_request.branch)
        threshold = config.block_after_failed_attempts
        
        # Check if should be blacklisted
        if otp_request.attempt_count >= threshold:
            blacklist_type = 'IP' if otp_request.ip_address else 'CONTACT'
            identifier = otp_request.ip_address or otp_request.recipient_contact
            
            if identifier:
                # Create or update blacklist entry
                blacklist, created = OTPBlacklist.objects.update_or_create(
                    blacklist_type=blacklist_type,
                    identifier=identifier,
                    branch=otp_request.branch,
                    defaults={
                        'reason': 'TOO_MANY_ATTEMPTS',
                        'description': f'Blocked after {otp_request.attempt_count} failed OTP attempts',
                        'attempt_count': otp_request.attempt_count,
                        'last_attempt': timezone.now(),
                        'created_by': otp_request.created_by
                    }
                )
                
                if created:
                    logger.info(f"Added {identifier} to blacklist after {otp_request.attempt_count} failed attempts")
                
    except Exception as e:
        logger.error(f"Failed to add to blacklist: {str(e)}")


def update_otp_config_counter(branch, counter_type):
    """Update OTP config counters"""
    try:
        if not branch:
            return
        
        config = OTPConfig.objects.get(branch=branch)
        
        if counter_type == 'sent':
            config.total_otp_sent += 1
        elif counter_type == 'verified':
            config.total_verified += 1
        elif counter_type == 'failed':
            config.total_failed += 1
        
        config.save(update_fields=['total_otp_sent', 'total_verified', 'total_failed'])
        
    except OTPConfig.DoesNotExist:
        pass
    except Exception as e:
        logger.error(f"Failed to update OTP config counter: {str(e)}")


def update_rate_limits(otp_request):
    """Update rate limits for identifiers"""
    try:
        # Update for recipient contact
        if otp_request.recipient_contact:
            rate_limit, _ = OTPRateLimit.objects.get_or_create(
                identifier=otp_request.recipient_contact,
                identifier_type='CONTACT',
                branch=otp_request.branch,
                defaults={'last_request': timezone.now()}
            )
            rate_limit.request_count += 1
            if otp_request.status == 'VERIFIED':
                rate_limit.successful_count += 1
            elif otp_request.status == 'FAILED':
                rate_limit.failed_count += 1
            rate_limit.last_request = timezone.now()
            rate_limit.save()
        
        # Update for IP address
        if otp_request.ip_address:
            rate_limit, _ = OTPRateLimit.objects.get_or_create(
                identifier=otp_request.ip_address,
                identifier_type='IP',
                branch=otp_request.branch,
                defaults={'last_request': timezone.now()}
            )
            rate_limit.request_count += 1
            rate_limit.last_request = timezone.now()
            rate_limit.save()
        
        # Update for device ID
        if otp_request.device_id:
            rate_limit, _ = OTPRateLimit.objects.get_or_create(
                identifier=otp_request.device_id,
                identifier_type='DEVICE',
                branch=otp_request.branch,
                defaults={'last_request': timezone.now()}
            )
            rate_limit.request_count += 1
            rate_limit.last_request = timezone.now()
            rate_limit.save()
            
    except Exception as e:
        logger.error(f"Failed to update rate limits: {str(e)}")


def schedule_otp_expiry_check(otp_request):
    """Schedule OTP expiry check (can be replaced with Celery)"""
    from django.core.cache import cache
    
    try:
        # Use cache to schedule expiry check
        cache_key = f'otp_expiry_check_{otp_request.otp_id}'
        expiry_seconds = (otp_request.expires_at - timezone.now()).total_seconds()
        
        if expiry_seconds > 0:
            # Schedule check 1 minute after expiry
            cache.set(cache_key, otp_request.otp_id, timeout=int(expiry_seconds) + 60)
            
    except Exception as e:
        logger.error(f"Failed to schedule OTP expiry check: {str(e)}")


def send_otp_status_notification(otp_request, old_status, new_status):
    """Send notifications for OTP status changes"""
    try:
        # Only send notifications for certain status changes
        if new_status in ['VERIFIED', 'FAILED', 'BLOCKED', 'EXPIRED']:
            notification_service = NotificationService()
            
            # Prepare notification data
            data = {
                'otp_id': str(otp_request.otp_id),
                'recipient_contact': otp_request.recipient_contact,
                'otp_type': otp_request.otp_type,
                'old_status': old_status,
                'new_status': new_status,
                'attempt_count': otp_request.attempt_count
            }
            
            # Send to recipient if contact is email
            if otp_request.contact_type == 'EMAIL':
                notification_service.send_email(
                    email=otp_request.recipient_contact,
                    subject=f'OTP {new_status.title()}',
                    body=f'Your OTP request has been {new_status.lower()}.',
                    data=data
                )
            
            # Send to admins for security events
            if new_status in ['BLOCKED', 'FAILED'] and otp_request.attempt_count >= 3:
                # Get admin users
                admins = User.objects.filter(
                    role__in=['super_admin', 'clinic_manager'],
                    is_active=True
                )
                
                for admin in admins:
                    notification_service.create_notification(
                        user=admin,
                        title=f'OTP Security Alert - {new_status}',
                        message=f'OTP {otp_request.otp_id} for {otp_request.recipient_contact} has been {new_status.lower()} after {otp_request.attempt_count} attempts.',
                        notification_type='SECURITY_ALERT',
                        priority='high',
                        data=data
                    )
        
    except Exception as e:
        logger.error(f"Failed to send OTP status notification: {str(e)}")


def block_related_otp_requests(blacklist):
    """Block related OTP requests when added to blacklist"""
    try:
        # Block pending OTP requests for this identifier
        otp_requests = OTPRequest.objects.filter(
            status__in=['PENDING', 'SENT', 'DELIVERED']
        )
        
        if blacklist.blacklist_type == 'IP':
            otp_requests = otp_requests.filter(ip_address=blacklist.identifier)
        elif blacklist.blacklist_type == 'CONTACT':
            otp_requests = otp_requests.filter(recipient_contact=blacklist.identifier)
        elif blacklist.blacklist_type == 'DEVICE':
            otp_requests = otp_requests.filter(device_id=blacklist.identifier)
        
        # Update status
        count = otp_requests.update(status='BLOCKED')
        
        if count > 0:
            logger.info(f"Blocked {count} OTP requests for blacklisted {blacklist.blacklist_type}: {blacklist.identifier}")
            
    except Exception as e:
        logger.error(f"Failed to block related OTP requests: {str(e)}")


def unblock_related_otp_requests(blacklist):
    """Unblock related OTP requests when removed from blacklist"""
    try:
        # This would be called when a blacklist entry is deleted or expires
        # Implementation depends on business logic
        pass
        
    except Exception as e:
        logger.error(f"Failed to unblock related OTP requests: {str(e)}")


def clear_template_cache(branch, template_type):
    """Clear template cache"""
    from django.core.cache import cache
    
    try:
        cache_key = f'otp_templates_{branch.id if branch else "global"}_{template_type}'
        cache.delete(cache_key)
    except Exception as e:
        logger.error(f"Failed to clear template cache: {str(e)}")


# ===========================================
# MODEL TRACKER SETUP
# ===========================================

def init_model_trackers():
    """
    Initialize model trackers for change detection
    This should be called in AppConfig.ready()
    """
    from django.db import models
    
    # Add tracker to models
    for model in [OTPConfig, OTPRequest, OTPBlacklist, OTPRateLimit, OTPTemplate]:
        if not hasattr(model, 'tracker'):
            model.add_to_class('tracker', models.FieldTracker())


# ===========================================
# APP CONFIG INTEGRATION
# ===========================================

class OTPSignalsConfig:
    """
    Configuration for OTP signals
    """
    @classmethod
    def ready(cls):
        """Initialize signals when app is ready"""
        init_model_trackers()
        logger.info("OTP signals initialized")