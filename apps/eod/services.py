# apps/eod/services.py
from django.db import models
from django.utils import timezone
from datetime import datetime, date
from decimal import Decimal

from .models import EodLock, DailySummary, CashReconciliation
from ..billing.models import Invoice
from ..payments.models import Payment, Refund
from ..clinics.models import Branch

from django.db import transaction
from django.core.exceptions import ValidationError
from apps.audit.services import log_action

class EodService:
    """
    End Of Day financial locking service
    """
    @staticmethod
    @transaction.atomic
    def close_day(branch, user, device_id=None, ip_address=None):
        if branch.is_eod_locked:
            raise ValidationError("EOD already closed for this branch")

        # 1️⃣ Lock all open invoices
        invoices = Invoice.objects.select_for_update().filter(
            branch=branch,
            is_locked=False
        )

        for invoice in invoices:
            invoice.is_locked = True
            invoice.save(update_fields=["is_locked"])

            log_action(
                user=user,
                branch=branch,
                instance=invoice,
                action="EOD_LOCK",
                device_id=device_id,
                ip_address=ip_address,
            )

        # 2️⃣ Lock branch
        branch.is_eod_locked = True
        branch.eod_closed_at = timezone.now()
        branch.save(update_fields=["is_eod_locked", "eod_closed_at"])

        log_action(
            user=user,
            branch=branch,
            instance=branch,
            action="EOD_CLOSE",
            device_id=device_id,
            ip_address=ip_address,
        )

        return {
            "locked_invoices": invoices.count(),
            "closed_at": branch.eod_closed_at,
        }
    
    @staticmethod
    def prepare_eod(branch, prepared_by, lock_date=None):
        """
        Prepare a new EOD for a branch
        """
        if lock_date is None:
            lock_date = timezone.now().date()
        
        # Check if EOD already exists for this date
        if EodLock.objects.filter(branch=branch, lock_date=lock_date).exists():
            raise ValueError(f"EOD already exists for {lock_date}")
        
        # Check if previous day is locked (optional business rule)
        previous_day = lock_date - timezone.timedelta(days=1)
        if not EodLock.objects.filter(branch=branch, lock_date=previous_day, status=EodLock.LOCKED).exists():
            # This could be a warning or error depending on business rules
            pass
        
        # Get opening cash from previous day's closing
        opening_cash = EodService.get_opening_cash(branch, lock_date)
        
        # Create EOD
        eod = EodLock.objects.create(
            branch=branch,
            lock_date=lock_date,
            opening_cash=opening_cash,
            prepared_by=prepared_by,
            created_by=prepared_by
        )
        
        # Calculate initial totals
        eod.calculate_totals()
        
        return eod
    
    @staticmethod
    def get_opening_cash(branch, date):
        """
        Get opening cash for a date based on previous day's closing
        """
        previous_day = date - timezone.timedelta(days=1)
        
        try:
            previous_eod = EodLock.objects.get(
                branch=branch,
                lock_date=previous_day,
                status=EodLock.LOCKED
            )
            return previous_eod.actual_cash or previous_eod.expected_cash
        except EodLock.DoesNotExist:
            # If no previous EOD, start with 0 or configurable amount
            return Decimal('0')
    
    @staticmethod
    def verify_and_lock_eod(eod_id, verified_by, actual_cash=None):
        """
        Verify cash and lock the EOD
        """
        try:
            eod = EodLock.objects.get(id=eod_id)
            
            # Verify cash if provided
            if actual_cash is not None:
                eod.verify_cash(actual_cash, verified_by)
            
            # Verify other components
            eod.digital_payments_verified = True
            eod.digital_verified_by = verified_by
            eod.digital_verified_at = timezone.now()
            
            eod.invoices_verified = True
            eod.invoices_verified_by = verified_by
            eod.invoices_verified_at = timezone.now()
            
            # Mark as reviewed if not already
            if eod.status == EodLock.PREPARED:
                eod.status = EodLock.REVIEWED
                eod.reviewed_by = verified_by
                eod.reviewed_at = timezone.now()
            
            eod.save()
            
            # Lock the EOD
            eod.lock(verified_by)
            
            return eod
            
        except EodLock.DoesNotExist:
            raise ValueError(f"EOD with ID {eod_id} not found")
    
    @staticmethod
    def generate_daily_report(branch, report_date=None, report_type='EOD'):
        """
        Generate a comprehensive daily report
        """
        if report_date is None:
            report_date = timezone.now().date()
        
        # Get or create EOD
        eod, created = EodLock.objects.get_or_create(
            branch=branch,
            lock_date=report_date,
            defaults={
                'prepared_by': None,  # Will be set by user
                'opening_cash': EodService.get_opening_cash(branch, report_date)
            }
        )
        
        if created:
            eod.calculate_totals()
        
        # Generate summary
        period_start = datetime.combine(report_date, datetime.min.time())
        period_end = datetime.combine(report_date, datetime.max.time())
        
        summary = DailySummary.generate_summary(
            branch=branch,
            summary_type=report_type,
            period_start=period_start,
            period_end=period_end,
            generated_by=None,  # Will be set by user
            custom_name=f"{report_type} Report for {report_date}"
        )
        
        # Link summary to EOD
        summary.eod_lock = eod
        summary.save()
        
        return {
            'eod': eod,
            'summary': summary,
            'invoices': Invoice.objects.filter(
                branch=branch,
                invoice_date=report_date
            ).count(),
            'payments': Payment.objects.filter(
                branch=branch,
                payment_date__date=report_date,
                status=Payment.COMPLETED
            ).count(),
            'cash_collected': eod.total_cash_collected,
            'digital_collected': eod.card_collections + eod.upi_collections,
        }
    
    @staticmethod
    def check_date_locked(branch, transaction_date):
        """
        Check if a date is locked for a branch
        """
        return EodLock.objects.filter(
            branch=branch,
            lock_date=transaction_date.date(),
            status=EodLock.LOCKED
        ).exists()
    
    @staticmethod
    def get_unlocked_dates(branch):
        """
        Get list of dates that are not locked for a branch
        """
        locked_dates = EodLock.objects.filter(
            branch=branch,
            status=EodLock.LOCKED
        ).values_list('lock_date', flat=True)
        
        # Get all dates with transactions
        invoice_dates = Invoice.objects.filter(
            branch=branch
        ).dates('invoice_date', 'day')
        
        payment_dates = Payment.objects.filter(
            branch=branch
        ).dates('payment_date', 'day')
        
        # Combine and find unique dates
        all_dates = set(invoice_dates) | set(payment_dates)
        
        # Return dates that are not locked
        return [d for d in all_dates if d not in locked_dates]


    @staticmethod
    def validate_transaction_before_posting(branch, transaction_date, transaction_type, amount):
        """
        Validate if transaction can be posted for a given date
        """
        if EodLock.objects.filter(
            branch=branch,
            lock_date=transaction_date.date(),
            status=EodLock.LOCKED
        ).exists():
            raise ValidationError(
                f"Cannot post {transaction_type} for locked date {transaction_date.date()}"
            )
        
        # Check if transaction date is too far in past (configurable)
        max_allowed_days = 30
        if (timezone.now().date() - transaction_date.date()).days > max_allowed_days:
            raise ValidationError(
                f"Cannot post transactions older than {max_allowed_days} days"
            )
        
        return True
    
class CashManagementService:
    """Service class for cash management"""
    
    @staticmethod
    def record_cash_handover(branch, cashier, counter, cash_amount, 
                           reconciliation_type, notes=''):
        """
        Record cash handover between shifts
        """
        reconciliation = CashReconciliation.objects.create(
            branch=branch,
            reconciliation_date=timezone.now().date(),
            reconciliation_type=reconciliation_type,
            cashier=cashier,
            counter=counter,
            declared_cash=cash_amount,
            notes=notes,
            created_by=cashier
        )
        
        return reconciliation
    
    @staticmethod
    def verify_cash_handover(reconciliation_id, supervisor, counted_cash,
                           denomination_breakdown=None, notes=''):
        """
        Verify cash handover
        """
        try:
            reconciliation = CashReconciliation.objects.get(id=reconciliation_id)
            reconciliation.verify(supervisor, counted_cash, notes, denomination_breakdown)
            return reconciliation
        except CashReconciliation.DoesNotExist:
            raise ValueError(f"Reconciliation with ID {reconciliation_id} not found")
    
    @staticmethod
    def get_cash_position(branch, as_of_date=None):
        """
        Get current cash position for a branch
        """
        if as_of_date is None:
            as_of_date = timezone.now().date()
        
        # Get latest EOD
        try:
            latest_eod = EodLock.objects.filter(
                branch=branch,
                lock_date__lte=as_of_date,
                status=EodLock.LOCKED
            ).latest('lock_date')
            
            base_cash = latest_eod.actual_cash or latest_eod.expected_cash
            base_date = latest_eod.lock_date
            
        except EodLock.DoesNotExist:
            base_cash = Decimal('0')
            base_date = None
        
        # Calculate cash movements since base date
        cash_collected = Payment.objects.filter(
            branch=branch,
            payment_date__date__gt=base_date if base_date else date.min,
            payment_date__date__lte=as_of_date,
            payment_method__code='CASH',
            status=Payment.COMPLETED
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        
        cash_refunded = Refund.objects.filter(
            branch=branch,
            requested_at__date__gt=base_date if base_date else date.min,
            requested_at__date__lte=as_of_date,
            refund_method='CASH',
            status=Refund.COMPLETED
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        
        current_cash = base_cash + cash_collected - cash_refunded
        
        return {
            'base_date': base_date,
            'base_cash': base_cash,
            'cash_collected': cash_collected,
            'cash_refunded': cash_refunded,
            'current_cash': current_cash,
            'as_of_date': as_of_date
        }