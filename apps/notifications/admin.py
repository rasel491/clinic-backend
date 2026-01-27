# # apps/notifications/admin.py
# from django.contrib import admin
# from .models import (
#     NotificationTemplate, NotificationLog, SMSProvider,
#     EmailProvider, NotificationSetting, NotificationQueue
# )


# @admin.register(NotificationTemplate)
# class NotificationTemplateAdmin(admin.ModelAdmin):
#     list_display = ('name', 'notification_type', 'category', 'is_active', 'branch')
#     list_filter = ('notification_type', 'category', 'is_active', 'branch')
#     search_fields = ('name', 'subject', 'body')
#     readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')


# @admin.register(NotificationLog)
# class NotificationLogAdmin(admin.ModelAdmin):
#     list_display = ('recipient_contact', 'notification_type', 'status', 'priority', 'created_at', 'branch')
#     list_filter = ('notification_type', 'status', 'priority', 'branch')
#     search_fields = ('recipient_contact', 'message', 'subject')
#     readonly_fields = ('created_at', 'updated_at', 'sent_at', 'delivered_at', 'read_at')
#     date_hierarchy = 'created_at'


# @admin.register(SMSProvider)
# class SMSProviderAdmin(admin.ModelAdmin):
#     list_display = ('name', 'provider_type', 'is_default', 'is_active', 'branch')
#     list_filter = ('provider_type', 'is_default', 'is_active', 'branch')
#     readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')


# @admin.register(EmailProvider)
# class EmailProviderAdmin(admin.ModelAdmin):
#     list_display = ('name', 'provider_type', 'is_default', 'is_active', 'branch')
#     list_filter = ('provider_type', 'is_default', 'is_active', 'branch')
#     readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')


# @admin.register(NotificationSetting)
# class NotificationSettingAdmin(admin.ModelAdmin):
#     list_display = ('category', 'send_sms', 'send_email', 'send_whatsapp', 'is_active')
#     list_filter = ('is_active',)
#     readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')


# @admin.register(NotificationQueue)
# class NotificationQueueAdmin(admin.ModelAdmin):
#     list_display = ('notification_log', 'priority', 'retry_count', 'processing', 'created_at')
#     list_filter = ('priority', 'processing')
#     readonly_fields = ('created_at', 'updated_at', 'processed_at')


# apps/notifications/admin.py
from django.contrib import admin
from .models import (
    NotificationTemplate, NotificationLog, SMSProvider,
    EmailProvider, NotificationSetting, NotificationQueue
)

@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'notification_type', 'category', 'branch', 'is_active']
    list_filter = ['notification_type', 'category', 'is_active', 'branch']
    search_fields = ['name', 'subject', 'body']

@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'recipient_contact', 'notification_type', 'status', 'branch', 'created_at']
    list_filter = ['notification_type', 'status', 'branch', 'created_at']
    search_fields = ['recipient_contact', 'message', 'subject']

@admin.register(SMSProvider)
class SMSProviderAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider_type', 'is_default', 'is_active', 'branch']
    list_filter = ['provider_type', 'is_default', 'is_active', 'branch']

@admin.register(EmailProvider)
class EmailProviderAdmin(admin.ModelAdmin):
    list_display = ['name', 'provider_type', 'is_default', 'is_active', 'branch']
    list_filter = ['provider_type', 'is_default', 'is_active', 'branch']

@admin.register(NotificationSetting)
class NotificationSettingAdmin(admin.ModelAdmin):
    list_display = ['category', 'send_sms', 'send_email', 'is_active']
    list_filter = ['is_active']

@admin.register(NotificationQueue)
class NotificationQueueAdmin(admin.ModelAdmin):
    list_display = ['id', 'notification_log', 'priority', 'processing', 'created_at']
    list_filter = ['priority', 'processing']