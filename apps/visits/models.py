# # apps/visits/models.py

# from django.db import models
# from django.utils import timezone
# from core.mixins.audit_fields import AuditFieldsMixin
# from core.mixins.soft_delete import SoftDeleteMixin
# from core.constants import VisitStatus

# class Visit(AuditFieldsMixin, SoftDeleteMixin, models.Model):
#     """Patient visit to clinic"""
    
#     APPOINTMENT_SOURCE = [
#         ('WALK_IN', 'Walk-in'),
#         ('ONLINE', 'Online Booking'),
#         ('PHONE', 'Phone Call'),
#         ('REFERRAL', 'Doctor Referral'),
#         ('FOLLOW_UP', 'Follow-up'),
#     ]
    
#     patient = models.ForeignKey(
#         'patients.Patient',
#         on_delete=models.PROTECT,
#         related_name='visits'
#     )
#     doctor = models.ForeignKey(
#         'doctors.Doctor',
#         on_delete=models.PROTECT,
#         related_name='visits',
#         null=True,
#         blank=True
#     )
#     branch = models.ForeignKey(
#         'clinics.Branch',
#         on_delete=models.PROTECT,
#         related_name='visits'
#     )
    
#     # Visit info
#     visit_id = models.CharField(max_length=50, unique=True, blank=True)
#     status = models.CharField(
#         max_length=50,
#         choices=VisitStatus.choices,
#         default=VisitStatus.REGISTERED
#     )
#     appointment_source = models.CharField(max_length=20, choices=APPOINTMENT_SOURCE, default='WALK_IN')
    
#     # Timing
#     scheduled_date = models.DateField()
#     scheduled_time = models.TimeField()
#     actual_checkin = models.DateTimeField(null=True, blank=True)
#     actual_checkout = models.DateTimeField(null=True, blank=True)
#     wait_duration = models.DurationField(null=True, blank=True, help_text="Waiting time before consultation")
#     consultation_duration = models.DurationField(null=True, blank=True, help_text="Actual consultation time")
    
#     # Reason
#     chief_complaint = models.TextField(blank=True)
#     symptoms = models.TextField(blank=True)
    
#     # Follow-up
#     is_follow_up = models.BooleanField(default=False)
#     follow_up_of = models.ForeignKey(
#         'self',
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='follow_ups'
#     )
#     next_follow_up_date = models.DateField(null=True, blank=True)
    
#     # Billing link
#     # linked_invoice = models.OneToOneField(
#     #     'billing.Invoice',
#     #     on_delete=models.SET_NULL,
#     #     null=True,
#     #     blank=True,
#     #     related_name='linked_visit'
#     # )
    
#     # Metadata
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'visits'
#         ordering = ['-scheduled_date', '-scheduled_time']
#         indexes = [
#             models.Index(fields=['visit_id']),
#             models.Index(fields=['patient', 'status']),
#             models.Index(fields=['doctor', 'status', 'scheduled_date']),
#             models.Index(fields=['branch', 'status', 'scheduled_date']),
#             models.Index(fields=['status', 'scheduled_date']),
#         ]
    
#     def __str__(self):
#         return f"Visit {self.visit_id}: {self.patient} ({self.get_status_display()})"
    
#     def save(self, *args, **kwargs):
#         if not self.visit_id:
#             self.visit_id = self._generate_visit_id()
#         super().save(*args, **kwargs)
    
#     @property
#     def has_invoice(self):
#         """Check if visit has an invoice"""
#         return bool(self.linked_invoice)  # Changed from self.invoice

#     def get_invoice(self):
#         """Get associated invoice"""
#         return self.linked_invoice  # Changed from self.invoice
    
#     def _generate_visit_id(self):
#         """Generate V-YYYYMMDD-XXXX format ID"""
#         from datetime import datetime
#         from django.db.models import Count
        
#         date_str = self.scheduled_date.strftime('%Y%m%d')
        
#         last_visit = Visit.objects.filter(
#             visit_id__startswith=f'V-{date_str}-'
#         ).order_by('visit_id').last()
        
#         if last_visit:
#             last_num = int(last_visit.visit_id.split('-')[-1])
#             new_num = last_num + 1
#         else:
#             new_num = 1
        
#         return f'V-{date_str}-{new_num:04d}'
    
#     @property
#     def total_duration(self):
#         """Total time spent at clinic"""
#         if self.actual_checkin and self.actual_checkout:
#             return self.actual_checkout - self.actual_checkin
#         return None
    
#     @property
#     def is_active(self):
#         """Check if visit is currently active"""
#         active_statuses = [VisitStatus.REGISTERED, VisitStatus.IN_CONSULTATION]
#         return self.status in active_statuses
    
#     @property
#     def can_checkout(self):
#         """Check if visit can be checked out"""
#         return self.status in [VisitStatus.IN_CONSULTATION, VisitStatus.READY_FOR_BILLING]
    
#     def mark_checked_in(self):
#         """Mark patient as checked in"""
#         if self.status == VisitStatus.REGISTERED:
#             self.actual_checkin = timezone.now()
#             self.status = VisitStatus.IN_CONSULTATION
#             self.save()
    
#     def mark_consultation_complete(self):
#         """Mark consultation as complete"""
#         if self.status == VisitStatus.IN_CONSULTATION:
#             self.actual_checkout = timezone.now()
#             self.status = VisitStatus.READY_FOR_BILLING
#             self.save()
    
#     def mark_completed(self):
#         """Mark visit as completed (after payment)"""
#         if self.status == VisitStatus.PAID:
#             self.status = VisitStatus.COMPLETED
#             self.save()


# class Appointment(models.Model):
#     """Future scheduled appointments"""
    
#     STATUS_CHOICES = [
#         ('SCHEDULED', 'Scheduled'),
#         ('CONFIRMED', 'Confirmed'),
#         ('CHECKED_IN', 'Checked In'),
#         ('NO_SHOW', 'No Show'),
#         ('CANCELLED', 'Cancelled'),
#         ('COMPLETED', 'Completed'),
#     ]
    
#     patient = models.ForeignKey(
#         'patients.Patient',
#         on_delete=models.CASCADE,
#         related_name='appointments'
#     )
#     doctor = models.ForeignKey(
#         'doctors.Doctor',
#         on_delete=models.CASCADE,
#         related_name='appointments'
#     )
#     branch = models.ForeignKey(
#         'clinics.Branch',
#         on_delete=models.CASCADE,
#         related_name='appointments'
#     )
    
#     # Appointment details
#     appointment_id = models.CharField(max_length=50, unique=True, blank=True)
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    
#     # Timing
#     appointment_date = models.DateField()
#     start_time = models.TimeField()
#     end_time = models.TimeField()
#     duration = models.PositiveIntegerField(default=30, help_text="Duration in minutes")
    
#     # Purpose
#     purpose = models.CharField(max_length=200, blank=True)
#     notes = models.TextField(blank=True)
    
#     # Reminders
#     reminder_sent = models.BooleanField(default=False)
#     reminder_sent_at = models.DateTimeField(null=True, blank=True)
    
#     # Cancellation
#     cancelled_at = models.DateTimeField(null=True, blank=True)
#     cancellation_reason = models.TextField(blank=True)
    
#     # Link to actual visit
#     visit = models.OneToOneField(
#         Visit,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='appointment'
#     )
    
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     class Meta:
#         db_table = 'appointments'
#         ordering = ['appointment_date', 'start_time']
#         indexes = [
#             models.Index(fields=['appointment_id']),
#             models.Index(fields=['patient', 'appointment_date']),
#             models.Index(fields=['doctor', 'appointment_date', 'status']),
#             models.Index(fields=['branch', 'appointment_date']),
#             models.Index(fields=['status', 'appointment_date']),
#         ]
    
#     def __str__(self):
#         return f"Appt {self.appointment_id}: {self.patient} with {self.doctor}"
    
#     def save(self, *args, **kwargs):
#         if not self.appointment_id:
#             self.appointment_id = self._generate_appointment_id()
        
#         # Auto-calculate end time if not set
#         if not self.end_time and self.start_time and self.duration:
#             from datetime import datetime, timedelta
#             start_dt = datetime.combine(self.appointment_date, self.start_time)
#             end_dt = start_dt + timedelta(minutes=self.duration)
#             self.end_time = end_dt.time()
        
#         super().save(*args, **kwargs)
    
#     def _generate_appointment_id(self):
#         """Generate APPT-YYYYMMDD-XXXX format ID"""
#         from datetime import datetime
#         from django.db.models import Count
        
#         date_str = self.appointment_date.strftime('%Y%m%d')
        
#         last_appt = Appointment.objects.filter(
#             appointment_id__startswith=f'APPT-{date_str}-'
#         ).order_by('appointment_id').last()
        
#         if last_appt:
#             last_num = int(last_appt.appointment_id.split('-')[-1])
#             new_num = last_num + 1
#         else:
#             new_num = 1
        
#         return f'APPT-{date_str}-{new_num:04d}'
    
#     @property
#     def is_upcoming(self):
#         """Check if appointment is in the future"""
#         from django.utils import timezone
#         today = timezone.now().date()
#         return self.appointment_date >= today and self.status in ['SCHEDULED', 'CONFIRMED']
    
#     @property
#     def is_today(self):
#         """Check if appointment is today"""
#         from django.utils import timezone
#         today = timezone.now().date()
#         return self.appointment_date == today
    
#     def convert_to_visit(self):
#         """Convert appointment to actual visit"""
#         if not self.visit:
#             from django.utils import timezone
#             visit = Visit.objects.create(
#                 patient=self.patient,
#                 doctor=self.doctor,
#                 branch=self.branch,
#                 scheduled_date=self.appointment_date,
#                 scheduled_time=self.start_time,
#                 appointment_source='ONLINE' if self.purpose else 'PHONE',
#                 chief_complaint=self.purpose
#             )
#             self.visit = visit
#             self.status = 'CHECKED_IN'
#             self.save()
#             return visit
#         return self.visit


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
        ('EMERGENCY', 'Emergency'),
    ]
    
    VISIT_TYPE = [
        ('CONSULTATION', 'Consultation'),
        ('TREATMENT', 'Treatment'),
        ('FOLLOW_UP', 'Follow-up'),
        ('EMERGENCY', 'Emergency'),
        ('SURGERY', 'Surgery'),
        ('CHECKUP', 'Regular Checkup'),
    ]
    
    PRIORITY_LEVEL = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('EMERGENCY', 'Emergency'),
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
    assigned_counter = models.ForeignKey(
        'clinics.Counter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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
    visit_type = models.CharField(max_length=20, choices=VISIT_TYPE, default='CONSULTATION')
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVEL, default='NORMAL')
    
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
    dental_issues = models.JSONField(default=dict, blank=True, help_text="JSON of affected teeth/areas")
    
    # Vital signs (can be null if not taken)
    blood_pressure = models.CharField(max_length=20, blank=True)
    heart_rate = models.IntegerField(null=True, blank=True)
    temperature = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
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
    follow_up_instructions = models.TextField(blank=True)
    
    # Doctor's notes
    diagnosis = models.TextField(blank=True)
    clinical_notes = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    
    # Treatment plan reference
    treatment_plan = models.ForeignKey(
        'treatments.TreatmentPlan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='visits'
    )
    
    # Queue management
    queue_number = models.IntegerField(null=True, blank=True)
    estimated_wait_time = models.DurationField(null=True, blank=True)
    
    # Insurance
    insurance_verified = models.BooleanField(default=False)
    insurance_notes = models.TextField(blank=True)
    
    # Referral
    referred_by = models.ForeignKey(
        'doctors.Doctor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals'
    )
    referral_reason = models.TextField(blank=True)
    
    class Meta:
        db_table = 'visits'
        ordering = ['-scheduled_date', '-scheduled_time']
        indexes = [
            models.Index(fields=['visit_id']),
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['doctor', 'status', 'scheduled_date']),
            models.Index(fields=['branch', 'status', 'scheduled_date']),
            models.Index(fields=['status', 'scheduled_date']),
            models.Index(fields=['queue_number', 'branch']),
            models.Index(fields=['priority', 'scheduled_date']),
        ]
    
    def __str__(self):
        return f"Visit {self.visit_id}: {self.patient} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        if not self.visit_id:
            self.visit_id = self._generate_visit_id()
        
        # Auto-generate queue number for walk-ins
        if self.appointment_source == 'WALK_IN' and not self.queue_number:
            self.queue_number = self._get_next_queue_number()
        
        # Auto-calculate wait time if checked in
        if self.actual_checkin and not self.wait_duration and self.scheduled_time:
            scheduled_dt = timezone.make_aware(
                timezone.datetime.combine(self.scheduled_date, self.scheduled_time)
            )
            if self.actual_checkin > scheduled_dt:
                self.wait_duration = self.actual_checkin - scheduled_dt
        
        super().save(*args, **kwargs)
    
    def _generate_visit_id(self):
        """Generate V-YYYYMMDD-XXXX format ID"""
        from datetime import datetime
        
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
    
    def _get_next_queue_number(self):
        """Get next queue number for the day"""
        today = timezone.now().date()
        last_visit = Visit.objects.filter(
            branch=self.branch,
            scheduled_date=today,
            appointment_source='WALK_IN'
        ).order_by('-queue_number').first()
        
        return (last_visit.queue_number if last_visit else 0) + 1
    
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
        checkout_statuses = [
            VisitStatus.IN_CONSULTATION, 
            VisitStatus.READY_FOR_BILLING,
            VisitStatus.TREATMENT_COMPLETED
        ]
        return self.status in checkout_statuses
    
    @property
    def current_status_info(self):
        """Get human-readable status information"""
        status_info = {
            VisitStatus.REGISTERED: "Waiting for doctor",
            VisitStatus.IN_CONSULTATION: f"With Dr. {self.doctor.user.get_full_name() if self.doctor else 'TBD'}",
            VisitStatus.READY_FOR_BILLING: "Ready for billing",
            VisitStatus.TREATMENT_COMPLETED: "Treatment completed",
            VisitStatus.PAID: "Payment received",
            VisitStatus.COMPLETED: "Visit completed",
            VisitStatus.CANCELLED: "Cancelled",
            VisitStatus.NO_SHOW: "No Show",
        }
        return status_info.get(self.status, self.get_status_display())
    
    def mark_checked_in(self, doctor=None):
        """Mark patient as checked in"""
        if self.status == VisitStatus.REGISTERED:
            self.actual_checkin = timezone.now()
            self.status = VisitStatus.IN_CONSULTATION
            if doctor:
                self.doctor = doctor
            self.save()
    
    def mark_consultation_complete(self, diagnosis="", clinical_notes="", recommendations=""):
        """Mark consultation as complete"""
        if self.status == VisitStatus.IN_CONSULTATION:
            self.diagnosis = diagnosis
            self.clinical_notes = clinical_notes
            self.recommendations = recommendations
            self.actual_checkout = timezone.now()
            
            # Auto-calculate consultation duration
            if self.actual_checkin:
                self.consultation_duration = self.actual_checkout - self.actual_checkin
            
            self.status = VisitStatus.READY_FOR_BILLING
            self.save()
    
    def mark_treatment_completed(self):
        """Mark treatment as completed"""
        self.actual_checkout = timezone.now()
        self.status = VisitStatus.TREATMENT_COMPLETED
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
    
    VISIT_TYPE = [
        ('CONSULTATION', 'Consultation'),
        ('TREATMENT', 'Treatment'),
        ('FOLLOW_UP', 'Follow-up'),
        ('EMERGENCY', 'Emergency'),
        ('SURGERY', 'Surgery'),
        ('CHECKUP', 'Regular Checkup'),
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
    visit_type = models.CharField(max_length=20, choices=VISIT_TYPE, default='CONSULTATION')
    
    # Timing
    appointment_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration = models.PositiveIntegerField(default=30, help_text="Duration in minutes")
    
    # Purpose
    purpose = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    expected_procedures = models.JSONField(default=list, blank=True, help_text="List of expected procedures")
    
    # Reminders
    reminder_sent = models.BooleanField(default=False)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Cancellation
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    cancelled_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_appointments'
    )
    
    # Link to actual visit
    visit = models.OneToOneField(
        Visit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointment'
    )
    
    # Recurring appointment
    is_recurring = models.BooleanField(default=False)
    recurrence_pattern = models.CharField(max_length=50, blank=True)  # 'WEEKLY', 'BIWEEKLY', 'MONTHLY'
    recurrence_end_date = models.DateField(null=True, blank=True)
    parent_appointment = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_appointments'
    )
    
    # Waiting list
    is_waiting_list = models.BooleanField(default=False)
    preferred_times = models.JSONField(default=list, blank=True, help_text="List of preferred alternative times")
    
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
            models.Index(fields=['is_waiting_list', 'appointment_date']),
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
        now = timezone.now()
        appointment_datetime = timezone.make_aware(
            timezone.datetime.combine(self.appointment_date, self.start_time)
        )
        return appointment_datetime > now and self.status in ['SCHEDULED', 'CONFIRMED']
    
    @property
    def is_today(self):
        """Check if appointment is today"""
        from django.utils import timezone
        today = timezone.now().date()
        return self.appointment_date == today and self.status in ['SCHEDULED', 'CONFIRMED']
    
    @property
    def is_past_due(self):
        """Check if appointment is past its scheduled time"""
        from django.utils import timezone
        now = timezone.now()
        appointment_datetime = timezone.make_aware(
            timezone.datetime.combine(self.appointment_date, self.start_time)
        )
        return appointment_datetime < now and self.status in ['SCHEDULED', 'CONFIRMED']
    
    def convert_to_visit(self):
        """Convert appointment to actual visit"""
        if not self.visit:
            visit = Visit.objects.create(
                patient=self.patient,
                doctor=self.doctor,
                branch=self.branch,
                scheduled_date=self.appointment_date,
                scheduled_time=self.start_time,
                appointment_source='ONLINE' if self.purpose else 'PHONE',
                chief_complaint=self.purpose,
                visit_type=self.visit_type
            )
            self.visit = visit
            self.status = 'CHECKED_IN'
            self.save()
            return visit
        return self.visit
    
    # def send_reminder(self):
    #     """Send appointment reminder"""
    #     from core.utils.notifications import send_sms_reminder, send_email_reminder
        
    #     # Send SMS reminder
    #     if self.patient.phone:
    #         send_sms_reminder(self.patient.phone, self)
        
    #     # Send email reminder
    #     if self.patient.user.email:
    #         send_email_reminder(self.patient.user.email, self)
        
    #     self.reminder_sent = True
    #     self.reminder_sent_at = timezone.now()
    #     self.save()


class Queue(models.Model):
    """Real-time queue management"""
    
    STATUS_CHOICES = [
        ('WAITING', 'Waiting'),
        ('IN_PROGRESS', 'In Progress'),
        ('SKIPPED', 'Skipped'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    branch = models.ForeignKey(
        'clinics.Branch',
        on_delete=models.CASCADE,
        related_name='queues'
    )
    doctor = models.ForeignKey(
        'doctors.Doctor',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='queues'
    )
    visit = models.OneToOneField(
        Visit,
        on_delete=models.CASCADE,
        related_name='queue_entry'
    )
    
    queue_number = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='WAITING')
    
    # Timing
    joined_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Counter assignment
    counter = models.ForeignKey(
        'clinics.Counter',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='queue_entries'
    )
    
    # Estimated wait time
    estimated_wait_minutes = models.IntegerField(default=15)
    
    # Notes
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'queues'
        ordering = ['queue_number']
        indexes = [
            models.Index(fields=['branch', 'status', 'queue_number']),
            models.Index(fields=['doctor', 'status']),
            models.Index(fields=['visit']),
        ]
        unique_together = ['branch', 'queue_number']
    
    def __str__(self):
        return f"Queue #{self.queue_number} - {self.visit.patient} ({self.get_status_display()})"
    
    def mark_called(self):
        """Mark patient as called"""
        if self.status == 'WAITING':
            self.called_at = timezone.now()
            self.status = 'IN_PROGRESS'
            self.save()
    
    def mark_completed(self):
        """Mark queue entry as completed"""
        self.completed_at = timezone.now()
        self.status = 'COMPLETED'
        self.save()
    
    def skip(self):
        """Skip patient in queue"""
        self.status = 'SKIPPED'
        self.save()
    
    @property
    def wait_time(self):
        """Calculate actual wait time"""
        if self.called_at and self.joined_at:
            return self.called_at - self.joined_at
        elif self.started_at and self.joined_at:
            return self.started_at - self.joined_at
        return None


class VisitDocument(models.Model):
    """Documents related to visit (prescriptions, reports, etc.)"""
    
    DOCUMENT_TYPES = [
        ('PRESCRIPTION', 'Prescription'),
        ('REPORT', 'Medical Report'),
        ('XRAY', 'X-Ray Image'),
        ('SCAN', 'Scan Result'),
        ('PHOTO', 'Clinical Photo'),
        ('CONSENT', 'Consent Form'),
        ('REFERRAL', 'Referral Letter'),
        ('CERTIFICATE', 'Medical Certificate'),
        ('OTHER', 'Other'),
    ]
    
    visit = models.ForeignKey(
        Visit,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # File storage
    file = models.FileField(upload_to='visit_documents/%Y/%m/%d/')
    thumbnail = models.ImageField(upload_to='visit_thumbnails/%Y/%m/%d/', null=True, blank=True)
    
    # Metadata
    uploaded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_documents'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Doctor notes
    doctor_notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'visit_documents'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.title} - {self.visit}"


class VisitVitalSign(models.Model):
    """Vital signs recorded during visit"""
    
    visit = models.ForeignKey(
        Visit,
        on_delete=models.CASCADE,
        related_name='vital_signs'
    )
    
    blood_pressure_systolic = models.IntegerField(null=True, blank=True)
    blood_pressure_diastolic = models.IntegerField(null=True, blank=True)
    heart_rate = models.IntegerField(null=True, blank=True)
    temperature = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    oxygen_saturation = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    respiratory_rate = models.IntegerField(null=True, blank=True)
    
    recorded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_vitals'
    )
    recorded_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'visit_vital_signs'
        ordering = ['-recorded_at']
    
    def __str__(self):
        return f"Vitals for {self.visit} at {self.recorded_at}"
    
    @property
    def bmi(self):
        """Calculate BMI"""
        if self.weight and self.height:
            # Convert height from cm to meters
            height_m = self.height / 100
            return round(self.weight / (height_m ** 2), 2)
        return None
    
    @property
    def blood_pressure(self):
        """Format blood pressure"""
        if self.blood_pressure_systolic and self.blood_pressure_diastolic:
            return f"{self.blood_pressure_systolic}/{self.blood_pressure_diastolic}"
        return None