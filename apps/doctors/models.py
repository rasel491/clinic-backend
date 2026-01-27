# #apps/doctors/models.py

# from django.db import models
# from core.mixins.audit_fields import AuditFieldsMixin
# from core.mixins.soft_delete import SoftDeleteMixin

# class Doctor(AuditFieldsMixin, SoftDeleteMixin, models.Model):
#     """Doctor profile - link to User account"""
    
#     SPECIALIZATION_CHOICES = [
#         ('GENERAL', 'General Dentistry'),
#         ('ORTHO', 'Orthodontics'),
#         ('PERIO', 'Periodontics'),
#         ('ENDO', 'Endodontics'),
#         ('PEDO', 'Pediatric Dentistry'),
#         ('SURG', 'Oral Surgery'),
#         ('PROS', 'Prosthodontics'),
#     ]
    
#     user = models.OneToOneField(
#         'accounts.User',
#         on_delete=models.CASCADE,
#         related_name='doctor_profile'
#     )
    
#     # Professional details
#     doctor_id = models.CharField(max_length=50, unique=True, blank=True)
#     specialization = models.CharField(max_length=50, choices=SPECIALIZATION_CHOICES)
#     qualification = models.CharField(max_length=200)
#     license_number = models.CharField(max_length=100, unique=True)
#     license_expiry = models.DateField()
    
#     # Branch association
#     primary_branch = models.ForeignKey(
#         'clinics.Branch',
#         on_delete=models.PROTECT,
#         related_name='doctors'
#     )
    
#     # Availability
#     is_active = models.BooleanField(default=True)
#     consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
#     # Bio
#     bio = models.TextField(blank=True)
#     years_of_experience = models.PositiveIntegerField(default=0)
    
#     class Meta:
#         db_table = 'doctors'
#         ordering = ['doctor_id']
#         indexes = [
#             models.Index(fields=['doctor_id']),
#             models.Index(fields=['specialization']),
#             models.Index(fields=['primary_branch', 'is_active']),
#             models.Index(fields=['license_number']),
#         ]
    
#     def __str__(self):
#         return f"Dr. {self.user.full_name} ({self.specialization})"
    
#     def save(self, *args, **kwargs):
#         if not self.doctor_id:
#             self.doctor_id = self._generate_doctor_id()
#         super().save(*args, **kwargs)
    
#     def _generate_doctor_id(self):
#         """Generate DOC-XXX format ID"""
#         from django.db.models import Count
        
#         count = Doctor.objects.count() + 1
#         return f'DOC-{count:03d}'

# class DoctorSchedule(AuditFieldsMixin, models.Model):
#     """Doctor's working schedule"""
    
#     DAY_CHOICES = [
#         (0, 'Monday'),
#         (1, 'Tuesday'),
#         (2, 'Wednesday'),
#         (3, 'Thursday'),
#         (4, 'Friday'),
#         (5, 'Saturday'),
#         (6, 'Sunday'),
#     ]
    
#     doctor = models.ForeignKey(
#         Doctor,
#         on_delete=models.CASCADE,
#         related_name='schedules'
#     )
    
#     day_of_week = models.IntegerField(choices=DAY_CHOICES)
#     start_time = models.TimeField()
#     end_time = models.TimeField()
#     is_active = models.BooleanField(default=True)
    
#     # Break timings
#     break_start = models.TimeField(null=True, blank=True)
#     break_end = models.TimeField(null=True, blank=True)
    
#     # Appointment settings
#     slot_duration = models.PositiveIntegerField(default=30)  # minutes
#     max_patients_per_slot = models.PositiveIntegerField(default=1)
    
#     class Meta:
#         db_table = 'doctor_schedules'
#         unique_together = ['doctor', 'day_of_week']
#         ordering = ['doctor', 'day_of_week']
#         indexes = [
#             models.Index(fields=['doctor', 'day_of_week', 'is_active']),
#         ]
    
#     def __str__(self):
#         return f"{self.doctor} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"

# class DoctorLeave(models.Model):
#     """Doctor's leave/absence records"""
    
#     doctor = models.ForeignKey(
#         Doctor,
#         on_delete=models.CASCADE,
#         related_name='leaves'
#     )
    
#     leave_date = models.DateField()
#     reason = models.CharField(max_length=200)
#     is_full_day = models.BooleanField(default=True)
    
#     # For half-day leaves
#     start_time = models.TimeField(null=True, blank=True)
#     end_time = models.TimeField(null=True, blank=True)
    
#     approved_by = models.ForeignKey(
#         'accounts.User',
#         on_delete=models.SET_NULL,
#         null=True,
#         related_name='approved_leaves'
#     )
    
#     created_at = models.DateTimeField(auto_now_add=True)
    
#     class Meta:
#         db_table = 'doctor_leaves'
#         unique_together = ['doctor', 'leave_date']
#         ordering = ['-leave_date']
#         indexes = [
#             models.Index(fields=['doctor', 'leave_date']),
#         ]
    
#     def __str__(self):
#         return f"{self.doctor} - {self.leave_date} ({self.reason})"



# apps/doctors/models.py

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin


class Doctor(AuditFieldsMixin, SoftDeleteMixin, models.Model):
    """Doctor profile - link to User account"""
    
    SPECIALIZATION_CHOICES = [
        ('GENERAL', 'General Dentistry'),
        ('ORTHO', 'Orthodontics'),
        ('PERIO', 'Periodontics'),
        ('ENDO', 'Endodontics'),
        ('PEDO', 'Pediatric Dentistry'),
        ('SURG', 'Oral Surgery'),
        ('PROS', 'Prosthodontics'),
        ('RADIO', 'Oral Radiology'),
        ('PATHO', 'Oral Pathology'),
        ('PUBLIC', 'Public Health Dentistry'),
    ]
    
    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='doctor_profile'
    )
    
    # Professional details
    doctor_id = models.CharField(max_length=50, unique=True, blank=True)
    specialization = models.CharField(max_length=50, choices=SPECIALIZATION_CHOICES)
    qualification = models.TextField(blank=True)
    license_number = models.CharField(max_length=100, unique=True)
    license_expiry = models.DateField()
    license_issuing_authority = models.CharField(max_length=200, blank=True)
    
    # Branch association
    primary_branch = models.ForeignKey(
        'clinics.Branch',
        on_delete=models.PROTECT,
        related_name='primary_doctors'
    )
    secondary_branches = models.ManyToManyField(
        'clinics.Branch',
        related_name='secondary_doctors',
        blank=True
    )
    
    # Professional details
    title = models.CharField(max_length=50, blank=True, default='Dr.')
    registration_number = models.CharField(max_length=100, blank=True)
    npi_number = models.CharField(max_length=20, blank=True)
    
    # Availability
    is_active = models.BooleanField(default=True)
    is_accepting_new_patients = models.BooleanField(default=True)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    follow_up_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True, null=True)
    
    # Contact preferences
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=[
            ('CLINIC', 'Clinic Phone'),
            ('PERSONAL', 'Personal Phone'),
            ('EMAIL', 'Email'),
            ('WHATSAPP', 'WhatsApp'),
        ],
        default='CLINIC'
    )
    
    # Bio
    bio = models.TextField(blank=True)
    years_of_experience = models.PositiveIntegerField(default=0)
    education = models.TextField(blank=True)
    certifications = models.TextField(blank=True)
    languages_spoken = models.CharField(max_length=200, default='English', blank=True)
    awards = models.TextField(blank=True)
    
    # Emergency contact
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    emergency_contact_relation = models.CharField(max_length=50, blank=True)
    
    # Signature
    signature_image = models.ImageField(
        upload_to='doctor_signatures/',
        null=True,
        blank=True
    )
    
    class Meta:
        db_table = 'doctors'
        ordering = ['doctor_id']
        indexes = [
            models.Index(fields=['doctor_id']),
            models.Index(fields=['specialization']),
            models.Index(fields=['primary_branch', 'is_active']),
            models.Index(fields=['license_number']),
            models.Index(fields=['is_accepting_new_patients']),
        ]
        verbose_name = 'Doctor'
        verbose_name_plural = 'Doctors'
    
    def __str__(self):
        title = f"{self.title} " if self.title else ""
        return f"{title}{self.user.full_name} ({self.specialization})"
    
    def clean(self):
        super().clean()
        
        if self.license_expiry and self.license_expiry < timezone.now().date():
            raise ValidationError({'license_expiry': 'License has expired.'})
        
        if self.years_of_experience > 100:
            raise ValidationError({'years_of_experience': 'Please enter a valid number of years.'})
    
    def save(self, *args, **kwargs):
        if not self.doctor_id:
            self.doctor_id = self._generate_doctor_id()
        super().save(*args, **kwargs)
    
    def _generate_doctor_id(self):
        from django.db.models import Count
        from datetime import datetime
        
        now = datetime.now()
        year_month = now.strftime('%Y%m')
        
        current_month_count = Doctor.objects.filter(
            doctor_id__startswith=f'DOC-{year_month}-'
        ).count() + 1
        
        return f'DOC-{year_month}-{current_month_count:04d}'
    
    @property
    def full_name(self):
        title = f"{self.title} " if self.title else ""
        return f"{title}{self.user.full_name}"
    
    @property
    def is_license_valid(self):
        return self.license_expiry >= timezone.now().date()
    
    @property
    def all_branches(self):
        branches = [self.primary_branch]
        branches.extend(self.secondary_branches.all())
        return list(set(branches))


# class DoctorSchedule(AuditFieldsMixin, models.Model):
#     """Doctor's working schedule"""
    
#     DAY_CHOICES = [
#         (0, 'Monday'),
#         (1, 'Tuesday'),
#         (2, 'Wednesday'),
#         (3, 'Thursday'),
#         (4, 'Friday'),
#         (5, 'Saturday'),
#         (6, 'Sunday'),
#     ]
    
#     doctor = models.ForeignKey(
#         Doctor,
#         on_delete=models.CASCADE,
#         related_name='schedules'
#     )
#     # Make branch nullable for migration, then we'll update it
#     branch = models.ForeignKey(
#         'clinics.Branch',
#         on_delete=models.CASCADE,
#         related_name='doctor_schedules',
#         null=True,  # TEMPORARY - for migration
#         blank=True  # TEMPORARY - for migration
#     )
    
#     day_of_week = models.IntegerField(choices=DAY_CHOICES)
#     start_time = models.TimeField()
#     end_time = models.TimeField()
#     is_active = models.BooleanField(default=True)
    
#     # Break timings
#     break_start = models.TimeField(null=True, blank=True)
#     break_end = models.TimeField(null=True, blank=True)
    
#     # Appointment settings
#     slot_duration = models.PositiveIntegerField(default=30, help_text="Duration in minutes")
#     max_patients_per_slot = models.PositiveIntegerField(default=1, help_text="Maximum patients per time slot")
    
#     # Room/Chair assignment
#     room_number = models.CharField(max_length=20, blank=True)
#     chair_number = models.CharField(max_length=20, blank=True)
    
#     class Meta:
#         db_table = 'doctor_schedules'
#         unique_together = ['doctor', 'branch', 'day_of_week']
#         ordering = ['doctor', 'day_of_week']
#         indexes = [
#             models.Index(fields=['doctor', 'branch', 'day_of_week', 'is_active']),
#             models.Index(fields=['branch', 'day_of_week', 'is_active']),
#         ]
#         verbose_name = 'Doctor Schedule'
#         verbose_name_plural = 'Doctor Schedules'
    
#     def __str__(self):
#         branch_name = self.branch.name if self.branch else 'No Branch'
#         return f"{self.doctor} - {branch_name} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"
    
#     def clean(self):
#         super().clean()
        
#         if self.end_time <= self.start_time:
#             raise ValidationError({'end_time': 'End time must be after start time.'})
        
#         if (self.break_start or self.break_end) and not (self.break_start and self.break_end):
#             raise ValidationError('Both break start and end times must be provided.')
        
#         if self.break_start and self.break_end:
#             if self.break_end <= self.break_start:
#                 raise ValidationError('Break end time must be after break start time.')
#             if self.break_start < self.start_time or self.break_end > self.end_time:
#                 raise ValidationError('Break time must be within working hours.')
    
#     @property
#     def working_hours(self):
#         from datetime import datetime, timedelta
        
#         start = datetime.combine(datetime.today(), self.start_time)
#         end = datetime.combine(datetime.today(), self.end_time)
        
#         if self.break_start and self.break_end:
#             break_start = datetime.combine(datetime.today(), self.break_start)
#             break_end = datetime.combine(datetime.today(), self.break_end)
#             break_duration = break_end - break_start
#             total_duration = (end - start) - break_duration
#         else:
#             total_duration = end - start
        
#         return total_duration.total_seconds() / 3600
    
#     @property
#     def total_slots(self):
#         total_minutes = self.working_hours * 60
#         return int(total_minutes / self.slot_duration)


# class DoctorLeave(AuditFieldsMixin, models.Model):
#     """Doctor's leave/absence records"""
    
#     LEAVE_TYPES = [
#         ('VACATION', 'Vacation'),
#         ('SICK', 'Sick Leave'),
#         ('PERSONAL', 'Personal Leave'),
#         ('EMERGENCY', 'Emergency'),
#         ('TRAINING', 'Training/Conference'),
#         ('OTHER', 'Other'),
#     ]
    
#     STATUS_CHOICES = [
#         ('PENDING', 'Pending Approval'),
#         ('APPROVED', 'Approved'),
#         ('REJECTED', 'Rejected'),
#         ('CANCELLED', 'Cancelled'),
#     ]
    
#     doctor = models.ForeignKey(
#         Doctor,
#         on_delete=models.CASCADE,
#         related_name='leaves'
#     )
    
#     leave_type = models.CharField(
#         max_length=20, 
#         choices=LEAVE_TYPES,
#         default='VACATION'  # Add default
#     )
#     start_date = models.DateField()
#     end_date = models.DateField()
#     reason = models.TextField()
#     is_full_day = models.BooleanField(default=True)
    
#     # For half-day leaves
#     start_time = models.TimeField(null=True, blank=True)
#     end_time = models.TimeField(null=True, blank=True)
    
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
#     approved_by = models.ForeignKey(
#         'accounts.User',
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='approved_leaves'
#     )
#     approved_at = models.DateTimeField(null=True, blank=True)
    
#     # Rejection/Cancellation reason
#     rejection_reason = models.TextField(blank=True)
    
#     # Cover doctor (if applicable)
#     covering_doctor = models.ForeignKey(
#         Doctor,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='covered_leaves'
#     )
    
#     class Meta:
#         db_table = 'doctor_leaves'
#         ordering = ['-start_date']
#         indexes = [
#             models.Index(fields=['doctor', 'start_date', 'end_date']),
#             models.Index(fields=['doctor', 'status']),
#             models.Index(fields=['start_date', 'end_date']),
#         ]
#         verbose_name = 'Doctor Leave'
#         verbose_name_plural = 'Doctor Leaves'
    
#     def __str__(self):
#         return f"{self.doctor} - {self.start_date} to {self.end_date} ({self.get_leave_type_display()})"
    
#     def clean(self):
#         super().clean()
        
#         if self.end_date < self.start_date:
#             raise ValidationError({'end_date': 'End date must be after start date.'})
        
#         if not self.is_full_day and not (self.start_time and self.end_time):
#             raise ValidationError('For half-day leaves, both start and end times must be provided.')
        
#         if self.covering_doctor and self.covering_doctor == self.doctor:
#             raise ValidationError({'covering_doctor': 'Doctor cannot cover their own leave.'})
    
#     def save(self, *args, **kwargs):
#         if self.status == 'APPROVED' and not self.approved_at:
#             self.approved_at = timezone.now()
#         super().save(*args, **kwargs)
    
#     @property
#     def total_days(self):
#         from datetime import timedelta
        
#         days = (self.end_date - self.start_date).days + 1
#         if not self.is_full_day:
#             days = days * 0.5
#         return days
    
#     def is_on_leave(self, date, time=None):
#         if not (self.start_date <= date <= self.end_date):
#             return False
        
#         if self.status != 'APPROVED':
#             return False
        
#         if self.is_full_day:
#             return True
        
#         if time and self.start_time and self.end_time:
#             return self.start_time <= time <= self.end_time
        
#         return False

class DoctorSchedule(AuditFieldsMixin, SoftDeleteMixin, models.Model):  # Added SoftDeleteMixin
    """Doctor's working schedule"""
    
    DAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    branch = models.ForeignKey(
        'clinics.Branch',
        on_delete=models.CASCADE,
        related_name='doctor_schedules'
    )
    
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    
    # Break timings
    break_start = models.TimeField(null=True, blank=True)
    break_end = models.TimeField(null=True, blank=True)
    
    # Appointment settings
    slot_duration = models.PositiveIntegerField(default=30, help_text="Duration in minutes")
    max_patients_per_slot = models.PositiveIntegerField(default=1, help_text="Maximum patients per time slot")
    
    # Room/Chair assignment
    room_number = models.CharField(max_length=20, blank=True)
    chair_number = models.CharField(max_length=20, blank=True)
    
    class Meta:
        db_table = 'doctor_schedules'
        unique_together = ['doctor', 'branch', 'day_of_week']
        ordering = ['doctor', 'day_of_week']
        indexes = [
            models.Index(fields=['doctor', 'branch', 'day_of_week', 'is_active']),
            models.Index(fields=['branch', 'day_of_week', 'is_active']),
        ]
        verbose_name = 'Doctor Schedule'
        verbose_name_plural = 'Doctor Schedules'
    
    def __str__(self):
        return f"{self.doctor} - {self.branch} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"
    
    def clean(self):
        super().clean()
        
        if self.end_time <= self.start_time:
            raise ValidationError({'end_time': 'End time must be after start time.'})
        
        if (self.break_start or self.break_end) and not (self.break_start and self.break_end):
            raise ValidationError('Both break start and end times must be provided.')
        
        if self.break_start and self.break_end:
            if self.break_end <= self.break_start:
                raise ValidationError('Break end time must be after break start time.')
            if self.break_start < self.start_time or self.break_end > self.end_time:
                raise ValidationError('Break time must be within working hours.')
    
    @property
    def working_hours(self):
        from datetime import datetime, timedelta
        
        start = datetime.combine(datetime.today(), self.start_time)
        end = datetime.combine(datetime.today(), self.end_time)
        
        if self.break_start and self.break_end:
            break_start = datetime.combine(datetime.today(), self.break_start)
            break_end = datetime.combine(datetime.today(), self.break_end)
            break_duration = break_end - break_start
            total_duration = (end - start) - break_duration
        else:
            total_duration = end - start
        
        return total_duration.total_seconds() / 3600
    
    @property
    def total_slots(self):
        total_minutes = self.working_hours * 60
        return int(total_minutes / self.slot_duration)


class DoctorLeave(AuditFieldsMixin, SoftDeleteMixin, models.Model):  # Added SoftDeleteMixin
    """Doctor's leave/absence records"""
    
    LEAVE_TYPES = [
        ('VACATION', 'Vacation'),
        ('SICK', 'Sick Leave'),
        ('PERSONAL', 'Personal Leave'),
        ('EMERGENCY', 'Emergency'),
        ('TRAINING', 'Training/Conference'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name='leaves'
    )
    
    leave_type = models.CharField(
        max_length=20, 
        choices=LEAVE_TYPES,
        default='VACATION'
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    is_full_day = models.BooleanField(default=True)
    
    # For half-day leaves
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    approved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_leaves'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Rejection/Cancellation reason
    rejection_reason = models.TextField(blank=True)
    
    # Cover doctor (if applicable)
    covering_doctor = models.ForeignKey(
        Doctor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='covered_leaves'
    )
    
    class Meta:
        db_table = 'doctor_leaves'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['doctor', 'start_date', 'end_date']),
            models.Index(fields=['doctor', 'status']),
            models.Index(fields=['start_date', 'end_date']),
        ]
        verbose_name = 'Doctor Leave'
        verbose_name_plural = 'Doctor Leaves'
    
    def __str__(self):
        return f"{self.doctor} - {self.start_date} to {self.end_date} ({self.get_leave_type_display()})"
    
    def clean(self):
        super().clean()
        
        if self.end_date < self.start_date:
            raise ValidationError({'end_date': 'End date must be after start date.'})
        
        if not self.is_full_day and not (self.start_time and self.end_time):
            raise ValidationError('For half-day leaves, both start and end times must be provided.')
        
        if self.covering_doctor and self.covering_doctor == self.doctor:
            raise ValidationError({'covering_doctor': 'Doctor cannot cover their own leave.'})
    
    def save(self, *args, **kwargs):
        if self.status == 'APPROVED' and not self.approved_at:
            self.approved_at = timezone.now()
        super().save(*args, **kwargs)
    
    @property
    def total_days(self):
        from datetime import timedelta
        
        days = (self.end_date - self.start_date).days + 1
        if not self.is_full_day:
            days = days * 0.5
        return days
    
    def is_on_leave(self, date, time=None):
        if not (self.start_date <= date <= self.end_date):
            return False
        
        if self.status != 'APPROVED':
            return False
        
        if self.is_full_day:
            return True
        
        if time and self.start_time and self.end_time:
            return self.start_time <= time <= self.end_time
        
        return False