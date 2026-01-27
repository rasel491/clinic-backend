from django.db import models
from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
from decimal import Decimal

from .models import Payment, Refund, PaymentReceipt
from apps.billing.models import Invoice


@receiver(pre_save, sender=Payment)
def validate_payment_amount(sender, instance, **kwargs):
    """Validate payment amount before saving"""
    if instance.pk:  # Only for existing instances
        original = Payment.objects.get(pk=instance.pk)
        
        # Check if amount changed for completed payments
        if original.status == Payment.COMPLETED and instance.amount != original.amount:
            raise ValueError("Cannot change amount of completed payment")
        
        # Check if payment is locked
        if original.is_locked and instance.status != original.status:
            raise ValueError("Cannot modify locked payment")


@receiver(post_save, sender=Payment)
def update_invoice_on_payment(sender, instance, created, **kwargs):
    """Update invoice when payment is completed"""
    if instance.status == Payment.COMPLETED:
        with transaction.atomic():
            # Recalculate invoice paid amount
            total_paid = Payment.objects.filter(
                invoice=instance.invoice,
                status=Payment.COMPLETED
            ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
            
            instance.invoice.paid_amount = total_paid
            instance.invoice.save()


@receiver(post_save, sender=Refund)
def update_payment_on_refund(sender, instance, created, **kwargs):
    """Update payment status when refund is completed"""
    if instance.status == Refund.COMPLETED:
        with transaction.atomic():
            # Recalculate total refunded for the payment
            total_refunded = Refund.objects.filter(
                payment=instance.payment,
                status__in=[Refund.APPROVED, Refund.COMPLETED]
            ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
            
            # Update payment status
            if total_refunded >= instance.payment.amount:
                instance.payment.status = Payment.REFUNDED
            elif total_refunded > 0:
                instance.payment.status = Payment.PARTIALLY_REFUNDED
            else:
                instance.payment.status = Payment.COMPLETED
            
            instance.payment.save()
            
            # Update invoice
            update_invoice_on_payment(sender, instance.payment, False, **kwargs)


@receiver(pre_delete, sender=Payment)
def prevent_payment_deletion(sender, instance, **kwargs):
    """Prevent deletion of payments under certain conditions"""
    if instance.is_locked:
        raise ValueError("Cannot delete locked payment")
    
    if instance.status == Payment.COMPLETED:
        raise ValueError("Cannot delete completed payment")
    
    # Check if payment has any refunds
    if instance.refunds.exists():
        raise ValueError("Cannot delete payment with refunds")


@receiver(pre_delete, sender=Refund)
def prevent_refund_deletion(sender, instance, **kwargs):
    """Prevent deletion of refunds under certain conditions"""
    if instance.is_locked:
        raise ValueError("Cannot delete locked refund")
    
    if instance.status in [Refund.COMPLETED, Refund.APPROVED]:
        raise ValueError(f"Cannot delete {instance.get_status_display()} refund")


@receiver(post_save, sender=PaymentReceipt)
def update_payment_receipt_status(sender, instance, created, **kwargs):
    """Update payment receipt_generated status"""
    if created and not instance.is_duplicate:
        instance.payment.receipt_generated = True
        instance.payment.receipt_number = instance.receipt_number
        instance.payment.save()


@receiver(pre_save, sender=Payment)
def auto_approve_small_payments(sender, instance, **kwargs):
    """Auto-approve small payments"""
    if instance.status == Payment.PENDING and not instance.requires_approval:
        # Auto-approve small payments
        if instance.amount <= Decimal('1000'):
            instance.status = Payment.COMPLETED
            instance.completed_at = timezone.now()


# Connect all signals
def ready():
    """Connect all signals when app is ready"""
    pass