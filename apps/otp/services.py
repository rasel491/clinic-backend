# apps/otp/services.py

import logging
import random
import string
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import re

from .models import (
    OTPConfig, OTPRequest, OTPBlacklist,
    OTPRateLimit, OTPTemplate, OTPType, OTPChannel
)
from apps.notifications.services import NotificationService
from apps.settings_core.models import SystemSetting

logger = logging.getLogger(__name__)


class OTPService:
    """Service for OTP operations"""
    
    def __init__(self):
        self.notification_service = NotificationService()
    
    def request_otp(self, recipient_contact, contact_type, otp_type, 
                   channel=None, purpose='verification', recipient_type='USER',
                   recipient_id=None, related_object_type=None, related_object_id=None,
                   branch_id=None, metadata=None, ip_address=None, user_agent=None,
                   device_id=None):
        """Request OTP"""
        try:
            # Check blacklist first
            if self._is_blacklisted(recipient_contact, contact_type, ip_address, device_id, branch_id):
                raise Exception("Request blocked due to security restrictions")
            
            # Check rate limits
            self._check_rate_limits(recipient_contact, ip_address, device_id, branch_id)
            
            # Get OTP configuration
            config = self._get_config(branch_id)
            
            # Get purpose-specific settings
            purpose_config = config.get_purpose_config(otp_type)
            
            # Check cool down period
            if not self._check_cool_down(recipient_contact, config.cool_down_period):
                raise Exception(f"Please wait {config.cool_down_period} seconds before requesting new OTP")
            
            # Check daily limit
            if not self._check_daily_limit(recipient_contact, config.max_otp_per_day):
                raise Exception(f"Daily OTP limit reached ({config.max_otp_per_day})")
            
            # Generate OTP
            otp_length = purpose_config['length']
            otp_code = self._generate_otp(otp_length)
            
            # Determine channel if not specified
            if not channel:
                channel = purpose_config['channels'][0]
                if contact_type == 'EMAIL' and OTPChannel.EMAIL not in purpose_config['channels']:
                    channel = purpose_config['channels'][0]
                elif contact_type == 'PHONE' and OTPChannel.SMS not in purpose_config['channels']:
                    channel = purpose_config['channels'][0]
            
            # Calculate expiry
            expiry_minutes = purpose_config['expiry_minutes']
            expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
            
            # Create OTP request
            otp_request = OTPRequest.objects.create(
                recipient_contact=recipient_contact,
                contact_type=contact_type,
                otp_type=otp_type,
                purpose=purpose,
                channel=channel,
                recipient_type=recipient_type,
                recipient_id=recipient_id,
                related_object_type=related_object_type,
                related_object_id=related_object_id,
                otp_code=otp_code,
                expires_at=expires_at,
                max_attempts=purpose_config['max_attempts'],
                ip_address=ip_address,
                user_agent=user_agent,
                device_id=device_id,
                branch_id=branch_id,
                metadata=metadata or {},
                created_by=None  # Will be set by middleware
            )
            
            # Send OTP
            self._send_otp(otp_request, config)
            
            # Update counters
            self._update_counters(recipient_contact, ip_address, device_id, branch_id, True)
            config.total_otp_sent += 1
            config.save()
            
            return otp_request
            
        except Exception as e:
            logger.error(f"Error requesting OTP: {str(e)}")
            self._update_counters(recipient_contact, ip_address, device_id, branch_id, False)
            raise
    
    def verify_otp(self, otp_id, otp_code, recipient_contact=None, increment_attempt=True):
        """Verify OTP"""
        try:
            # Get OTP request
            otp_request = OTPRequest.objects.get(otp_id=otp_id)
            
            # Validate recipient if provided
            if recipient_contact and otp_request.recipient_contact != recipient_contact:
                raise Exception("Recipient mismatch")
            
            # Verify OTP
            verified = otp_request.verify(otp_code, increment_attempt)
            
            # Update counters
            if verified:
                config = self._get_config(otp_request.branch_id)
                config.total_verified += 1
                config.save()
            
            return verified
            
        except OTPRequest.DoesNotExist:
            raise Exception("Invalid OTP request")
        except Exception as e:
            logger.error(f"Error verifying OTP: {str(e)}")
            raise
    
    def resend_otp(self, otp_id, channel=None):
        """Resend OTP"""
        try:
            # Get OTP request
            otp_request = OTPRequest.objects.get(otp_id=otp_id)
            
            # Check if can be resent
            if not otp_request.is_valid():
                return None
            
            # Use new channel if specified
            if channel:
                otp_request.channel = channel
            
            # Generate new OTP if needed
            config = self._get_config(otp_request.branch_id)
            purpose_config = config.get_purpose_config(otp_request.otp_type)
            
            new_otp = self._generate_otp(purpose_config['length'])
            otp_request.otp_code = new_otp
            
            # Update expiry
            expiry_minutes = purpose_config['expiry_minutes']
            otp_request.expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
            
            # Reset attempt count
            otp_request.attempt_count = 0
            otp_request.status = 'PENDING'
            
            otp_request.save()
            
            # Resend OTP
            self._send_otp(otp_request, config)
            
            # Update counters
            config.total_otp_sent += 1
            config.save()
            
            return otp_request
            
        except OTPRequest.DoesNotExist:
            raise Exception("Invalid OTP request")
        except Exception as e:
            logger.error(f"Error resending OTP: {str(e)}")
            raise
    
    def check_rate_limit(self, identifier, identifier_type, branch_id=None):
        """Check rate limits for identifier"""
        try:
            rate_limit, created = OTPRateLimit.objects.get_or_create(
                identifier=identifier,
                identifier_type=identifier_type,
                branch_id=branch_id,
                defaults={'last_request': timezone.now()}
            )
            
            # Reset daily counters if needed
            rate_limit.reset_daily_counters()
            
            # Get config for limits
            config = self._get_config(branch_id)
            
            return {
                'identifier': identifier,
                'identifier_type': identifier_type,
                'request_count': rate_limit.request_count,
                'daily_limit': config.max_otp_per_day,
                'remaining': max(0, config.max_otp_per_day - rate_limit.request_count),
                'last_request': rate_limit.last_request,
                'cool_down_seconds': config.cool_down_period
            }
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            raise
    
    def _send_otp(self, otp_request, config):
        """Send OTP via appropriate channel"""
        try:
            # Prepare context
            context = {
                'otp': otp_request.otp_code,
                'expiry': config.default_expiry_minutes,
                'purpose': otp_request.purpose,
                'contact': otp_request.recipient_contact,
                'timestamp': timezone.now().isoformat(),
            }
            
            # Get appropriate template
            template = self._get_template(otp_request, config)
            
            # Send based on channel
            if otp_request.channel == OTPChannel.SMS:
                self._send_sms_otp(otp_request, template, context, config)
            elif otp_request.channel == OTPChannel.EMAIL:
                self._send_email_otp(otp_request, template, context, config)
            elif otp_request.channel == OTPChannel.WHATSAPP:
                self._send_whatsapp_otp(otp_request, template, context, config)
            elif otp_request.channel == OTPChannel.VOICE_CALL:
                self._send_voice_otp(otp_request, template, context, config)
            
            otp_request.mark_sent()
            
        except Exception as e:
            logger.error(f"Error sending OTP: {str(e)}")
            otp_request.mark_failed(str(e))
            raise
    
    def _send_sms_otp(self, otp_request, template, context, config):
        """Send OTP via SMS"""
        message = template.render(context) if template else config.sms_template.format(**context)
        
        # Use notification service
        self.notification_service.send_sms(
            phone_number=otp_request.recipient_contact,
            message=message,
            branch_id=otp_request.branch_id
        )
    
    def _send_email_otp(self, otp_request, template, context, config):
        """Send OTP via Email"""
        if template:
            subject = template.subject.format(**context)
            body = template.render(context)
        else:
            subject = config.email_subject
            body = config.email_template.format(**context)
        
        # Use notification service
        self.notification_service.send_email(
            email=otp_request.recipient_contact,
            subject=subject,
            body=body,
            branch_id=otp_request.branch_id
        )
    
    def _send_whatsapp_otp(self, otp_request, template, context, config):
        """Send OTP via WhatsApp"""
        message = template.render(context) if template else f"Your OTP is {context['otp']}. Valid for {context['expiry']} minutes."
        
        # Use notification service
        self.notification_service.send_whatsapp(
            phone_number=otp_request.recipient_contact,
            message=message,
            branch_id=otp_request.branch_id
        )
    
    def _send_voice_otp(self, otp_request, template, context, config):
        """Send OTP via Voice Call"""
        # Implement voice call logic here
        # This would integrate with a voice call service
        pass
    
    def _generate_otp(self, length=6):
        """Generate OTP code"""
        # Use only digits for most OTPs
        return ''.join(random.choice(string.digits) for _ in range(length))
    
    def _get_config(self, branch_id):
        """Get OTP configuration"""
        if branch_id:
            try:
                return OTPConfig.objects.get(branch_id=branch_id)
            except OTPConfig.DoesNotExist:
                pass
        
        # Get default config or create one
        return OTPConfig.objects.first() or OTPConfig.objects.create(
            branch_id=branch_id
        )
    
    def _get_template(self, otp_request, config):
        """Get appropriate template"""
        try:
            # Look for branch-specific template first
            template = OTPTemplate.objects.filter(
                branch=otp_request.branch,
                template_type=otp_request.channel,
                purposes__contains=[otp_request.otp_type],
                is_default=True
            ).first()
            
            if not template:
                # Look for system-wide template
                template = OTPTemplate.objects.filter(
                    branch__isnull=True,
                    template_type=otp_request.channel,
                    purposes__contains=[otp_request.otp_type],
                    is_default=True
                ).first()
            
            return template
            
        except Exception:
            return None
    
    def _is_blacklisted(self, recipient_contact, contact_type, ip_address, device_id, branch_id):
        """Check if identifier is blacklisted"""
        try:
            # Check IP
            if ip_address:
                blacklist = OTPBlacklist.objects.filter(
                    blacklist_type='IP',
                    identifier=ip_address,
                    branch_id=branch_id
                ).first()
                if blacklist and blacklist.is_blocked():
                    return True
            
            # Check device
            if device_id:
                blacklist = OTPBlacklist.objects.filter(
                    blacklist_type='DEVICE',
                    identifier=device_id,
                    branch_id=branch_id
                ).first()
                if blacklist and blacklist.is_blocked():
                    return True
            
            # Check contact
            if recipient_contact:
                blacklist = OTPBlacklist.objects.filter(
                    blacklist_type='CONTACT',
                    identifier=recipient_contact,
                    branch_id=branch_id
                ).first()
                if blacklist and blacklist.is_blocked():
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking blacklist: {str(e)}")
            return False
    
    def _check_rate_limits(self, recipient_contact, ip_address, device_id, branch_id):
        """Check rate limits"""
        try:
            config = self._get_config(branch_id)
            
            # Check multiple identifiers
            identifiers = [
                (recipient_contact, 'CONTACT'),
                (ip_address, 'IP'),
                (device_id, 'DEVICE')
            ]
            
            for identifier, identifier_type in identifiers:
                if identifier:
                    rate_limit, created = OTPRateLimit.objects.get_or_create(
                        identifier=identifier,
                        identifier_type=identifier_type,
                        branch_id=branch_id,
                        defaults={'last_request': timezone.now()}
                    )
                    
                    # Reset daily counters if needed
                    rate_limit.reset_daily_counters()
                    
                    # Check daily limit
                    if rate_limit.request_count >= config.max_otp_per_day:
                        raise Exception(f"Daily OTP limit reached for {identifier_type}")
                    
                    # Update last request
                    rate_limit.last_request = timezone.now()
                    rate_limit.save()
            
        except Exception as e:
            logger.error(f"Error checking rate limits: {str(e)}")
            raise
    
    def _update_counters(self, recipient_contact, ip_address, device_id, branch_id, success):
        """Update rate limit counters"""
        try:
            identifiers = [
                (recipient_contact, 'CONTACT'),
                (ip_address, 'IP'),
                (device_id, 'DEVICE')
            ]
            
            for identifier, identifier_type in identifiers:
                if identifier:
                    try:
                        rate_limit = OTPRateLimit.objects.get(
                            identifier=identifier,
                            identifier_type=identifier_type,
                            branch_id=branch_id
                        )
                        
                        rate_limit.request_count += 1
                        if success:
                            rate_limit.successful_count += 1
                        else:
                            rate_limit.failed_count += 1
                        
                        rate_limit.last_request = timezone.now()
                        rate_limit.save()
                        
                    except OTPRateLimit.DoesNotExist:
                        pass
                        
        except Exception as e:
            logger.error(f"Error updating counters: {str(e)}")
    
    def _check_cool_down(self, recipient_contact, cool_down_period):
        """Check cool down period"""
        try:
            if not cool_down_period:
                return True
            
            # Check last successful OTP for this contact
            last_otp = OTPRequest.objects.filter(
                recipient_contact=recipient_contact,
                status='VERIFIED'
            ).order_by('-created_at').first()
            
            if last_otp:
                cool_down_end = last_otp.created_at + timedelta(seconds=cool_down_period)
                if timezone.now() < cool_down_end:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking cool down: {str(e)}")
            return True
    
    def _check_daily_limit(self, recipient_contact, max_per_day):
        """Check daily OTP limit"""
        try:
            if not max_per_day:
                return True
            
            today = timezone.now().date()
            today_count = OTPRequest.objects.filter(
                recipient_contact=recipient_contact,
                created_at__date=today
            ).count()
            
            return today_count < max_per_day
            
        except Exception as e:
            logger.error(f"Error checking daily limit: {str(e)}")
            return True
        

    # Add to apps/otp/services.py in _send_voice_otp method:

    def _send_voice_otp(self, otp_request, template, context, config):
        """Send OTP via Voice Call"""
        try:
            # Integrate with Twilio or other voice service
            from twilio.rest import Client
            
            # Configuration
            account_sid = config.metadata.get('twilio_account_sid')
            auth_token = config.metadata.get('twilio_auth_token')
            from_number = config.metadata.get('twilio_from_number')
            
            if not all([account_sid, auth_token, from_number]):
                logger.warning("Voice OTP not configured")
                otp_request.mark_failed("Voice OTP not configured")
                return
            
            client = Client(account_sid, auth_token)
            
            # Create message - speak OTP digits
            otp_digits = ' '.join(otp_request.otp_code)
            message = f"Your OTP code is {otp_digits}. This code expires in {context['expiry']} minutes."
            
            # Make call
            call = client.calls.create(
                twiml=f'<Response><Say>{message}</Say></Response>',
                to=otp_request.recipient_contact,
                from_=from_number
            )
            
            otp_request.metadata['voice_call_sid'] = call.sid
            otp_request.save()
            
        except ImportError:
            logger.error("Twilio not installed for voice OTP")
        except Exception as e:
            logger.error(f"Voice OTP error: {str(e)}")
            otp_request.mark_failed(f"Voice OTP failed: {str(e)}")