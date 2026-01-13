# core/constants.py
from django.db import models

class VisitStatus(models.TextChoices):
    REGISTERED = 'registered', 'Registered'
    IN_CONSULTATION = 'in_consultation', 'In Consultation'
    READY_FOR_BILLING = 'ready_for_billing', 'Ready for Billing'
    PARTIALLY_PAID = 'partially_paid', 'Partially Paid'
    PAID = 'paid', 'Paid'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'

class UserRoles(models.TextChoices):
    PATIENT = 'patient', 'Patient'
    FRONT_DESK = 'front_desk', 'Front Desk'
    DOCTOR = 'doctor', 'Doctor'
    CASHIER = 'cashier', 'Cashier'
    MANAGER = 'manager', 'Manager'
    ADMIN = 'admin', 'Admin'

class PaymentModes(models.TextChoices):
    CASH = 'cash', 'Cash'
    CARD = 'card', 'Card'
    UPI = 'upi', 'UPI'
    CHEQUE = 'cheque', 'Cheque'
    INSURANCE = 'insurance', 'Insurance'
    ONLINE = 'online', 'Online'