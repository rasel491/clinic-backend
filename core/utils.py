import uuid
from django.utils import timezone
from datetime import datetime, timedelta

def generate_unique_id(prefix='', length=8):
    """Generate unique ID with prefix"""
    uid = str(uuid.uuid4().int)[:length]
    return f"{prefix}{uid}" if prefix else uid

def generate_patient_id():
    """Generate unique patient ID"""
    return generate_unique_id('PAT', 6)

def generate_appointment_id():
    """Generate unique appointment ID"""
    return generate_unique_id('APT', 6)

def generate_invoice_id():
    """Generate unique invoice ID"""
    now = timezone.now()
    return f"INV{now.strftime('%Y%m%d')}{generate_unique_id('', 4)}"

def is_eod_locked(date=None):
    """Check if EOD is locked for a date"""
    from apps.accounts.models import EODLock
    
    if date is None:
        date = timezone.now().date()
    
    try:
        eod_lock = EODLock.objects.get(date=date)
        return eod_lock.is_locked
    except EODLock.DoesNotExist:
        return False

def get_fiscal_year():
    """Get current fiscal year (assuming April-March)"""
    today = timezone.now().date()
    if today.month >= 4:
        return today.year
    else:
        return today.year - 1

def validate_device_limit(user, device_id):
    """Validate device limit for user"""
    from apps.accounts.models import UserDevice
    
    active_devices = UserDevice.objects.filter(
        user=user, 
        is_active=True
    ).exclude(device_id=device_id)
    
    if active_devices.count() >= 3:  # MAX_DEVICES_PER_USER
        # Deactivate oldest device
        oldest_device = active_devices.order_by('last_login').first()
        oldest_device.is_active = False
        oldest_device.save()
    
    return True