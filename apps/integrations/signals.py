# apps/integrations/signals.py

# apps/integrations/signals.py

import logging
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache

from apps.audit.models import AuditLog
from .models import (
    IntegrationType, IntegrationProvider, BranchIntegration,
    PharmacyIntegration, PaymentGatewayIntegration,
    IntegrationLog, WebhookEvent, PharmacyOrder, PaymentTransaction
)

logger = logging.getLogger(__name__)

# Cache keys
INTEGRATION_CACHE_KEYS = {
    'branch_active': 'branch_integrations_active:{branch_id}',
    'integration_types': 'integration_types_all',
    'providers_by_type': 'providers_by_type:{type_id}',
}


def clear_integration_cache(branch_id=None, integration_type_id=None):
    """Clear integration related cache"""
    if branch_id:
        cache.delete(INTEGRATION_CACHE_KEYS['branch_active'].format(branch_id=branch_id))
    
    cache.delete(INTEGRATION_CACHE_KEYS['integration_types'])
    
    if integration_type_id:
        cache.delete(INTEGRATION_CACHE_KEYS['providers_by_type'].format(type_id=integration_type_id))


@receiver(post_save, sender=IntegrationType)
def integration_type_changed(sender, instance, created, **kwargs):
    """Handle integration type changes"""
    clear_integration_cache(integration_type_id=instance.id)
    
    action = 'CREATED' if created else 'UPDATED'
    
    AuditLog.objects.create(
        user=instance.updated_by,
        action=f'INTEGRATION_TYPE_{action}',
        model_name='IntegrationType',
        object_id=str(instance.id),
        details={
            'name': instance.name,
            'integration_type': instance.integration_type,
            'is_active': instance.is_active,
            'changes': {
                'name': instance.name,
                'type': instance.integration_type,
                'active': instance.is_active
            }
        },
        ip_address=None,
        user_agent=None
    )
    
    logger.info(f"Integration type {instance.name} {action.lower()}")


@receiver(post_save, sender=IntegrationProvider)
def integration_provider_changed(sender, instance, created, **kwargs):
    """Handle integration provider changes"""
    clear_integration_cache(integration_type_id=instance.integration_type_id)
    
    action = 'CREATED' if created else 'UPDATED'
    
    AuditLog.objects.create(
        user=instance.updated_by,
        action=f'INTEGRATION_PROVIDER_{action}',
        model_name='IntegrationProvider',
        object_id=str(instance.id),
        details={
            'name': instance.name,
            'provider_type': instance.provider_type,
            'integration_type': instance.integration_type.name,
            'is_active': instance.is_active,
        },
        ip_address=None,
        user_agent=None
    )


@receiver(pre_save, sender=BranchIntegration)
def validate_branch_integration(sender, instance, **kwargs):
    """Validate branch integration before saving"""
    # Ensure only one default integration per type per branch
    if instance.is_default:
        BranchIntegration.objects.filter(
            branch=instance.branch,
            integration_type=instance.integration_type,
            is_default=True
        ).exclude(pk=instance.pk).update(is_default=False)
    
    # Validate auth type and credentials
    if instance.auth_type == 'api_key':
        if not instance.api_key:
            raise ValueError("API key is required for API key authentication")
    
    elif instance.auth_type == 'oauth' and not instance.access_token:
        # For OAuth, we need either access token or ability to get one
        if not instance.api_key or not instance.api_secret:
            raise ValueError("API key and secret are required for OAuth authentication")


@receiver(post_save, sender=BranchIntegration)
def branch_integration_changed(sender, instance, created, **kwargs):
    """Handle branch integration changes"""
    clear_integration_cache(branch_id=instance.branch_id)
    
    action = 'CREATED' if created else 'UPDATED'
    
    AuditLog.objects.create(
        user=instance.updated_by,
        action=f'BRANCH_INTEGRATION_{action}',
        model_name='BranchIntegration',
        object_id=str(instance.id),
        details={
            'branch_id': str(instance.branch_id),
            'branch_name': instance.branch.name,
            'provider': instance.provider.name,
            'integration_type': instance.integration_type.name,
            'status': instance.status,
            'is_default': instance.is_default,
        },
        ip_address=None,
        user_agent=None
    )
    
    # If integration is set to active, ensure proper configuration exists
    if instance.status == 'active':
        if instance.integration_type.integration_type == 'pharmacy':
            # Ensure pharmacy integration config exists
            PharmacyIntegration.objects.get_or_create(branch_integration=instance)
        elif instance.integration_type.integration_type == 'payment':
            # Ensure payment gateway config exists
            PaymentGatewayIntegration.objects.get_or_create(branch_integration=instance)


@receiver(post_save, sender=PharmacyIntegration)
def pharmacy_integration_changed(sender, instance, created, **kwargs):
    """Handle pharmacy integration changes"""
    action = 'CREATED' if created else 'UPDATED'
    
    AuditLog.objects.create(
        user=instance.updated_by,
        action=f'PHARMACY_INTEGRATION_{action}',
        model_name='PharmacyIntegration',
        object_id=str(instance.id),
        details={
            'branch_integration_id': str(instance.branch_integration_id),
            'delivery_enabled': instance.delivery_enabled,
            'sync_inventory': instance.sync_inventory,
            'auto_create_order': instance.auto_create_order,
        },
        ip_address=None,
        user_agent=None
    )


@receiver(post_save, sender=PaymentGatewayIntegration)
def payment_gateway_integration_changed(sender, instance, created, **kwargs):
    """Handle payment gateway integration changes"""
    action = 'CREATED' if created else 'UPDATED'
    
    AuditLog.objects.create(
        user=instance.updated_by,
        action=f'PAYMENT_GATEWAY_INTEGRATION_{action}',
        model_name='PaymentGatewayIntegration',
        object_id=str(instance.id),
        details={
            'branch_integration_id': str(instance.branch_integration_id),
            'currency': instance.currency,
            'accept_upi': instance.accept_upi,
            'auto_refund': instance.auto_refund,
        },
        ip_address=None,
        user_agent=None
    )


@receiver(post_save, sender=IntegrationLog)
def integration_log_created(sender, instance, created, **kwargs):
    """Handle integration log creation"""
    if created:
        # Update related integration's last sync info for certain log types
        if instance.log_type in ['sync', 'api_call'] and instance.status == 'success':
            instance.branch_integration.last_sync = timezone.now()
            instance.branch_integration.sync_status = 'success'
            instance.branch_integration.save()


@receiver(pre_save, sender=PharmacyOrder)
def validate_pharmacy_order(sender, instance, **kwargs):
    """Validate pharmacy order before saving"""
    # Auto-generate order ID if not set
    if not instance.order_id:
        import uuid
        instance.order_id = str(uuid.uuid4())
    
    # Validate status transitions
    if instance.pk:
        old_instance = PharmacyOrder.objects.get(pk=instance.pk)
        
        # Cannot modify cancelled or delivered orders
        if old_instance.status in ['cancelled', 'delivered']:
            raise ValueError(f"Cannot modify order in {old_instance.status} status")
        
        # Validate payment status changes
        if old_instance.payment_status == 'refunded' and instance.payment_status != 'refunded':
            raise ValueError("Cannot change status of refunded order")


@receiver(post_save, sender=PharmacyOrder)
def pharmacy_order_changed(sender, instance, created, **kwargs):
    """Handle pharmacy order changes"""
    action = 'CREATED' if created else 'UPDATED'
    
    # Create audit log
    AuditLog.objects.create(
        user=instance.updated_by,
        action=f'PHARMACY_ORDER_{action}',
        model_name='PharmacyOrder',
        object_id=str(instance.id),
        details={
            'order_id': instance.order_id,
            'external_order_id': instance.external_order_id,
            'prescription_id': str(instance.prescription_id),
            'status': instance.status,
            'payment_status': instance.payment_status,
            'total_amount': float(instance.total),
        },
        ip_address=None,
        user_agent=None
    )
    
    # Trigger webhook if order status changed to delivered
    if not created and 'status' in instance.tracker.changed():
        if instance.status == 'delivered':
            # Trigger webhook to update prescription status
            from .services import PharmacyService
            pharmacy_service = PharmacyService()
            # This would typically be async
            # pharmacy_service.trigger_delivery_webhook(instance)


@receiver(pre_save, sender=PaymentTransaction)
def validate_payment_transaction(sender, instance, **kwargs):
    """Validate payment transaction before saving"""
    # Auto-generate transaction ID if not set
    if not instance.transaction_id:
        import uuid
        instance.transaction_id = str(uuid.uuid4())
    
    # Set initiated_at if not set
    if not instance.initiated_at:
        instance.initiated_at = timezone.now()
    
    # Validate status transitions
    if instance.pk:
        old_instance = PaymentTransaction.objects.get(pk=instance.pk)
        
        # Cannot modify verified transactions
        if old_instance.is_verified and not instance.is_verified:
            raise ValueError("Cannot un-verify a verified transaction")


@receiver(post_save, sender=PaymentTransaction)
def payment_transaction_changed(sender, instance, created, **kwargs):
    """Handle payment transaction changes"""
    action = 'CREATED' if created else 'UPDATED'
    
    # Create audit log
    AuditLog.objects.create(
        user=instance.updated_by,
        action=f'PAYMENT_TRANSACTION_{action}',
        model_name='PaymentTransaction',
        object_id=str(instance.id),
        details={
            'transaction_id': instance.transaction_id,
            'external_transaction_id': instance.external_transaction_id,
            'status': instance.status,
            'amount': float(instance.amount),
            'currency': instance.currency,
            'payment_method': instance.payment_method,
            'invoice_id': str(instance.invoice_id) if instance.invoice else None,
        },
        ip_address=None,
        user_agent=None
    )
    
    # Update invoice payment status
    if instance.invoice and instance.status in ['captured', 'refunded']:
        if instance.status == 'captured':
            instance.invoice.payment_status = 'paid'
        elif instance.status == 'refunded':
            instance.invoice.payment_status = 'refunded'
        instance.invoice.save()


@receiver(post_save, sender=WebhookEvent)
def webhook_event_changed(sender, instance, created, **kwargs):
    """Handle webhook event changes"""
    if created:
        # Log webhook receipt
        AuditLog.objects.create(
            user=None,  # System action
            action='WEBHOOK_RECEIVED',
            model_name='WebhookEvent',
            object_id=str(instance.id),
            details={
                'event_type': instance.event_type,
                'event_id': instance.event_id,
                'branch_integration_id': str(instance.branch_integration_id),
                'processed': instance.processed,
            },
            ip_address=None,
            user_agent=None
        )
        
        # Trigger async processing (would use Celery in production)
        if not instance.processed:
            # In production, this would be a Celery task
            try:
                from .services import PaymentService, PharmacyService
                
                if instance.event_type.startswith('payment_'):
                    payment_service = PaymentService()
                    payment_service.process_webhook_event(instance)
                elif instance.event_type.startswith('order_'):
                    pharmacy_service = PharmacyService()
                    pharmacy_service.process_webhook_event(instance)
                    
                instance.processed = True
                instance.processed_at = timezone.now()
                instance.save()
                
            except Exception as e:
                logger.error(f"Error processing webhook event {instance.id}: {str(e)}")
                instance.processing_error = str(e)
                instance.save()


@receiver(post_delete, sender=IntegrationType)
def integration_type_deleted(sender, instance, **kwargs):
    """Handle integration type deletion"""
    clear_integration_cache(integration_type_id=instance.id)
    
    AuditLog.objects.create(
        user=None,  # System action
        action='INTEGRATION_TYPE_DELETED',
        model_name='IntegrationType',
        object_id=str(instance.id),
        details={
            'name': instance.name,
            'integration_type': instance.integration_type,
        },
        ip_address=None,
        user_agent=None
    )


@receiver(post_delete, sender=IntegrationProvider)
def integration_provider_deleted(sender, instance, **kwargs):
    """Handle integration provider deletion"""
    clear_integration_cache(integration_type_id=instance.integration_type_id)
    
    AuditLog.objects.create(
        user=None,
        action='INTEGRATION_PROVIDER_DELETED',
        model_name='IntegrationProvider',
        object_id=str(instance.id),
        details={
            'name': instance.name,
            'provider_type': instance.provider_type,
            'integration_type': instance.integration_type.name,
        },
        ip_address=None,
        user_agent=None
    )


@receiver(post_delete, sender=BranchIntegration)
def branch_integration_deleted(sender, instance, **kwargs):
    """Handle branch integration deletion"""
    clear_integration_cache(branch_id=instance.branch_id)
    
    AuditLog.objects.create(
        user=None,
        action='BRANCH_INTEGRATION_DELETED',
        model_name='BranchIntegration',
        object_id=str(instance.id),
        details={
            'branch_id': str(instance.branch_id),
            'branch_name': instance.branch.name,
            'provider': instance.provider.name,
            'integration_type': instance.integration_type.name,
        },
        ip_address=None,
        user_agent=None
    )


# Signal for when integration becomes active
@receiver(post_save, sender=BranchIntegration)
def handle_integration_activation(sender, instance, created, **kwargs):
    """Handle when an integration becomes active"""
    if not created and 'status' in instance.tracker.changed():
        if instance.status == 'active':
            logger.info(f"Integration {instance.id} activated for branch {instance.branch.name}")
            
            # Send notification to branch managers
            from apps.notifications.services import NotificationService
            notification_service = NotificationService()
            
            notification_service.send_integration_activated_notification(
                integration=instance,
                branch=instance.branch
            )


# Signal for pharmacy order delivery
@receiver(post_save, sender=PharmacyOrder)
def handle_pharmacy_order_delivery(sender, instance, created, **kwargs):
    """Handle when a pharmacy order is delivered"""
    if not created and 'status' in instance.tracker.changed():
        if instance.status == 'delivered':
            logger.info(f"Pharmacy order {instance.order_id} delivered")
            
            # Update prescription status
            instance.prescription.delivery_status = 'delivered'
            instance.prescription.save()
            
            # Send delivery notification to patient
            from apps.notifications.services import NotificationService
            notification_service = NotificationService()
            
            notification_service.send_order_delivered_notification(
                order=instance,
                patient=instance.prescription.patient
            )

