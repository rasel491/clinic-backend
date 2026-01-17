# apps/eod/utils.py
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import EodLock


class EodValidator:
    """Utility class for EOD validation"""
    
    @staticmethod
    def validate_eod_requirements(branch, lock_date):
        """
        Validate if all requirements are met for EOD locking
        Returns list of validation errors
        """
        errors = []
        
        # Check if date is in the future
        if lock_date > timezone.now().date():
            errors.append("Cannot lock EOD for future date")
        
        # Check if date is already locked
        if EodLock.objects.filter(branch=branch, lock_date=lock_date, status=EodLock.LOCKED).exists():
            errors.append(f"EOD for {lock_date} is already locked")
        
        # Check if previous day is locked (business rule)
        previous_day = lock_date - timedelta(days=1)
        if not EodLock.objects.filter(branch=branch, lock_date=previous_day, status=EodLock.LOCKED).exists():
            errors.append(f"Previous day ({previous_day}) is not locked")
        
        # TODO: Add more business rule validations
        
        return errors
    
    @staticmethod
    def validate_cash_count(expected_cash, actual_cash, tolerance=Decimal('0.50')):
        """
        Validate cash count against expected amount
        """
        difference = actual_cash - expected_cash
        is_valid = abs(difference) <= tolerance
        
        return {
            'is_valid': is_valid,
            'difference': difference,
            'tolerance': tolerance,
            'is_over': difference > tolerance,
            'is_under': difference < -tolerance
        }
    
    @staticmethod
    def get_eod_status_summary(branch):
        """
        Get summary of EOD status for a branch
        """
        today = timezone.now().date()
        
        # Get last 30 days of EOD status
        start_date = today - timedelta(days=30)
        
        eods = EodLock.objects.filter(
            branch=branch,
            lock_date__gte=start_date,
            lock_date__lte=today
        ).order_by('lock_date')
        
        # Create date range
        date_range = []
        current_date = start_date
        while current_date <= today:
            date_range.append(current_date)
            current_date += timedelta(days=1)
        
        # Create status map
        status_map = {}
        for eod in eods:
            status_map[eod.lock_date] = eod.status
        
        summary = []
        for date in date_range:
            status = status_map.get(date, 'UNLOCKED')
            summary.append({
                'date': date,
                'status': status,
                'is_locked': status == EodLock.LOCKED,
                'is_today': date == today
            })
        
        # Calculate statistics
        locked_count = len([s for s in summary if s['is_locked']])
        unlocked_count = len(summary) - locked_count
        
        return {
            'summary': summary,
            'statistics': {
                'total_days': len(summary),
                'locked_days': locked_count,
                'unlocked_days': unlocked_count,
                'lock_percentage': (locked_count / len(summary) * 100) if summary else 0
            },
            'current_status': status_map.get(today, 'UNLOCKED')
        }