# apps/otp/serializers.py

from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
import re

from .models import (
    OTPConfig, OTPRequest, OTPBlacklist,
    OTPRateLimit, OTPTemplate, OTPType, OTPChannel
)
from apps.clinics.serializers import BranchSerializer


class OTPConfigSerializer(serializers.ModelSerializer):
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = OTPConfig
        fields = [
            'id', 'branch', 'branch_id', 'default_otp_length',
            'default_expiry_minutes', 'max_attempts_per_otp',
            'max_otp_per_day', 'cool_down_period', 'enable_anti_spam',
            'block_after_failed_attempts', 'block_duration_minutes',
            'default_channel', 'fallback_channel', 'sms_template',
            'email_subject', 'email_template', 'auto_verify_on_match',
            'require_captcha', 'captcha_threshold', 'total_otp_sent',
            'total_verified', 'total_failed',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']


class OTPRequestSerializer(serializers.ModelSerializer):
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = OTPRequest
        fields = [
            'id', 'otp_id', 'reference_id', 'recipient_type',
            'recipient_id', 'recipient_contact', 'contact_type',
            'otp_code', 'otp_type', 'purpose', 'channel', 'status',
            'expires_at', 'sent_at', 'delivered_at', 'verified_at',
            'attempt_count', 'max_attempts', 'ip_address', 'user_agent',
            'device_id', 'related_object_type', 'related_object_id',
            'branch', 'branch_id', 'metadata',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'otp_id', 'otp_code', 'status', 'expires_at',
            'sent_at', 'delivered_at', 'verified_at', 'attempt_count',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def validate_recipient_contact(self, value):
        """Validate email or phone format"""
        contact_type = self.initial_data.get('contact_type')
        
        if contact_type == 'EMAIL':
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
                raise serializers.ValidationError("Invalid email format")
        elif contact_type == 'PHONE':
            # Basic phone validation - adjust based on your country
            if not re.match(r'^\+?1?\d{9,15}$', value):
                raise serializers.ValidationError("Invalid phone number format")
        
        return value


class OTPBlacklistSerializer(serializers.ModelSerializer):
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = OTPBlacklist
        fields = [
            'id', 'blacklist_type', 'identifier', 'reason',
            'description', 'blocked_until', 'is_permanent',
            'branch', 'branch_id', 'attempt_count', 'last_attempt',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']


class OTPRateLimitSerializer(serializers.ModelSerializer):
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = OTPRateLimit
        fields = [
            'id', 'identifier', 'identifier_type', 'request_count',
            'successful_count', 'failed_count', 'last_request',
            'daily_reset', 'branch', 'branch_id',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'request_count', 'successful_count', 'failed_count',
            'last_request', 'daily_reset', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]


class OTPTemplateSerializer(serializers.ModelSerializer):
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = OTPTemplate
        fields = [
            'id', 'name', 'template_type', 'subject', 'content',
            'variables', 'purposes', 'branch', 'branch_id',
            'is_default', 'is_active',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']


# Request/Response serializers
class RequestOTPSerializer(serializers.Serializer):
    """Serializer for requesting OTP"""
    recipient_contact = serializers.CharField(required=True)
    contact_type = serializers.ChoiceField(
        choices=[('EMAIL', 'Email'), ('PHONE', 'Phone'), ('USERNAME', 'Username')],
        required=True
    )
    otp_type = serializers.ChoiceField(
        choices=[
            (OTPType.LOGIN, 'Login'),
            (OTPType.REGISTRATION, 'Registration'),
            (OTPType.FORGOT_PASSWORD, 'Forgot Password'),
            (OTPType.PHONE_VERIFICATION, 'Phone Verification'),
            (OTPType.EMAIL_VERIFICATION, 'Email Verification'),
            (OTPType.TRANSACTION, 'Transaction'),
            (OTPType.APPOINTMENT_CONFIRMATION, 'Appointment Confirmation'),
            (OTPType.PAYMENT_VERIFICATION, 'Payment Verification'),
        ],
        required=True
    )
    channel = serializers.ChoiceField(
        choices=[
            (OTPChannel.SMS, 'SMS'),
            (OTPChannel.EMAIL, 'Email'),
            (OTPChannel.WHATSAPP, 'WhatsApp'),
            (OTPChannel.VOICE_CALL, 'Voice Call'),
        ],
        required=False
    )
    purpose = serializers.CharField(required=False, default='verification')
    recipient_type = serializers.ChoiceField(
        choices=[
            ('PATIENT', 'Patient'),
            ('DOCTOR', 'Doctor'),
            ('STAFF', 'Staff'),
            ('USER', 'User'),
        ],
        required=False,
        default='USER'
    )
    recipient_id = serializers.CharField(required=False)
    related_object_type = serializers.CharField(required=False)
    related_object_id = serializers.CharField(required=False)
    branch_id = serializers.IntegerField(required=False)
    metadata = serializers.DictField(required=False, default=dict)
    
    def validate(self, data):
        # Validate contact based on type
        contact = data.get('recipient_contact')
        contact_type = data.get('contact_type')
        
        if contact_type == 'EMAIL':
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', contact):
                raise serializers.ValidationError({
                    'recipient_contact': 'Invalid email format'
                })
        elif contact_type == 'PHONE':
            if not re.match(r'^\+?1?\d{9,15}$', contact):
                raise serializers.ValidationError({
                    'recipient_contact': 'Invalid phone number format'
                })
        
        return data


class VerifyOTPSerializer(serializers.Serializer):
    """Serializer for verifying OTP"""
    otp_id = serializers.UUIDField(required=True)
    otp_code = serializers.CharField(required=True, max_length=10)
    recipient_contact = serializers.CharField(required=False)
    increment_attempt = serializers.BooleanField(default=True)
    
    def validate_otp_code(self, value):
        """Validate OTP code format"""
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits")
        return value.strip()


class ResendOTPSerializer(serializers.Serializer):
    """Serializer for resending OTP"""
    otp_id = serializers.UUIDField(required=True)
    channel = serializers.ChoiceField(
        choices=[
            (OTPChannel.SMS, 'SMS'),
            (OTPChannel.EMAIL, 'Email'),
            (OTPChannel.WHATSAPP, 'WhatsApp'),
            (OTPChannel.VOICE_CALL, 'Voice Call'),
        ],
        required=False
    )


class OTPStatsSerializer(serializers.Serializer):
    """Serializer for OTP statistics"""
    total_requests = serializers.IntegerField()
    total_verified = serializers.IntegerField()
    total_failed = serializers.IntegerField()
    success_rate = serializers.FloatField()
    by_type = serializers.DictField()
    by_channel = serializers.DictField()
    recent_requests = serializers.ListField()


class CheckRateLimitSerializer(serializers.Serializer):
    """Serializer for checking rate limits"""
    identifier = serializers.CharField(required=True)
    identifier_type = serializers.ChoiceField(
        choices=[
            ('IP', 'IP Address'),
            ('DEVICE', 'Device ID'),
            ('USER', 'User ID'),
        ],
        required=True
    )
    branch_id = serializers.IntegerField(required=False)