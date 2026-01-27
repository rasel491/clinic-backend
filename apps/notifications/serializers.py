# # apps/notifications/serializers.py

# from rest_framework import serializers
# from django.utils import timezone
# from .models import (
#     NotificationTemplate, NotificationLog, SMSProvider, 
#     EmailProvider, NotificationSetting, NotificationQueue
# )
# from apps.clinics.serializers import BranchSerializer


# class NotificationTemplateSerializer(serializers.ModelSerializer):
#     branch = BranchSerializer(read_only=True)
#     branch_id = serializers.IntegerField(write_only=True)
    
#     class Meta:
#         model = NotificationTemplate
#         fields = [
#             'id', 'name', 'notification_type', 'category', 'subject', 
#             'body', 'variables', 'is_active', 'branch', 'branch_id',
#             'created_at', 'updated_at', 'created_by', 'updated_by'
#         ]
#         read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']


# class NotificationLogSerializer(serializers.ModelSerializer):
#     branch = BranchSerializer(read_only=True)
#     branch_id = serializers.IntegerField(write_only=True)
#     template_details = NotificationTemplateSerializer(source='template', read_only=True)
    
#     class Meta:
#         model = NotificationLog
#         fields = [
#             'id', 'recipient_type', 'recipient_id', 'recipient_contact',
#             'notification_type', 'template', 'template_details', 'subject',
#             'message', 'status', 'priority', 'scheduled_for', 'sent_at',
#             'delivered_at', 'read_at', 'error_message', 'metadata',
#             'branch', 'branch_id', 'related_object_type', 'related_object_id',
#             'created_at', 'updated_at', 'created_by', 'updated_by'
#         ]
#         read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']


# class SMSProviderSerializer(serializers.ModelSerializer):
#     branch = BranchSerializer(read_only=True)
#     branch_id = serializers.IntegerField(write_only=True)
    
#     class Meta:
#         model = SMSProvider
#         fields = [
#             'id', 'name', 'provider_type', 'is_default', 'account_sid',
#             'auth_token', 'api_key', 'api_secret', 'sender_id', 'endpoint_url',
#             'is_active', 'branch', 'branch_id',
#             'created_at', 'updated_at', 'created_by', 'updated_by'
#         ]
#         read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
#     def validate(self, data):
#         if data.get('is_default'):
#             # If setting as default, update other providers
#             SMSProvider.objects.filter(
#                 branch_id=data.get('branch_id'),
#                 is_default=True
#             ).update(is_default=False)
#         return data


# class EmailProviderSerializer(serializers.ModelSerializer):
#     branch = BranchSerializer(read_only=True)
#     branch_id = serializers.IntegerField(write_only=True)
    
#     class Meta:
#         model = EmailProvider
#         fields = [
#             'id', 'name', 'provider_type', 'is_default', 'host', 'port',
#             'username', 'password', 'use_tls', 'use_ssl', 'api_key',
#             'sender_email', 'sender_name', 'is_active', 'branch', 'branch_id',
#             'created_at', 'updated_at', 'created_by', 'updated_by'
#         ]
#         read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']


# class NotificationSettingSerializer(serializers.ModelSerializer):
#     template_sms_details = NotificationTemplateSerializer(source='template_sms', read_only=True)
#     template_email_details = NotificationTemplateSerializer(source='template_email', read_only=True)
    
#     class Meta:
#         model = NotificationSetting
#         fields = [
#             'id', 'category', 'send_sms', 'send_email', 'send_whatsapp',
#             'hours_before', 'is_active', 'template_sms', 'template_sms_details',
#             'template_email', 'template_email_details',
#             'created_at', 'updated_at', 'created_by', 'updated_by'
#         ]
#         read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']


# class NotificationQueueSerializer(serializers.ModelSerializer):
#     notification_log_details = NotificationLogSerializer(source='notification_log', read_only=True)
    
#     class Meta:
#         model = NotificationQueue
#         fields = [
#             'id', 'notification_log', 'notification_log_details', 'priority',
#             'retry_count', 'max_retries', 'next_retry_at', 'processing',
#             'processed_at', 'created_at', 'updated_at'
#         ]
#         read_only_fields = ['created_at', 'updated_at']


# class SendNotificationSerializer(serializers.Serializer):
#     """Serializer for sending notifications"""
#     recipient_type = serializers.CharField(required=True)
#     recipient_id = serializers.CharField(required=True)
#     recipient_contact = serializers.CharField(required=True)
#     notification_type = serializers.ChoiceField(choices=NotificationTemplate.NOTIFICATION_TYPES)
#     template_id = serializers.IntegerField(required=False)
#     subject = serializers.CharField(required=False, allow_blank=True)
#     message = serializers.CharField(required=False, allow_blank=True)
#     variables = serializers.DictField(required=False, default=dict)
#     priority = serializers.ChoiceField(choices=NotificationLog.PRIORITY_CHOICES, default='medium')
#     scheduled_for = serializers.DateTimeField(required=False)
#     related_object_type = serializers.CharField(required=False, allow_blank=True)
#     related_object_id = serializers.CharField(required=False, allow_blank=True)
    
#     def validate(self, data):
#         if not data.get('template_id') and not data.get('message'):
#             raise serializers.ValidationError("Either template_id or message is required")
#         return data


# apps/notifications/serializers.py
from rest_framework import serializers
from django.utils import timezone
from .models import (
    NotificationTemplate, NotificationLog, SMSProvider, 
    EmailProvider, NotificationSetting, NotificationQueue
)
from apps.clinics.serializers import BranchSerializer


class NotificationTemplateSerializer(serializers.ModelSerializer):
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'name', 'notification_type', 'category', 'subject', 
            'body', 'variables', 'is_active', 'branch', 'branch_id',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
    def validate_branch_id(self, value):
        from apps.clinics.models import Branch
        if not Branch.objects.filter(id=value).exists():
            raise serializers.ValidationError("Branch does not exist")
        return value


class NotificationLogSerializer(serializers.ModelSerializer):
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.IntegerField(write_only=True)
    template_details = NotificationTemplateSerializer(source='template', read_only=True)
    
    class Meta:
        model = NotificationLog
        fields = [
            'id', 'recipient_type', 'recipient_id', 'recipient_contact',
            'notification_type', 'template', 'template_details', 'subject',
            'message', 'status', 'priority', 'scheduled_for', 'sent_at',
            'delivered_at', 'read_at', 'error_message', 'metadata',
            'branch', 'branch_id', 'related_object_type', 'related_object_id',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
    def validate_branch_id(self, value):
        from apps.clinics.models import Branch
        if not Branch.objects.filter(id=value).exists():
            raise serializers.ValidationError("Branch does not exist")
        return value


class SMSProviderSerializer(serializers.ModelSerializer):
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = SMSProvider
        fields = [
            'id', 'name', 'provider_type', 'is_default', 'account_sid',
            'auth_token', 'api_key', 'api_secret', 'sender_id', 'endpoint_url',
            'is_active', 'branch', 'branch_id',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
    def validate_branch_id(self, value):
        from apps.clinics.models import Branch
        if not Branch.objects.filter(id=value).exists():
            raise serializers.ValidationError("Branch does not exist")
        return value
    
    def validate(self, data):
        if data.get('is_default'):
            # If setting as default, update other providers
            SMSProvider.objects.filter(
                branch_id=data.get('branch_id'),
                is_default=True
            ).update(is_default=False)
        return data


class EmailProviderSerializer(serializers.ModelSerializer):
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = EmailProvider
        fields = [
            'id', 'name', 'provider_type', 'is_default', 'host', 'port',
            'username', 'password', 'use_tls', 'use_ssl', 'api_key',
            'sender_email', 'sender_name', 'is_active', 'branch', 'branch_id',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
    def validate_branch_id(self, value):
        from apps.clinics.models import Branch
        if not Branch.objects.filter(id=value).exists():
            raise serializers.ValidationError("Branch does not exist")
        return value


class NotificationSettingSerializer(serializers.ModelSerializer):
    template_sms_details = NotificationTemplateSerializer(source='template_sms', read_only=True)
    template_email_details = NotificationTemplateSerializer(source='template_email', read_only=True)
    
    class Meta:
        model = NotificationSetting
        fields = [
            'id', 'category', 'send_sms', 'send_email', 'send_whatsapp',
            'hours_before', 'is_active', 'template_sms', 'template_sms_details',
            'template_email', 'template_email_details',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']


class NotificationQueueSerializer(serializers.ModelSerializer):
    notification_log_details = NotificationLogSerializer(source='notification_log', read_only=True)
    
    class Meta:
        model = NotificationQueue
        fields = [
            'id', 'notification_log', 'notification_log_details', 'priority',
            'retry_count', 'max_retries', 'next_retry_at', 'processing',
            'processed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class SendNotificationSerializer(serializers.Serializer):
    """Serializer for sending notifications"""
    recipient_type = serializers.CharField(required=True)
    recipient_id = serializers.CharField(required=True)
    recipient_contact = serializers.CharField(required=True)
    notification_type = serializers.ChoiceField(choices=NotificationTemplate.NOTIFICATION_TYPES)
    template_id = serializers.IntegerField(required=False)
    subject = serializers.CharField(required=False, allow_blank=True)
    message = serializers.CharField(required=False, allow_blank=True)
    variables = serializers.DictField(required=False, default=dict)
    priority = serializers.ChoiceField(choices=NotificationLog.PRIORITY_CHOICES, default='medium')
    scheduled_for = serializers.DateTimeField(required=False)
    related_object_type = serializers.CharField(required=False, allow_blank=True)
    related_object_id = serializers.CharField(required=False, allow_blank=True)
    branch_id = serializers.IntegerField(required=True)  # Added missing field
    
    def validate(self, data):
        if not data.get('template_id') and not data.get('message'):
            raise serializers.ValidationError("Either template_id or message is required")
        
        # Validate branch exists
        from apps.clinics.models import Branch
        if not Branch.objects.filter(id=data.get('branch_id')).exists():
            raise serializers.ValidationError({"branch_id": "Branch does not exist"})
        
        return data