# apps/otp/admin.py

from django.contrib import admin
from .models import (
    OTPConfig, OTPRequest, OTPBlacklist,
    OTPRateLimit, OTPTemplate
)


@admin.register(OTPConfig)
class OTPConfigAdmin(admin.ModelAdmin):
    list_display = ('branch', 'default_otp_length', 'default_expiry_minutes', 'max_attempts_per_otp')
    list_filter = ('branch',)
    search_fields = ('branch__name',)
    readonly_fields = ('total_otp_sent', 'total_verified', 'total_failed')


@admin.register(OTPRequest)
class OTPRequestAdmin(admin.ModelAdmin):
    list_display = ('recipient_contact', 'otp_type', 'status', 'created_at', 'expires_at', 'branch')
    list_filter = ('status', 'otp_type', 'channel', 'branch', 'created_at')
    search_fields = ('recipient_contact', 'otp_code', 'reference_id')
    readonly_fields = ('created_at', 'updated_at', 'sent_at', 'delivered_at', 'verified_at')
    date_hierarchy = 'created_at'


@admin.register(OTPBlacklist)
class OTPBlacklistAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'blacklist_type', 'reason', 'is_permanent', 'blocked_until')
    list_filter = ('blacklist_type', 'reason', 'is_permanent', 'branch')
    search_fields = ('identifier', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OTPRateLimit)
class OTPRateLimitAdmin(admin.ModelAdmin):
    list_display = ('identifier', 'identifier_type', 'request_count', 'last_request', 'branch')
    list_filter = ('identifier_type', 'branch')
    search_fields = ('identifier',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OTPTemplate)
class OTPTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'is_default', 'branch')
    list_filter = ('template_type', 'is_default', 'branch')
    search_fields = ('name', 'content')
    readonly_fields = ('created_at', 'updated_at')