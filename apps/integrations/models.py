# apps/integrations/models.py

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.postgres.fields import JSONField
from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin
import uuid


class IntegrationType(AuditFieldsMixin, SoftDeleteMixin):
    """Types of integrations (Pharmacy, Payment, Lab, etc.)"""
    INTEGRATION_TYPES = [
        ('pharmacy', 'Pharmacy'),
        ('payment', 'Payment Gateway'),
        ('lab', 'Laboratory'),
        ('imaging', 'Imaging Center'),
        ('insurance', 'Insurance'),
        ('accounting', 'Accounting Software'),
        ('crm', 'CRM'),
        ('others', 'Others'),
    ]
    
    name = models.CharField(max_length=100)
    integration_type = models.CharField(max_length=20, choices=INTEGRATION_TYPES)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_integration_type_display()})"


class IntegrationProvider(AuditFieldsMixin, SoftDeleteMixin):
    """Providers for each integration type"""
    PROVIDER_TYPES = [
        ('razorpay', 'Razorpay'),
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('instamojo', 'Instamojo'),
        ('pharmeasy', 'PharmEasy'),
        ('netmeds', 'Netmeds'),
        ('apollo', 'Apollo Pharmacy'),
        ('custom', 'Custom API'),
    ]
    
    name = models.CharField(max_length=100)
    provider_type = models.CharField(max_length=20, choices=PROVIDER_TYPES)
    integration_type = models.ForeignKey(IntegrationType, on_delete=models.CASCADE, related_name='providers')
    description = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to='integration_logos/', blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.integration_type}"


class BranchIntegration(AuditFieldsMixin, SoftDeleteMixin):
    """Integration configuration for a specific branch"""
    AUTH_TYPES = [
        ('api_key', 'API Key'),
        ('oauth', 'OAuth 2.0'),
        ('basic', 'Basic Auth'),
        ('jwt', 'JWT'),
        ('custom', 'Custom'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending Setup'),
        ('failed', 'Failed'),
    ]
    
    branch = models.ForeignKey('clinics.Branch', on_delete=models.CASCADE, related_name='integrations')
    provider = models.ForeignKey(IntegrationProvider, on_delete=models.CASCADE, related_name='branch_configs')
    integration_type = models.ForeignKey(IntegrationType, on_delete=models.CASCADE, related_name='branch_configs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_default = models.BooleanField(default=False, help_text="Default integration for this type")
    
    # Authentication
    auth_type = models.CharField(max_length=20, choices=AUTH_TYPES, default='api_key')
    api_key = models.CharField(max_length=500, blank=True, null=True)
    api_secret = models.CharField(max_length=500, blank=True, null=True)
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    token_expiry = models.DateTimeField(blank=True, null=True)
    
    # Configuration
    endpoint_url = models.URLField(blank=True, null=True)
    webhook_url = models.URLField(blank=True, null=True)
    webhook_secret = models.CharField(max_length=500, blank=True, null=True)
    config_data = models.JSONField(default=dict, help_text="Provider-specific configuration")
    
    # Meta
    last_sync = models.DateTimeField(blank=True, null=True)
    sync_status = models.CharField(max_length=20, blank=True, null=True)
    sync_error = models.TextField(blank=True, null=True)
    is_test_mode = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-is_default', 'provider__name']
        unique_together = ['branch', 'provider', 'integration_type']
    
    def __str__(self):
        return f"{self.branch.name} - {self.provider.name}"


class PharmacyIntegration(AuditFieldsMixin):
    """Specific configuration for pharmacy integrations"""
    branch_integration = models.OneToOneField(BranchIntegration, on_delete=models.CASCADE, related_name='pharmacy_config')
    
    # Pharmacy specific
    pharmacy_id = models.CharField(max_length=100, blank=True, null=True, help_text="Pharmacy's ID for this clinic")
    store_id = models.CharField(max_length=100, blank=True, null=True)
    delivery_enabled = models.BooleanField(default=True)
    delivery_radius = models.IntegerField(default=10, help_text="Delivery radius in km")
    delivery_time = models.IntegerField(default=60, help_text="Estimated delivery time in minutes")
    
    # Inventory sync
    sync_inventory = models.BooleanField(default=False)
    inventory_sync_interval = models.IntegerField(default=60, help_text="Minutes between syncs")
    last_inventory_sync = models.DateTimeField(blank=True, null=True)
    
    # Order settings
    auto_create_order = models.BooleanField(default=False)
    require_confirmation = models.BooleanField(default=True)
    payment_method = models.CharField(max_length=50, default='cod', choices=[
        ('cod', 'Cash on Delivery'),
        ('prepaid', 'Prepaid'),
        ('both', 'Both'),
    ])
    
    class Meta:
        verbose_name = "Pharmacy Integration"
        verbose_name_plural = "Pharmacy Integrations"
    
    def __str__(self):
        return f"Pharmacy Config for {self.branch_integration}"


class PaymentGatewayIntegration(AuditFieldsMixin):
    """Specific configuration for payment gateway integrations"""
    branch_integration = models.OneToOneField(BranchIntegration, on_delete=models.CASCADE, related_name='payment_config')
    
    # Payment specific
    merchant_id = models.CharField(max_length=100, blank=True, null=True)
    terminal_id = models.CharField(max_length=100, blank=True, null=True)
    currency = models.CharField(max_length=3, default='INR')
    
    # Payment methods
    accept_credit_card = models.BooleanField(default=True)
    accept_debit_card = models.BooleanField(default=True)
    accept_netbanking = models.BooleanField(default=True)
    accept_upi = models.BooleanField(default=True)
    accept_wallet = models.BooleanField(default=True)
    
    # Settlement
    settlement_days = models.IntegerField(default=2)
    auto_refund = models.BooleanField(default=False)
    refund_days = models.IntegerField(default=7)
    
    # Security
    use_encryption = models.BooleanField(default=True)
    encryption_key = models.CharField(max_length=500, blank=True, null=True)
    
    class Meta:
        verbose_name = "Payment Gateway Integration"
        verbose_name_plural = "Payment Gateway Integrations"
    
    def __str__(self):
        return f"Payment Config for {self.branch_integration}"


class IntegrationLog(AuditFieldsMixin):
    """Log of all integration activities"""
    LOG_TYPES = [
        ('api_call', 'API Call'),
        ('webhook', 'Webhook'),
        ('sync', 'Data Sync'),
        ('auth', 'Authentication'),
        ('error', 'Error'),
        ('webhook', 'Webhook Received'),
    ]
    
    DIRECTION_CHOICES = [
        ('outgoing', 'Outgoing'),
        ('incoming', 'Incoming'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    ]
    
    branch_integration = models.ForeignKey(BranchIntegration, on_delete=models.CASCADE, related_name='logs')
    log_type = models.CharField(max_length=20, choices=LOG_TYPES)
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    
    # Request/Response
    endpoint = models.CharField(max_length=500, blank=True, null=True)
    method = models.CharField(max_length=10, blank=True, null=True)
    request_data = models.JSONField(default=dict, blank=True, null=True)
    request_headers = models.JSONField(default=dict, blank=True, null=True)
    response_data = models.JSONField(default=dict, blank=True, null=True)
    response_headers = models.JSONField(default=dict, blank=True, null=True)
    response_code = models.IntegerField(blank=True, null=True)
    
    # Timing
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(blank=True, null=True)
    duration = models.FloatField(blank=True, null=True, help_text="Duration in seconds")
    
    # Error info
    error_message = models.TextField(blank=True, null=True)
    error_code = models.CharField(max_length=100, blank=True, null=True)
    retry_count = models.IntegerField(default=0)
    
    # Related objects
    related_object_type = models.CharField(max_length=50, blank=True, null=True)
    related_object_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['branch_integration', 'started_at']),
            models.Index(fields=['log_type', 'status']),
        ]
    
    def save(self, *args, **kwargs):
        if self.started_at and self.completed_at:
            self.duration = (self.completed_at - self.started_at).total_seconds()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.log_type} - {self.status} - {self.branch_integration}"


class WebhookEvent(AuditFieldsMixin):
    """Incoming webhook events from integrated services"""
    EVENT_TYPES = [
        ('payment_success', 'Payment Success'),
        ('payment_failed', 'Payment Failed'),
        ('payment_refunded', 'Payment Refunded'),
        ('order_created', 'Order Created'),
        ('order_shipped', 'Order Shipped'),
        ('order_delivered', 'Order Delivered'),
        ('order_cancelled', 'Order Cancelled'),
        ('inventory_update', 'Inventory Update'),
        ('prescription_ready', 'Prescription Ready'),
        ('appointment_reminder', 'Appointment Reminder'),
        ('custom', 'Custom Event'),
    ]
    
    branch_integration = models.ForeignKey(BranchIntegration, on_delete=models.CASCADE, related_name='webhooks')
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    event_id = models.CharField(max_length=100, blank=True, null=True, help_text="External event ID")
    
    # Payload
    payload = models.JSONField(default=dict)
    headers = models.JSONField(default=dict)
    signature = models.CharField(max_length=500, blank=True, null=True)
    
    # Processing
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(blank=True, null=True)
    processing_error = models.TextField(blank=True, null=True)
    
    # Related object after processing
    related_object_type = models.CharField(max_length=50, blank=True, null=True)
    related_object_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['branch_integration', 'event_type']),
            models.Index(fields=['processed', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.branch_integration}"


class PharmacyOrder(AuditFieldsMixin):
    """Orders placed with integrated pharmacies"""
    ORDER_STATUS = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed by Pharmacy'),
        ('processing', 'Processing'),
        ('ready', 'Ready for Pickup'),
        ('shipped', 'Shipped'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    # Identifiers
    order_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    external_order_id = models.CharField(max_length=100, blank=True, null=True, help_text="Pharmacy's order ID")
    prescription = models.ForeignKey('prescriptions.Prescription', on_delete=models.CASCADE, related_name='pharmacy_orders')
    branch_integration = models.ForeignKey(BranchIntegration, on_delete=models.CASCADE, related_name='pharmacy_orders')
    
    # Order details
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_method = models.CharField(max_length=20, default='cod')
    
    # Delivery
    delivery_address = models.JSONField(default=dict)
    delivery_type = models.CharField(max_length=20, default='delivery', choices=[
        ('delivery', 'Delivery'),
        ('pickup', 'Pickup'),
    ])
    estimated_delivery = models.DateTimeField(blank=True, null=True)
    actual_delivery = models.DateTimeField(blank=True, null=True)
    
    # Financials
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Items
    items = models.JSONField(default=list, help_text="List of medicines with details")
    
    # Tracking
    tracking_url = models.URLField(blank=True, null=True)
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_id']),
            models.Index(fields=['prescription', 'status']),
            models.Index(fields=['status', 'payment_status']),
        ]
    
    def __str__(self):
        return f"Order {self.order_id} - {self.get_status_display()}"


class PaymentTransaction(AuditFieldsMixin):
    """Payment transactions through integrated gateways"""
    PAYMENT_TYPES = [
        ('payment', 'Payment'),
        ('refund', 'Refund'),
        ('capture', 'Capture'),
        ('void', 'Void'),
    ]
    
    PAYMENT_STATUS = [
        ('created', 'Created'),
        ('authorized', 'Authorized'),
        ('captured', 'Captured'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    ]
    
    # Identifiers
    transaction_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    external_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    payment_id = models.CharField(max_length=100, blank=True, null=True)
    order_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Relations
    branch_integration = models.ForeignKey(BranchIntegration, on_delete=models.CASCADE, related_name='payment_transactions')
    invoice = models.ForeignKey('billing.Invoice', on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_transactions')
    
    # Payment details
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES, default='payment')
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='created')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    
    # Method
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    payment_method_type = models.CharField(max_length=50, blank=True, null=True)
    card_last4 = models.CharField(max_length=4, blank=True, null=True)
    card_network = models.CharField(max_length=20, blank=True, null=True)
    upi_id = models.CharField(max_length=50, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    
    # Customer
    customer_name = models.CharField(max_length=200, blank=True, null=True)
    customer_email = models.CharField(max_length=200, blank=True, null=True)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    
    # Gateway response
    gateway_response = models.JSONField(default=dict, blank=True, null=True)
    gateway_error = models.TextField(blank=True, null=True)
    gateway_code = models.CharField(max_length=100, blank=True, null=True)
    
    # Timing
    initiated_at = models.DateTimeField()
    authorized_at = models.DateTimeField(blank=True, null=True)
    captured_at = models.DateTimeField(blank=True, null=True)
    refunded_at = models.DateTimeField(blank=True, null=True)
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(blank=True, null=True)
    verification_notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['external_transaction_id']),
            models.Index(fields=['status', 'initiated_at']),
            models.Index(fields=['invoice', 'status']),
        ]
    
    def __str__(self):
        return f"Txn {self.transaction_id} - {self.amount} {self.currency} - {self.get_status_display()}"