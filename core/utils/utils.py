# core/utils.py
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





# # New full code utils

# # core/utils.py
# import uuid
# import random
# import string
# from django.utils import timezone
# from datetime import datetime, timedelta, date
# from django.core.exceptions import ValidationError
# from django.db import transaction
# import hashlib
# import json
# from decimal import Decimal
# import re


# # ===========================================
# # ID GENERATION
# # ===========================================
# def generate_unique_id(prefix='', length=8):
#     """Generate unique ID with prefix"""
#     uid = str(uuid.uuid4().int)[:length]
#     return f"{prefix}{uid}" if prefix else uid

# def generate_patient_id():
#     """Generate unique patient ID"""
#     return generate_unique_id('PAT', 6)

# def generate_appointment_id():
#     """Generate unique appointment ID"""
#     return generate_unique_id('APT', 6)

# def generate_invoice_id():
#     """Generate unique invoice ID"""
#     now = timezone.now()
#     return f"INV{now.strftime('%Y%m%d')}{generate_unique_id('', 4)}"

# def generate_visit_id():
#     """Generate unique visit ID"""
#     now = timezone.now()
#     return f"V-{now.strftime('%Y%m%d')}-{generate_unique_id('', 4)}"

# def generate_prescription_id():
#     """Generate unique prescription ID"""
#     now = timezone.now()
#     return f"RX-{now.strftime('%Y%m%d')}-{generate_unique_id('', 4)}"

# def generate_queue_number(branch, date=None):
#     """Generate queue number for a branch"""
#     from apps.visits.models import Queue
    
#     if date is None:
#         date = timezone.now().date()
    
#     last_queue = Queue.objects.filter(
#         branch=branch,
#         joined_at__date=date
#     ).order_by('-queue_number').first()
    
#     return (last_queue.queue_number + 1) if last_queue else 1


# # ===========================================
# # DATE & TIME UTILITIES
# # ===========================================
# def is_eod_locked(date=None):
#     """Check if EOD is locked for a date"""
#     from apps.accounts.models import EODLock
    
#     if date is None:
#         date = timezone.now().date()
    
#     try:
#         eod_lock = EODLock.objects.get(date=date)
#         return eod_lock.is_locked
#     except EODLock.DoesNotExist:
#         return False

# def get_fiscal_year():
#     """Get current fiscal year (assuming April-March)"""
#     today = timezone.now().date()
#     if today.month >= 4:
#         return today.year
#     else:
#         return today.year - 1

# def get_week_range(date_obj=None):
#     """Get start and end of week for a date"""
#     if date_obj is None:
#         date_obj = timezone.now().date()
    
#     start = date_obj - timedelta(days=date_obj.weekday())
#     end = start + timedelta(days=6)
#     return start, end

# def get_month_range(date_obj=None):
#     """Get start and end of month for a date"""
#     if date_obj is None:
#         date_obj = timezone.now().date()
    
#     start = date_obj.replace(day=1)
#     if date_obj.month == 12:
#         end = date_obj.replace(year=date_obj.year + 1, month=1, day=1) - timedelta(days=1)
#     else:
#         end = date_obj.replace(month=date_obj.month + 1, day=1) - timedelta(days=1)
    
#     return start, end

# def get_quarter_range(date_obj=None):
#     """Get start and end of quarter for a date"""
#     if date_obj is None:
#         date_obj = timezone.now().date()
    
#     quarter = (date_obj.month - 1) // 3 + 1
#     start_month = (quarter - 1) * 3 + 1
#     end_month = start_month + 2
    
#     start = date_obj.replace(month=start_month, day=1)
#     if end_month == 12:
#         end = date_obj.replace(year=date_obj.year + 1, month=1, day=1) - timedelta(days=1)
#     else:
#         end = date_obj.replace(month=end_month + 1, day=1) - timedelta(days=1)
    
#     return start, end

# def format_duration(duration):
#     """Format duration to human readable string"""
#     if not duration:
#         return "0 minutes"
    
#     total_seconds = int(duration.total_seconds())
#     hours = total_seconds // 3600
#     minutes = (total_seconds % 3600) // 60
    
#     if hours > 0:
#         return f"{hours} hour{'s' if hours > 1 else ''} {minutes} minute{'s' if minutes > 1 else ''}"
#     else:
#         return f"{minutes} minute{'s' if minutes > 1 else ''}"


# # ===========================================
# # VALIDATION UTILITIES
# # ===========================================
# def validate_device_limit(user, device_id):
#     """Validate device limit for user"""
#     from apps.accounts.models import UserDevice
    
#     active_devices = UserDevice.objects.filter(
#         user=user, 
#         is_active=True
#     ).exclude(device_id=device_id)
    
#     if active_devices.count() >= 3:  # MAX_DEVICES_PER_USER
#         # Deactivate oldest device
#         oldest_device = active_devices.order_by('last_login').first()
#         oldest_device.is_active = False
#         oldest_device.save()
    
#     return True

# def validate_phone_number(phone):
#     """Validate phone number format"""
#     # Remove all non-digit characters
#     phone = re.sub(r'\D', '', phone)
    
#     # Basic validation - adjust based on your country
#     if len(phone) < 10 or len(phone) > 15:
#         return False
    
#     return True

# def validate_email(email):
#     """Validate email format"""
#     pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
#     return re.match(pattern, email) is not None

# def validate_aadhaar_number(aadhaar):
#     """Validate Aadhaar number (Indian ID)"""
#     # Remove whitespace
#     aadhaar = re.sub(r'\s', '', aadhaar)
    
#     # Should be 12 digits
#     if not re.match(r'^\d{12}$', aadhaar):
#         return False
    
#     # Verhoeff algorithm validation (optional)
#     return True

# def validate_pan_number(pan):
#     """Validate PAN number (Indian Tax ID)"""
#     pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
#     return re.match(pattern, pan) is not None


# # ===========================================
# # FINANCIAL UTILITIES
# # ===========================================
# def calculate_gst(amount, gst_rate=18):
#     """Calculate GST amount"""
#     gst_amount = (amount * Decimal(gst_rate)) / Decimal(100)
#     return gst_amount.quantize(Decimal('0.01'))

# def calculate_discount(amount, discount_percent):
#     """Calculate discount amount"""
#     discount = (amount * Decimal(discount_percent)) / Decimal(100)
#     return discount.quantize(Decimal('0.01'))

# def calculate_total_with_tax(amount, gst_rate=18):
#     """Calculate total amount with GST"""
#     gst_amount = calculate_gst(amount, gst_rate)
#     total = amount + gst_amount
#     return total.quantize(Decimal('0.01'))

# def format_currency(amount):
#     """Format amount as currency"""
#     return f"₹{amount:,.2f}"

# def generate_payment_reference():
#     """Generate payment reference ID"""
#     timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
#     random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
#     return f"PAY-{timestamp}-{random_str}"


# # ===========================================
# # DATA TRANSFORMATION
# # ===========================================
# def dict_to_choices(data_dict):
#     """Convert dictionary to Django choices tuple"""
#     return [(key, value) for key, value in data_dict.items()]

# def queryset_to_list(queryset, fields=None):
#     """Convert queryset to list of dictionaries"""
#     if fields is None:
#         fields = [field.name for field in queryset.model._meta.fields]
    
#     result = []
#     for obj in queryset:
#         item = {}
#         for field in fields:
#             value = getattr(obj, field)
            
#             # Handle callables
#             if callable(value):
#                 value = value()
            
#             # Handle dates
#             if isinstance(value, (datetime, date)):
#                 value = value.isoformat()
            
#             # Handle Decimal
#             if isinstance(value, Decimal):
#                 value = float(value)
            
#             item[field] = value
        
#         result.append(item)
    
#     return result

# def safe_json_parse(json_string, default=None):
#     """Safely parse JSON string"""
#     if default is None:
#         default = {}
    
#     try:
#         return json.loads(json_string)
#     except (json.JSONDecodeError, TypeError):
#         return default

# def mask_sensitive_data(text, visible_chars=4):
#     """Mask sensitive data like phone numbers, emails"""
#     if not text:
#         return text
    
#     if '@' in text:  # Email
#         parts = text.split('@')
#         username = parts[0]
#         domain = parts[1]
        
#         if len(username) <= visible_chars:
#             masked_username = '*' * len(username)
#         else:
#             masked_username = username[:visible_chars] + '*' * (len(username) - visible_chars)
        
#         return f"{masked_username}@{domain}"
    
#     elif text.replace(' ', '').isdigit():  # Phone number
#         text = text.replace(' ', '')
#         if len(text) <= visible_chars:
#             return '*' * len(text)
#         else:
#             return text[:visible_chars] + '*' * (len(text) - visible_chars)
    
#     return text


# # ===========================================
# # SECURITY & HASHING
# # ===========================================
# def generate_secure_token(length=32):
#     """Generate secure random token"""
#     return ''.join(random.choices(
#         string.ascii_letters + string.digits, 
#         k=length
#     ))

# def hash_sensitive_data(data):
#     """Hash sensitive data for storage"""
#     if not data:
#         return None
    
#     return hashlib.sha256(data.encode()).hexdigest()

# def generate_otp(length=6):
#     """Generate OTP"""
#     return ''.join(random.choices(string.digits, k=length))

# def generate_password(length=12):
#     """Generate strong password"""
#     chars = string.ascii_letters + string.digits + '!@#$%^&*'
#     password = ''.join(random.choices(chars, k=length))
    
#     # Ensure at least one of each type
#     if not any(c.isupper() for c in password):
#         password = password[:-1] + random.choice(string.ascii_uppercase)
#     if not any(c.islower() for c in password):
#         password = password[:-1] + random.choice(string.ascii_lowercase)
#     if not any(c.isdigit() for c in password):
#         password = password[:-1] + random.choice(string.digits)
#     if not any(c in '!@#$%^&*' for c in password):
#         password = password[:-1] + random.choice('!@#$%^&*')
    
#     return password


# # ===========================================
# # BUSINESS LOGIC UTILITIES
# # ===========================================
# def calculate_age(birth_date):
#     """Calculate age from birth date"""
#     if not birth_date:
#         return None
    
#     today = timezone.now().date()
#     age = today.year - birth_date.year
    
#     # Adjust if birthday hasn't occurred this year
#     if (today.month, today.day) < (birth_date.month, birth_date.day):
#         age -= 1
    
#     return age

# def calculate_bmi(weight_kg, height_cm):
#     """Calculate BMI"""
#     if not weight_kg or not height_cm:
#         return None
    
#     height_m = height_cm / 100
#     bmi = weight_kg / (height_m ** 2)
#     return round(bmi, 2)

# def get_bmi_category(bmi):
#     """Get BMI category"""
#     if bmi is None:
#         return "Unknown"
    
#     if bmi < 18.5:
#         return "Underweight"
#     elif bmi < 25:
#         return "Normal"
#     elif bmi < 30:
#         return "Overweight"
#     else:
#         return "Obese"

# def calculate_blood_pressure_category(systolic, diastolic):
#     """Categorize blood pressure"""
#     if not systolic or not diastolic:
#         return "Unknown"
    
#     if systolic < 90 or diastolic < 60:
#         return "Low"
#     elif systolic < 120 and diastolic < 80:
#         return "Normal"
#     elif systolic < 130 and diastolic < 80:
#         return "Elevated"
#     elif systolic < 140 or diastolic < 90:
#         return "Hypertension Stage 1"
#     elif systolic < 180 or diastolic < 120:
#         return "Hypertension Stage 2"
#     else:
#         return "Hypertensive Crisis"

# def generate_next_follow_up_date(base_date, days=30):
#     """Generate next follow-up date"""
#     if not base_date:
#         return None
    
#     return base_date + timedelta(days=days)


# # ===========================================
# # FILE & MEDIA UTILITIES
# # ===========================================
# def generate_filename(instance, filename):
#     """Generate unique filename for file uploads"""
#     ext = filename.split('.')[-1]
#     timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
#     unique_id = generate_unique_id('', 8)
    
#     model_name = instance.__class__.__name__.lower()
#     return f'{model_name}/{timestamp}_{unique_id}.{ext}'

# def get_file_size(file_path):
#     """Get human-readable file size"""
#     import os
    
#     if not os.path.exists(file_path):
#         return "0 bytes"
    
#     size = os.path.getsize(file_path)
    
#     for unit in ['bytes', 'KB', 'MB', 'GB']:
#         if size < 1024.0:
#             return f"{size:.1f} {unit}"
#         size /= 1024.0
    
#     return f"{size:.1f} TB"


# # ===========================================
# # ERROR HANDLING
# # ===========================================
# class ValidationErrorWithCode(ValidationError):
#     """Validation error with error code"""
#     def __init__(self, message, code=None, params=None):
#         super().__init__(message, code, params)
#         self.code = code

# def handle_exception_as_response(exception):
#     """Convert exception to API response format"""
#     if isinstance(exception, ValidationError):
#         if hasattr(exception, 'code'):
#             return {
#                 'error': str(exception),
#                 'code': exception.code,
#                 'type': 'validation_error'
#             }
#         return {
#             'error': str(exception),
#             'type': 'validation_error'
#         }
#     else:
#         return {
#             'error': str(exception),
#             'type': 'server_error'
#         }


# # ===========================================
# # DECORATORS
# # ===========================================
# def atomic_transaction(func):
#     """Decorator to wrap function in atomic transaction"""
#     def wrapper(*args, **kwargs):
#         with transaction.atomic():
#             return func(*args, **kwargs)
#     return wrapper

# def log_execution_time(func):
#     """Decorator to log function execution time"""
#     import time
#     import logging
    
#     logger = logging.getLogger(__name__)
    
#     def wrapper(*args, **kwargs):
#         start_time = time.time()
#         result = func(*args, **kwargs)
#         end_time = time.time()
        
#         logger.debug(f"{func.__name__} executed in {end_time - start_time:.4f} seconds")
#         return result
#     return wrapper


# # ===========================================
# # EXPORT FOR VISITS APP
# # ===========================================
# # These functions are imported by visits app
# def export_visits_to_excel(visits_queryset, filename=None):
#     """Export visits to Excel - wrapper for visits app"""
#     from core.utils.excel_export import export_to_excel
    
#     if filename is None:
#         timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
#         filename = f'visits_export_{timestamp}.xlsx'
    
#     return export_to_excel(visits_queryset, filename, 'Visits')

# def export_appointments_to_excel(appointments_queryset, filename=None):
#     """Export appointments to Excel - wrapper for visits app"""
#     from core.utils.excel_export import export_to_excel
    
#     if filename is None:
#         timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
#         filename = f'appointments_export_{timestamp}.xlsx'
    
#     return export_to_excel(appointments_queryset, filename, 'Appointments')