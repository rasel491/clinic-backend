# apps/integrations/serializers.py
from rest_framework import serializers
from django.utils import timezone
import uuid
from .models import (
    IntegrationType, IntegrationProvider, BranchIntegration,
    PharmacyIntegration, PaymentGatewayIntegration,
    IntegrationLog, WebhookEvent, PharmacyOrder, PaymentTransaction
)
from apps.clinics.serializers import BranchSerializer
from apps.prescriptions.serializers import PrescriptionSerializer
from apps.billing.serializers import InvoiceSerializer


class IntegrationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationType
        fields = [
            'id', 'name', 'integration_type', 'description', 
            'is_active', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']


class IntegrationProviderSerializer(serializers.ModelSerializer):
    integration_type_details = IntegrationTypeSerializer(source='integration_type', read_only=True)
    
    class Meta:
        model = IntegrationProvider
        fields = [
            'id', 'name', 'provider_type', 'integration_type', 'integration_type_details',
            'description', 'logo', 'website', 'is_active',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']


class BranchIntegrationSerializer(serializers.ModelSerializer):
    branch = BranchSerializer(read_only=True)
    branch_id = serializers.IntegerField(write_only=True)
    provider_details = IntegrationProviderSerializer(source='provider', read_only=True)
    integration_type_details = IntegrationTypeSerializer(source='integration_type', read_only=True)
    
    class Meta:
        model = BranchIntegration
        fields = [
            'id', 'branch', 'branch_id', 'provider', 'provider_details',
            'integration_type', 'integration_type_details', 'status', 'is_default',
            'auth_type', 'api_key', 'api_secret', 'access_token', 'refresh_token',
            'token_expiry', 'endpoint_url', 'webhook_url', 'webhook_secret',
            'config_data', 'last_sync', 'sync_status', 'sync_error', 'is_test_mode',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
        extra_kwargs = {
            'api_key': {'write_only': True},
            'api_secret': {'write_only': True},
            'access_token': {'write_only': True},
            'refresh_token': {'write_only': True},
            'webhook_secret': {'write_only': True},
        }
    
    def validate(self, data):
        if data.get('is_default'):
            # If setting as default, update other integrations of same type
            BranchIntegration.objects.filter(
                branch_id=data.get('branch_id'),
                integration_type=data.get('integration_type'),
                is_default=True
            ).update(is_default=False)
        
        # Validate based on integration type
        integration_type = data.get('integration_type')
        if integration_type:
            if integration_type.integration_type == 'payment':
                if not data.get('endpoint_url'):
                    raise serializers.ValidationError({
                        'endpoint_url': 'Endpoint URL is required for payment integrations'
                    })
        
        return data


class PharmacyIntegrationSerializer(serializers.ModelSerializer):
    branch_integration_details = BranchIntegrationSerializer(source='branch_integration', read_only=True)
    
    class Meta:
        model = PharmacyIntegration
        fields = [
            'id', 'branch_integration', 'branch_integration_details',
            'pharmacy_id', 'store_id', 'delivery_enabled', 'delivery_radius',
            'delivery_time', 'sync_inventory', 'inventory_sync_interval',
            'last_inventory_sync', 'auto_create_order', 'require_confirmation',
            'payment_method', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']


class PaymentGatewayIntegrationSerializer(serializers.ModelSerializer):
    branch_integration_details = BranchIntegrationSerializer(source='branch_integration', read_only=True)
    
    class Meta:
        model = PaymentGatewayIntegration
        fields = [
            'id', 'branch_integration', 'branch_integration_details',
            'merchant_id', 'terminal_id', 'currency', 'accept_credit_card',
            'accept_debit_card', 'accept_netbanking', 'accept_upi',
            'accept_wallet', 'settlement_days', 'auto_refund', 'refund_days',
            'use_encryption', 'encryption_key', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
        extra_kwargs = {
            'encryption_key': {'write_only': True},
        }


class IntegrationLogSerializer(serializers.ModelSerializer):
    branch_integration_details = BranchIntegrationSerializer(source='branch_integration', read_only=True)
    
    class Meta:
        model = IntegrationLog
        fields = [
            'id', 'branch_integration', 'branch_integration_details', 'log_type',
            'direction', 'status', 'endpoint', 'method', 'request_data',
            'request_headers', 'response_data', 'response_headers', 'response_code',
            'started_at', 'completed_at', 'duration', 'error_message', 'error_code',
            'retry_count', 'related_object_type', 'related_object_id',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by', 'duration']


class WebhookEventSerializer(serializers.ModelSerializer):
    branch_integration_details = BranchIntegrationSerializer(source='branch_integration', read_only=True)
    
    class Meta:
        model = WebhookEvent
        fields = [
            'id', 'branch_integration', 'branch_integration_details', 'event_type',
            'event_id', 'payload', 'headers', 'signature', 'processed',
            'processed_at', 'processing_error', 'related_object_type',
            'related_object_id', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']


class PharmacyOrderSerializer(serializers.ModelSerializer):
    prescription_details = PrescriptionSerializer(source='prescription', read_only=True)
    branch_integration_details = BranchIntegrationSerializer(source='branch_integration', read_only=True)
    
    class Meta:
        model = PharmacyOrder
        fields = [
            'id', 'order_id', 'external_order_id', 'prescription', 'prescription_details',
            'branch_integration', 'branch_integration_details', 'status', 'payment_status',
            'payment_method', 'delivery_address', 'delivery_type', 'estimated_delivery',
            'actual_delivery', 'subtotal', 'tax', 'delivery_charge', 'discount', 'total',
            'items', 'tracking_url', 'tracking_number', 'notes',
            'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = ['order_id', 'created_at', 'updated_at', 'created_by', 'updated_by']
    
    def create(self, validated_data):
        validated_data['order_id'] = str(uuid.uuid4())
        return super().create(validated_data)


class PaymentTransactionSerializer(serializers.ModelSerializer):
    invoice_details = InvoiceSerializer(source='invoice', read_only=True)
    branch_integration_details = BranchIntegrationSerializer(source='branch_integration', read_only=True)
    
    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'transaction_id', 'external_transaction_id', 'payment_id', 'order_id',
            'branch_integration', 'branch_integration_details', 'invoice', 'invoice_details',
            'payment_type', 'status', 'amount', 'currency', 'payment_method',
            'payment_method_type', 'card_last4', 'card_network', 'upi_id', 'bank_name',
            'customer_name', 'customer_email', 'customer_phone', 'gateway_response',
            'gateway_error', 'gateway_code', 'initiated_at', 'authorized_at',
            'captured_at', 'refunded_at', 'is_verified', 'verified_at',
            'verification_notes', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
        read_only_fields = [
            'transaction_id', 'initiated_at', 'authorized_at', 'captured_at',
            'refunded_at', 'created_at', 'updated_at', 'created_by', 'updated_by'
        ]
    
    def create(self, validated_data):
        validated_data['transaction_id'] = str(uuid.uuid4())
        validated_data['initiated_at'] = timezone.now()
        return super().create(validated_data)


# Pharmacy-specific serializers
class PharmacyOrderCreateSerializer(serializers.Serializer):
    """Serializer for creating pharmacy orders"""
    prescription_id = serializers.IntegerField(required=True)
    delivery_type = serializers.ChoiceField(choices=[('delivery', 'Delivery'), ('pickup', 'Pickup')])
    delivery_address = serializers.JSONField(required=False)
    payment_method = serializers.ChoiceField(
        choices=[('cod', 'Cash on Delivery'), ('prepaid', 'Prepaid')],
        default='cod'
    )
    notes = serializers.CharField(required=False, allow_blank=True)


class PaymentIntentSerializer(serializers.Serializer):
    """Serializer for creating payment intents"""
    invoice_id = serializers.IntegerField(required=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    currency = serializers.CharField(default='INR', max_length=3)
    payment_method = serializers.CharField(required=False)
    customer_name = serializers.CharField(required=False)
    customer_email = serializers.EmailField(required=False)
    customer_phone = serializers.CharField(required=False)
    return_url = serializers.URLField(required=False)