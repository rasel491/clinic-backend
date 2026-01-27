# apps/payments/signals.py

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Invoice, InvoiceItem
from django.db import models  
from decimal import Decimal 
from django.db.models import Sum 


@receiver(post_save, sender=Invoice)
def update_invoice_status(sender, instance, created, **kwargs):
    """Update invoice status when saved"""
    if not created:
        instance._update_status()


@receiver(pre_delete, sender=InvoiceItem)
def protect_locked_invoice_item_deletion(sender, instance, **kwargs):
    """Prevent deletion of invoice items from locked invoices"""
    if instance.invoice and instance.invoice.is_locked:
        raise ValueError("Cannot delete item from locked invoice")


@receiver(post_save, sender=InvoiceItem)
def update_invoice_subtotal(sender, instance, created, **kwargs):
    """Update invoice subtotal when item is saved"""
    if instance.invoice:
        instance.invoice.subtotal = instance.invoice.items.aggregate(
            total=models.Sum('total_amount')
        )['total'] or Decimal('0.00')
        instance.invoice.save()