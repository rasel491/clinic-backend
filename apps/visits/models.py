# apps/visits/models.py

from django.db import models
from django.utils import timezone
from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin
from core.constants import VisitStatus

class Visit(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """Patient visit to clinic"""
    
    APPOINTMENT_SOURCE = [
        ('WALK_IN', 'Walk-in'),
        ('ONLINE', 'Online Booking'),
        ('PHONE', 'Phone Call'),
        ('REFERRAL', 'Doctor Referral'),
        ('FOLLOW_UP', 'Follow-up'),
    ]
    
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.PROTECT,
        related_name='visits'
    )
    doctor = models.ForeignKey(
        'doctors.Doctor',
        on_delete=models.PROTECT,
        related_name='visits',
        null=True,
        blank=True
    )
    branch = models.ForeignKey(
        'clinics.Branch',
        on_delete=models.PROTECT,
        related_name='visits'
    )
    
    # Visit info
    visit_id = models.CharField(max_length=50, unique=True, blank=True)
    status = models.CharField(
        max_length=50,
        choices=VisitStatus.choices,
        default=VisitStatus.REGISTERED
    )
    appointment_source = models.CharField(max_length=20, choices=APPOINTMENT_SOURCE, default='WALK_IN')
    
    # Timing
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    actual_checkin = models.DateTimeField(null=True, blank=True)
    actual_checkout = models.DateTimeField(null=True, blank=True)
    wait_duration = models.DurationField(null=True, blank=True, help_text="Waiting time before consultation")
    consultation_duration = models.DurationField(null=True, blank=True, help_text="Actual consultation time")
    
    # Reason
    chief_complaint = models.TextField(blank=True)
    symptoms = models.TextField(blank=True)
    
    # Follow-up
    is_follow_up = models.BooleanField(default=False)
    follow_up_of = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='follow_ups'
    )
    next_follow_up_date = models.DateField(null=True, blank=True)
    
    # Billing link
    # linked_invoice = models.OneToOneField(
    #     'billing.Invoice',
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='linked_visit'
    # )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'visits'
        ordering = ['-scheduled_date', '-scheduled_time']
        indexes = [
            models.Index(fields=['visit_id']),
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['doctor', 'status', 'scheduled_date']),
            models.Index(fields=['branch', 'status', 'scheduled_date']),
            models.Index(fields=['status', 'scheduled_date']),
        ]
    
    def __str__(self):
        return f"Visit {self.visit_id}: {self.patient} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        if not self.visit_id:
            self.visit_id = self._generate_visit_id()
        super().save(*args, **kwargs)
    
    @property
    def has_invoice(self):
        """Check if visit has an invoice"""
        return bool(self.linked_invoice)  # Changed from self.invoice

    def get_invoice(self):
        """Get associated invoice"""
        return self.linked_invoice  # Changed from self.invoice
    
    def _generate_visit_id(self):
        """Generate V-YYYYMMDD-XXXX format ID"""
        from datetime import datetime
        from django.db.models import Count
        
        date_str = self.scheduled_date.strftime('%Y%m%d')
        
        last_visit = Visit.objects.filter(
            visit_id__startswith=f'V-{date_str}-'
        ).order_by('visit_id').last()
        
        if last_visit:
            last_num = int(last_visit.visit_id.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f'V-{date_str}-{new_num:04d}'
    
    @property
    def total_duration(self):
        """Total time spent at clinic"""
        if self.actual_checkin and self.actual_checkout:
            return self.actual_checkout - self.actual_checkin
        return None
    
    @property
    def is_active(self):
        """Check if visit is currently active"""
        active_statuses = [VisitStatus.REGISTERED, VisitStatus.IN_CONSULTATION]
        return self.status in active_statuses
    
    @property
    def can_checkout(self):
        """Check if visit can be checked out"""
        return self.status in [VisitStatus.IN_CONSULTATION, VisitStatus.READY_FOR_BILLING]
    
    def mark_checked_in(self):
        """Mark patient as checked in"""
        if self.status == VisitStatus.REGISTERED:
            self.actual_checkin = timezone.now()
            self.status = VisitStatus.IN_CONSULTATION
            self.save()
    
    def mark_consultation_complete(self):
        """Mark consultation as complete"""
        if self.status == VisitStatus.IN_CONSULTATION:
            self.actual_checkout = timezone.now()
            self.status = VisitStatus.READY_FOR_BILLING
            self.save()
    
    def mark_completed(self):
        """Mark visit as completed (after payment)"""
        if self.status == VisitStatus.PAID:
            self.status = VisitStatus.COMPLETED
            self.save()


class Appointment(models.Model):
    """Future scheduled appointments"""
    
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('CONFIRMED', 'Confirmed'),
        ('CHECKED_IN', 'Checked In'),
        ('NO_SHOW', 'No Show'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    ]
    
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='appointments'
    )
    doctor = models.ForeignKey(
        'doctors.Doctor',
        on_delete=models.CASCADE,
        related_name='appointments'
    )
    branch = models.ForeignKey(
        'clinics.Branch',
        on_delete=models.CASCADE,
        related_name='appointments'
    )
    
    # Appointment details
    appointment_id = models.CharField(max_length=50, unique=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    
    # Timing
    appointment_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration = models.PositiveIntegerField(default=30, help_text="Duration in minutes")
    
    # Purpose
    purpose = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    
    # Reminders
    reminder_sent = models.BooleanField(default=False)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Cancellation
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    
    # Link to actual visit
    visit = models.OneToOneField(
        Visit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointment'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'appointments'
        ordering = ['appointment_date', 'start_time']
        indexes = [
            models.Index(fields=['appointment_id']),
            models.Index(fields=['patient', 'appointment_date']),
            models.Index(fields=['doctor', 'appointment_date', 'status']),
            models.Index(fields=['branch', 'appointment_date']),
            models.Index(fields=['status', 'appointment_date']),
        ]
    
    def __str__(self):
        return f"Appt {self.appointment_id}: {self.patient} with {self.doctor}"
    
    def save(self, *args, **kwargs):
        if not self.appointment_id:
            self.appointment_id = self._generate_appointment_id()
        
        # Auto-calculate end time if not set
        if not self.end_time and self.start_time and self.duration:
            from datetime import datetime, timedelta
            start_dt = datetime.combine(self.appointment_date, self.start_time)
            end_dt = start_dt + timedelta(minutes=self.duration)
            self.end_time = end_dt.time()
        
        super().save(*args, **kwargs)
    
    def _generate_appointment_id(self):
        """Generate APPT-YYYYMMDD-XXXX format ID"""
        from datetime import datetime
        from django.db.models import Count
        
        date_str = self.appointment_date.strftime('%Y%m%d')
        
        last_appt = Appointment.objects.filter(
            appointment_id__startswith=f'APPT-{date_str}-'
        ).order_by('appointment_id').last()
        
        if last_appt:
            last_num = int(last_appt.appointment_id.split('-')[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f'APPT-{date_str}-{new_num:04d}'
    
    @property
    def is_upcoming(self):
        """Check if appointment is in the future"""
        from django.utils import timezone
        today = timezone.now().date()
        return self.appointment_date >= today and self.status in ['SCHEDULED', 'CONFIRMED']
    
    @property
    def is_today(self):
        """Check if appointment is today"""
        from django.utils import timezone
        today = timezone.now().date()
        return self.appointment_date == today
    
    def convert_to_visit(self):
        """Convert appointment to actual visit"""
        if not self.visit:
            from django.utils import timezone
            visit = Visit.objects.create(
                patient=self.patient,
                doctor=self.doctor,
                branch=self.branch,
                scheduled_date=self.appointment_date,
                scheduled_time=self.start_time,
                appointment_source='ONLINE' if self.purpose else 'PHONE',
                chief_complaint=self.purpose
            )
            self.visit = visit
            self.status = 'CHECKED_IN'
            self.save()
            return visit
        return self.visit