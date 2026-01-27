# apps/integrations/admin.py

from django.contrib import admin
from .models import (
    IntegrationType, IntegrationProvider, BranchIntegration,
    PharmacyIntegration, PaymentGatewayIntegration,
    IntegrationLog, WebhookEvent, PharmacyOrder, PaymentTransaction
)


@admin.register(IntegrationType)
class IntegrationTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'integration_type', 'is_active')
    list_filter = ('integration_type', 'is_active')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')


@admin.register(IntegrationProvider)
class IntegrationProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'provider_type', 'integration_type', 'is_active')
    list_filter = ('provider_type', 'integration_type', 'is_active')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')


@admin.register(BranchIntegration)
class BranchIntegrationAdmin(admin.ModelAdmin):
    list_display = ('branch', 'provider', 'integration_type', 'status', 'is_default')
    list_filter = ('status', 'is_default', 'integration_type', 'branch')
    search_fields = ('branch__name', 'provider__name')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'last_sync')
    fieldsets = (
        ('Basic Info', {
            'fields': ('branch', 'provider', 'integration_type', 'status', 'is_default')
        }),
        ('Authentication', {
            'fields': ('auth_type', 'api_key', 'api_secret', 'access_token', 
                      'refresh_token', 'token_expiry')
        }),
        ('Configuration', {
            'fields': ('endpoint_url', 'webhook_url', 'webhook_secret', 'config_data')
        }),
        ('Sync Info', {
            'fields': ('last_sync', 'sync_status', 'sync_error', 'is_test_mode')
        }),
    )


@admin.register(PharmacyIntegration)
class PharmacyIntegrationAdmin(admin.ModelAdmin):
    list_display = ('branch_integration', 'delivery_enabled', 'sync_inventory', 'auto_create_order')
    list_filter = ('delivery_enabled', 'sync_inventory', 'auto_create_order')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')


@admin.register(PaymentGatewayIntegration)
class PaymentGatewayIntegrationAdmin(admin.ModelAdmin):
    list_display = ('branch_integration', 'currency', 'accept_upi', 'auto_refund')
    list_filter = ('currency', 'accept_upi', 'auto_refund')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')


@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = ('branch_integration', 'log_type', 'direction', 'status', 'started_at')
    list_filter = ('log_type', 'direction', 'status', 'branch_integration')
    search_fields = ('endpoint', 'error_message')
    readonly_fields = ('started_at', 'completed_at', 'duration', 'created_at', 'updated_at')
    date_hierarchy = 'started_at'


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ('branch_integration', 'event_type', 'processed', 'created_at')
    list_filter = ('event_type', 'processed', 'branch_integration')
    search_fields = ('event_id', 'processing_error')
    readonly_fields = ('created_at', 'updated_at', 'processed_at')
    date_hierarchy = 'created_at'


@admin.register(PharmacyOrder)
class PharmacyOrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'prescription', 'status', 'payment_status', 'total', 'created_at')
    list_filter = ('status', 'payment_status', 'delivery_type', 'branch_integration')
    search_fields = ('order_id', 'external_order_id', 'prescription__patient__name')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    date_hierarchy = 'created_at'


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'invoice', 'status', 'amount', 'payment_method', 'initiated_at')
    list_filter = ('status', 'payment_type', 'payment_method', 'branch_integration')
    search_fields = ('transaction_id', 'external_transaction_id', 'customer_email', 'customer_phone')
    readonly_fields = ('initiated_at', 'authorized_at', 'captured_at', 'refunded_at', 
                      'verified_at', 'created_at', 'updated_at')
    date_hierarchy = 'initiated_at'