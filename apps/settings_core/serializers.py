# apps/settings_core/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import *

User = get_user_model()


class SystemSettingSerializer(serializers.ModelSerializer):
    value = serializers.SerializerMethodField()
    last_modified_by_name = serializers.CharField(
        source='last_modified_by.get_full_name',
        read_only=True
    )

    class Meta:
        model = SystemSetting
        fields = [
            'id', 'key', 'name', 'description', 'category', 'data_type',
            'value', 'choices', 'is_editable', 'requires_restart',
            'requires_superuser', 'sort_order', 'group_name', 'help_text',
            'last_modified_by', 'last_modified_by_name', 'last_modified_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'last_modified_at']

    def get_value(self, obj):
        return obj.get_value()

    def validate(self, data):
        # Validate based on data_type
        data_type = data.get('data_type', self.instance.data_type if self.instance else None)
        
        if 'value' in self.initial_data:
            value = self.initial_data['value']
            
            if data_type == SystemSetting.INTEGER:
                if not isinstance(value, int):
                    raise serializers.ValidationError({"value": "Value must be an integer"})
            elif data_type == SystemSetting.DECIMAL:
                try:
                    decimal_value = Decimal(str(value))
                except:
                    raise serializers.ValidationError({"value": "Value must be a decimal number"})
            elif data_type == SystemSetting.BOOLEAN:
                if not isinstance(value, bool):
                    raise serializers.ValidationError({"value": "Value must be boolean"})
            elif data_type == SystemSetting.CHOICE:
                if 'choices' in data and value not in data['choices']:
                    raise serializers.ValidationError({"value": f"Value must be one of: {data['choices']}"})
        
        return data

    def update(self, instance, validated_data):
        # Handle value update
        if 'value' in self.initial_data:
            value = self.initial_data['value']
            user = self.context['request'].user if 'request' in self.context else None
            instance.set_value(value, user)
        
        # Update other fields
        for attr, value in validated_data.items():
            if attr not in ['string_value', 'integer_value', 'decimal_value',
                          'boolean_value', 'json_value', 'datetime_value',
                          'date_value', 'time_value']:
                setattr(instance, attr, value)
        
        instance.save()
        return instance


class BranchSettingSerializer(serializers.ModelSerializer):
    value = serializers.SerializerMethodField()
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = BranchSetting
        fields = [
            'id', 'branch', 'branch_name', 'key', 'name', 'description',
            'category', 'data_type', 'value', 'choices', 'override_system',
            'is_editable', 'requires_manager', 'sort_order', 'group_name',
            'help_text', 'created_by', 'updated_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_value(self, obj):
        return obj.get_value()

    def validate(self, data):
        branch = data.get('branch', self.instance.branch if self.instance else None)
        key = data.get('key', self.instance.key if self.instance else None)
        
        # Check for duplicate branch+key
        if BranchSetting.objects.filter(branch=branch, key=key).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError(
                f"Setting with key '{key}' already exists for this branch"
            )
        
        return data


class ClinicConfigurationSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = ClinicConfiguration
        fields = [
            'id', 'branch', 'branch_name', 'clinic_name', 'clinic_logo',
            'clinic_address', 'clinic_phone', 'clinic_email', 'clinic_website',
            'working_days', 'opening_time', 'closing_time', 'lunch_start',
            'lunch_end', 'appointment_duration', 'max_appointments_per_slot',
            'buffer_time', 'advance_booking_days', 'currency_symbol',
            'currency_code', 'default_tax_rate', 'invoice_prefix',
            'invoice_terms', 'invoice_footer', 'default_follow_up_days',
            'send_appointment_reminders', 'reminder_hours_before',
            'default_consultation_fee', 'enable_digital_prescriptions',
            'enable_treatment_plans', 'send_sms_notifications',
            'send_email_notifications', 'created_by', 'updated_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_working_days(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Working days must be a list")
        
        valid_days = [choice[0] for choice in ClinicConfiguration.DAY_CHOICES]
        for day in value:
            if day not in valid_days:
                raise serializers.ValidationError(
                    f"Invalid day: {day}. Must be one of: {valid_days}"
                )
        
        return value


class HolidaySerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = Holiday
        fields = [
            'id', 'branch', 'branch_name', 'name', 'date',
            'is_recurring', 'description', 'created_by',
            'updated_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class TaxConfigurationSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = TaxConfiguration
        fields = [
            'id', 'branch', 'branch_name', 'name', 'tax_type', 'rate', 'code',
            'description', 'applicable_from', 'applicable_to', 'is_active',
            'apply_to_services', 'apply_to_products', 'apply_to_consultations',
            'sgst_rate', 'cgst_rate', 'igst_rate', 'created_by', 'updated_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, data):
        tax_type = data.get('tax_type', self.instance.tax_type if self.instance else None)
        
        if tax_type == 'GST':
            sgst = data.get('sgst_rate', self.instance.sgst_rate if self.instance else None)
            cgst = data.get('cgst_rate', self.instance.cgst_rate if self.instance else None)
            igst = data.get('igst_rate', self.instance.igst_rate if self.instance else None)
            
            if not (sgst and cgst) and not igst:
                raise serializers.ValidationError(
                    "For GST, either SGST+CGST or IGST must be provided"
                )
        
        return data


class SMSConfigurationSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = SMSConfiguration
        fields = [
            'id', 'branch', 'branch_name', 'provider', 'is_active',
            'api_key', 'api_secret', 'sender_id', 'api_url',
            'priority', 'max_per_day', 'characters_per_sms',
            'total_sent', 'successful_sent', 'failed_sent',
            'last_used', 'created_by', 'updated_by',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'total_sent', 'successful_sent', 'failed_sent',
            'last_used', 'created_at', 'updated_at'
        ]


class EmailConfigurationSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = EmailConfiguration
        fields = [
            'id', 'branch', 'branch_name', 'provider', 'is_active',
            'smtp_host', 'smtp_port', 'smtp_username', 'smtp_password',
            'use_tls', 'use_ssl', 'from_email', 'from_name', 'reply_to',
            'api_key', 'api_secret', 'api_url', 'total_sent',
            'successful_sent', 'failed_sent', 'last_used',
            'created_by', 'updated_by', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'total_sent', 'successful_sent', 'failed_sent',
            'last_used', 'created_at', 'updated_at'
        ]


class NotificationTemplateSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True, allow_null=True)

    class Meta:
        model = NotificationTemplate
        fields = [
            'id', 'branch', 'branch_name', 'name', 'notification_type',
            'trigger', 'is_active', 'sms_template', 'email_subject',
            'email_template', 'available_variables', 'send_before_hours',
            'send_after_hours', 'is_required', 'can_override',
            'created_by', 'updated_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class RolePermissionSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source='role.name', read_only=True)
    permission_name = serializers.CharField(source='permission.name', read_only=True)
    app_label = serializers.CharField(source='permission.content_type.app_label', read_only=True)
    model_name = serializers.CharField(source='permission.content_type.model', read_only=True)

    class Meta:
        model = RolePermission
        fields = [
            'id', 'role', 'role_name', 'permission', 'permission_name',
            'app_label', 'model_name', 'module', 'can_view', 'can_create',
            'can_edit', 'can_delete', 'can_approve', 'can_export',
            'scope_all_branches', 'custom_permissions', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class BackupConfigurationSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = BackupConfiguration
        fields = [
            'id', 'branch', 'branch_name', 'backup_type', 'storage_type',
            'is_active', 'frequency', 'schedule_time', 'retention_days',
            'local_path', 'aws_bucket', 'aws_access_key', 'aws_secret_key',
            'google_drive_folder', 'azure_container', 'notify_on_success',
            'notify_on_failure', 'notify_email', 'last_backup',
            'last_backup_size', 'total_backups', 'successful_backups',
            'failed_backups', 'created_by', 'updated_by', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'last_backup', 'last_backup_size', 'total_backups',
            'successful_backups', 'failed_backups', 'created_at', 'updated_at'
        ]


class AuditLogConfigurationSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = AuditLogConfiguration
        fields = [
            'id', 'branch', 'branch_name', 'log_level',
            'enable_login_logging', 'enable_data_change_logging',
            'enable_financial_logging', 'enable_system_event_logging',
            'retention_days', 'archive_after_days', 'allow_log_export',
            'export_requires_approval', 'enable_alerts',
            'alert_on_multiple_failures', 'failure_threshold',
            'created_by', 'updated_by', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']