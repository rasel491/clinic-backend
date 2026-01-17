# core/constants.py

from django.db import models

class UserRoles:
    """User role constants for RBAC"""
    SUPER_ADMIN = 'super_admin'
    CLINIC_MANAGER = 'clinic_manager'
    DOCTOR = 'doctor'
    RECEPTIONIST = 'receptionist'
    CASHIER = 'cashier'
    LAB_TECHNICIAN = 'lab_technician'
    INVENTORY_MANAGER = 'inventory_manager'
    
    CHOICES = [
        (SUPER_ADMIN, 'Super Administrator'),
        (CLINIC_MANAGER, 'Clinic Manager'),
        (DOCTOR, 'Doctor'),
        (RECEPTIONIST, 'Receptionist'),
        (CASHIER, 'Cashier'),
        (LAB_TECHNICIAN, 'Laboratory Technician'),
        (INVENTORY_MANAGER, 'Inventory Manager'),
    ]

class Gender(models.TextChoices):
    MALE = 'M', 'Male'
    FEMALE = 'F', 'Female'
    OTHER = 'O', 'Other'

class MaritalStatus(models.TextChoices):
    SINGLE = 'S', 'Single'
    MARRIED = 'M', 'Married'
    DIVORCED = 'D', 'Divorced'
    WIDOWED = 'W', 'Widowed'

class AppointmentStatus(models.TextChoices):
    SCHEDULED = 'scheduled', 'Scheduled'
    CONFIRMED = 'confirmed', 'Confirmed'
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'
    NO_SHOW = 'no_show', 'No Show'

class PaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PARTIAL = 'partial', 'Partial'
    PAID = 'paid', 'Paid'
    CANCELLED = 'cancelled', 'Cancelled'
    REFUNDED = 'refunded', 'Refunded'

class PaymentModes(models.TextChoices):
    CASH = 'cash', 'Cash'
    CARD = 'card', 'Card'
    UPI = 'upi', 'UPI'
    CHEQUE = 'cheque', 'Cheque'
    INSURANCE = 'insurance', 'Insurance'
    ONLINE = 'online', 'Online'

class VisitStatus(models.TextChoices):
    REGISTERED = 'registered', 'Registered'
    IN_CONSULTATION = 'in_consultation', 'In Consultation'
    READY_FOR_BILLING = 'ready_for_billing', 'Ready for Billing'
    PARTIALLY_PAID = 'partially_paid', 'Partially Paid'
    PAID = 'paid', 'Paid'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'
    
class AuditActions:
    """Audit log action types"""
    CREATE = 'create'
    UPDATE = 'update'
    DELETE = 'delete'
    LOGIN = 'login'
    LOGOUT = 'logout'
    VIEW = 'view'
    EXPORT = 'export'
    IMPORT = 'import'
    APPROVE = 'approve'
    REJECT = 'reject'
    
    CHOICES = [
        (CREATE, 'Create'),
        (UPDATE, 'Update'),
        (DELETE, 'Delete'),
        (LOGIN, 'Login'),
        (LOGOUT, 'Logout'),
        (VIEW, 'View'),
        (EXPORT, 'Export'),
        (IMPORT, 'Import'),
        (APPROVE, 'Approve'),
        (REJECT, 'Reject'),
    ]

