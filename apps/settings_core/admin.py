# apps/settings_core/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
import json

from .models import (
    SystemSetting, BranchSetting, ClinicConfiguration,
    Holiday, TaxConfiguration, SMSConfiguration,
    EmailConfiguration, NotificationTemplate,
    RolePermission, BackupConfiguration, AuditLogConfiguration
)


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ('name', 'key', 'category', 'data_type',
                   'is_editable', 'requires_superuser',
                   'last_modified_at')
    list_filter = ('category', 'data_type', 'is_editable',
                  'requires_superuser')
    search_fields = ('name', 'key', 'description')
    readonly_fields = ('last_modified_at', 'last_modified_by',
                      'created_at', 'updated_at')
    list_editable = ('is_editable',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('key', 'name', 'description', 'category',
                      'data_type', 'group_name')
        }),
        ('Value Storage', {
            'fields': ('string_value', 'integer_value', 'decimal_value',
                      'boolean_value', 'json_value', 'datetime_value',
                      'date_value', 'time_value', 'choices')
        }),
        ('Validation', {
            'fields': ('min_value', 'max_value', 'regex_pattern'),
            'classes': ('collapse',)
        }),
        ('Access Control', {
            'fields': ('is_editable', 'requires_restart',
                      'requires_superuser')
        }),
        ('Display', {
            'fields': ('sort_order', 'help_text')
        }),
        ('Audit Information', {
            'fields': ('last_modified_by', 'last_modified_at',
                      'created_at', 'updated_at')
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make key read-only for existing objects"""
        readonly_fields = list(self.readonly_fields)
        if obj and obj.pk:
            readonly_fields.append('key')
            readonly_fields.append('data_type')
        return readonly_fields
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Customize form fields"""
        if db_field.name == 'json_value':
            kwargs['widget'] = admin.widgets.AdminTextareaWidget(attrs={'rows': 10})
        elif db_field.name == 'choices':
            kwargs['widget'] = admin.widgets.AdminTextareaWidget(attrs={'rows': 5})
        return super().formfield_for_dbfield(db_field, request, **kwargs)
    
    actions = ['export_settings', 'import_settings']
    
    def export_settings(self, request, queryset):
        """Action to export settings as JSON"""
        settings_data = []
        for setting in queryset:
            settings_data.append({
                'key': setting.key,
                'name': setting.name,
                'category': setting.category,
                'data_type': setting.data_type,
                'value': setting.get_value(),
                'description': setting.description,
                'is_editable': setting.is_editable,
            })
        
        # In a real implementation, this would return a JSON file
        self.message_user(
            request,
            f"Exported {len(settings_data)} settings. "
            f"JSON: {json.dumps(settings_data, indent=2, default=str)[:200]}...",
            messages.INFO
        )
    export_settings.short_description = "Export selected settings"
    
    def import_settings(self, request, queryset):
        """Action to import settings from JSON"""
        # This would be implemented with file upload
        self.message_user(
            request,
            "Import functionality would open a file upload dialog.",
            messages.INFO
        )
    import_settings.short_description = "Import settings"


@admin.register(BranchSetting)
class BranchSettingAdmin(admin.ModelAdmin):
    list_display = ('branch', 'name', 'key', 'category',
                   'override_system', 'is_editable')
    list_filter = ('branch', 'category', 'override_system',
                  'is_editable')
    search_fields = ('name', 'key', 'description')
    raw_id_fields = ('branch', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('branch', 'key', 'name', 'description',
                      'category', 'data_type', 'group_name')
        }),
        ('Value Storage', {
            'fields': ('string_value', 'integer_value', 'decimal_value',
                      'boolean_value', 'json_value', 'datetime_value',
                      'date_value', 'time_value', 'choices')
        }),
        ('Override Control', {
            'fields': ('override_system',)
        }),
        ('Access Control', {
            'fields': ('is_editable', 'requires_manager')
        }),
        ('Display', {
            'fields': ('sort_order', 'help_text')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at',
                      'created_by', 'updated_by')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by user's branch
        if hasattr(request.user, 'branch'):
            return qs.filter(branch=request.user.branch)
        return qs.none()


@admin.register(ClinicConfiguration)
class ClinicConfigurationAdmin(admin.ModelAdmin):
    list_display = ('branch', 'clinic_name', 'clinic_phone',
                   'opening_time', 'closing_time')
    list_filter = ('branch',)
    search_fields = ('clinic_name', 'clinic_address', 'clinic_phone')
    raw_id_fields = ('branch', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Clinic Information', {
            'fields': ('branch', 'clinic_name', 'clinic_logo',
                      'clinic_address', 'clinic_phone', 'clinic_email',
                      'clinic_website')
        }),
        ('Working Hours', {
            'fields': ('working_days', 'opening_time', 'closing_time',
                      'lunch_start', 'lunch_end')
        }),
        ('Appointment Configuration', {
            'fields': ('appointment_duration', 'max_appointments_per_slot',
                      'buffer_time', 'advance_booking_days')
        }),
        ('Financial Configuration', {
            'fields': ('currency_symbol', 'currency_code',
                      'default_tax_rate')
        }),
        ('Invoice Configuration', {
            'fields': ('invoice_prefix', 'invoice_terms',
                      'invoice_footer')
        }),
        ('Patient Configuration', {
            'fields': ('default_follow_up_days',
                      'send_appointment_reminders',
                      'reminder_hours_before')
        }),
        ('Clinical Configuration', {
            'fields': ('default_consultation_fee',
                      'enable_digital_prescriptions',
                      'enable_treatment_plans')
        }),
        ('Notification Configuration', {
            'fields': ('send_sms_notifications',
                      'send_email_notifications')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at',
                      'created_by', 'updated_by')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by user's branch
        if hasattr(request.user, 'branch'):
            return qs.filter(branch=request.user.branch)
        return qs.none()


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('name', 'branch', 'date', 'is_recurring')
    list_filter = ('branch', 'is_recurring', 'date')
    search_fields = ('name', 'description')
    raw_id_fields = ('branch', 'created_by', 'updated_by')
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('branch', 'name', 'date', 'is_recurring')
        }),
        ('Description', {
            'fields': ('description',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at',
                      'created_by', 'updated_by')
        }),
    )
    
    actions = ['copy_to_other_branches']
    
    def copy_to_other_branches(self, request, queryset):
        """Action to copy holidays to other branches"""
        from apps.clinics.models import Branch
        
        branches = Branch.objects.exclude(
            id__in=queryset.values_list('branch', flat=True).distinct()
        )
        
        count = 0
        for holiday in queryset:
            for branch in branches:
                Holiday.objects.create(
                    branch=branch,
                    name=holiday.name,
                    date=holiday.date,
                    is_recurring=holiday.is_recurring,
                    description=holiday.description,
                    created_by=request.user,
                    updated_by=request.user
                )
                count += 1
        
        self.message_user(request, f"Copied {count} holidays to other branches.")
    copy_to_other_branches.short_description = "Copy to other branches"


@admin.register(TaxConfiguration)
class TaxConfigurationAdmin(admin.ModelAdmin):
    list_display = ('name', 'tax_type', 'rate', 'code',
                   'is_active', 'applicable_from', 'branch')
    list_filter = ('tax_type', 'is_active', 'branch')
    search_fields = ('name', 'code', 'description')
    raw_id_fields = ('branch', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('branch', 'name', 'tax_type', 'rate', 'code',
                      'description')
        }),
        ('Applicability', {
            'fields': ('applicable_from', 'applicable_to', 'is_active')
        }),
        ('Scope', {
            'fields': ('apply_to_services', 'apply_to_products',
                      'apply_to_consultations')
        }),
        ('GST Specific', {
            'fields': ('sgst_rate', 'cgst_rate', 'igst_rate'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at',
                      'created_by', 'updated_by')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by user's branch
        if hasattr(request.user, 'branch'):
            return qs.filter(branch=request.user.branch)
        return qs.none()


@admin.register(SMSConfiguration)
class SMSConfigurationAdmin(admin.ModelAdmin):
    list_display = ('provider', 'branch', 'is_active', 'priority',
                   'total_sent', 'last_used')
    list_filter = ('provider', 'is_active', 'branch')
    search_fields = ('sender_id', 'api_url')
    raw_id_fields = ('branch',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('branch', 'provider', 'is_active', 'priority')
        }),
        ('API Configuration', {
            'fields': ('api_key', 'api_secret', 'sender_id', 'api_url')
        }),
        ('Settings', {
            'fields': ('max_per_day', 'characters_per_sms')
        }),
        ('Status', {
            'fields': ('total_sent', 'successful_sent', 'failed_sent',
                      'last_used')
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make status fields read-only"""
        readonly_fields = super().get_readonly_fields(request, obj)
        if obj and obj.pk:
            readonly_fields = list(readonly_fields) + [
                'total_sent', 'successful_sent', 'failed_sent', 'last_used'
            ]
        return readonly_fields
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by user's branch
        if hasattr(request.user, 'branch'):
            return qs.filter(branch=request.user.branch)
        return qs.none()


@admin.register(EmailConfiguration)
class EmailConfigurationAdmin(admin.ModelAdmin):
    list_display = ('provider', 'branch', 'is_active',
                   'from_email', 'total_sent', 'last_used')
    list_filter = ('provider', 'is_active', 'branch')
    search_fields = ('from_email', 'from_name', 'smtp_host')
    raw_id_fields = ('branch',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('branch', 'provider', 'is_active')
        }),
        ('SMTP Configuration', {
            'fields': ('smtp_host', 'smtp_port', 'smtp_username',
                      'smtp_password', 'use_tls', 'use_ssl')
        }),
        ('Email Settings', {
            'fields': ('from_email', 'from_name', 'reply_to')
        }),
        ('API Configuration', {
            'fields': ('api_key', 'api_secret', 'api_url'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('total_sent', 'successful_sent', 'failed_sent',
                      'last_used')
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make status fields read-only"""
        readonly_fields = super().get_readonly_fields(request, obj)
        if obj and obj.pk:
            readonly_fields = list(readonly_fields) + [
                'total_sent', 'successful_sent', 'failed_sent', 'last_used'
            ]
        return readonly_fields
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by user's branch
        if hasattr(request.user, 'branch'):
            return qs.filter(branch=request.user.branch)
        return qs.none()


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'trigger', 'notification_type',
                   'is_active', 'is_required', 'branch')
    list_filter = ('trigger', 'notification_type', 'is_active',
                  'is_required', 'branch')
    search_fields = ('name', 'sms_template', 'email_subject')
    raw_id_fields = ('branch', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('branch', 'name', 'notification_type',
                      'trigger', 'is_active', 'is_required',
                      'can_override')
        }),
        ('Templates', {
            'fields': ('sms_template', 'email_subject',
                      'email_template')
        }),
        ('Variables', {
            'fields': ('available_variables',),
            'classes': ('collapse',)
        }),
        ('Timing', {
            'fields': ('send_before_hours', 'send_after_hours')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at',
                      'created_by', 'updated_by')
        }),
    )
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Customize form fields"""
        if db_field.name in ['sms_template', 'email_template']:
            kwargs['widget'] = admin.widgets.AdminTextareaWidget(attrs={'rows': 10})
        elif db_field.name == 'available_variables':
            kwargs['widget'] = admin.widgets.AdminTextareaWidget(attrs={'rows': 5})
        return super().formfield_for_dbfield(db_field, request, **kwargs)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by user's branch
        if hasattr(request.user, 'branch'):
            return qs.filter(branch=request.user.branch)
        return qs.none()


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ('role', 'module', 'can_view', 'can_create',
                   'can_edit', 'can_delete', 'can_approve')
    list_filter = ('role', 'module', 'scope_all_branches')
    search_fields = ('role__name', 'module')
    raw_id_fields = ('role',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('role', 'module', 'scope_all_branches')
        }),
        ('Permissions', {
            'fields': ('can_view', 'can_create', 'can_edit',
                      'can_delete', 'can_approve', 'can_export')
        }),
        ('Custom Permissions', {
            'fields': ('custom_permissions',),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Customize form fields"""
        if db_field.name == 'custom_permissions':
            kwargs['widget'] = admin.widgets.AdminTextareaWidget(attrs={'rows': 10})
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(BackupConfiguration)
class BackupConfigurationAdmin(admin.ModelAdmin):
    list_display = ('branch', 'backup_type', 'storage_type',
                   'is_active', 'frequency', 'last_backup',
                   'total_backups')
    list_filter = ('backup_type', 'storage_type', 'is_active',
                  'frequency', 'branch')
    search_fields = ('local_path', 'aws_bucket', 'google_drive_folder')
    raw_id_fields = ('branch',)
    
    fieldsets = (
        ('Basic Configuration', {
            'fields': ('branch', 'backup_type', 'storage_type',
                      'is_active')
        }),
        ('Schedule', {
            'fields': ('frequency', 'schedule_time', 'retention_days')
        }),
        ('Storage Configuration', {
            'fields': ('local_path', 'aws_bucket', 'aws_access_key',
                      'aws_secret_key', 'google_drive_folder',
                      'azure_container')
        }),
        ('Notification', {
            'fields': ('notify_on_success', 'notify_on_failure',
                      'notify_email')
        }),
        ('Status', {
            'fields': ('last_backup', 'last_backup_size',
                      'total_backups', 'successful_backups',
                      'failed_backups')
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make status fields read-only"""
        readonly_fields = super().get_readonly_fields(request, obj)
        if obj and obj.pk:
            readonly_fields = list(readonly_fields) + [
                'last_backup', 'last_backup_size', 'total_backups',
                'successful_backups', 'failed_backups'
            ]
        return readonly_fields
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by user's branch
        if hasattr(request.user, 'branch'):
            return qs.filter(branch=request.user.branch)
        return qs.none()


@admin.register(AuditLogConfiguration)
class AuditLogConfigurationAdmin(admin.ModelAdmin):
    list_display = ('branch', 'log_level', 'enable_login_logging',
                   'retention_days', 'enable_alerts')
    list_filter = ('log_level', 'enable_login_logging',
                  'enable_alerts', 'branch')
    raw_id_fields = ('branch', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Basic Configuration', {
            'fields': ('branch', 'log_level')
        }),
        ('Logging Settings', {
            'fields': ('enable_login_logging', 'enable_data_change_logging',
                      'enable_financial_logging', 'enable_system_event_logging')
        }),
        ('Retention', {
            'fields': ('retention_days', 'archive_after_days')
        }),
        ('Export', {
            'fields': ('allow_log_export', 'export_requires_approval')
        }),
        ('Monitoring', {
            'fields': ('enable_alerts', 'alert_on_multiple_failures',
                      'failure_threshold')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at',
                      'created_by', 'updated_by')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by user's branch
        if hasattr(request.user, 'branch'):
            return qs.filter(branch=request.user.branch)
        return qs.none()