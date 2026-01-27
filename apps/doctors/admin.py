# from django.contrib import admin
# from .models import Doctor, DoctorSchedule, DoctorLeave

# @admin.register(Doctor)
# class DoctorAdmin(admin.ModelAdmin):
#     list_display = ('doctor_id', 'user', 'specialization', 'primary_branch', 'is_active')
#     list_filter = ('specialization', 'is_active', 'primary_branch')
#     search_fields = ('doctor_id', 'user__email', 'user__full_name', 'license_number')
#     readonly_fields = ('doctor_id',)
#     raw_id_fields = ('user', 'primary_branch')

# @admin.register(DoctorSchedule)
# class DoctorScheduleAdmin(admin.ModelAdmin):
#     list_display = ('doctor', 'day_of_week', 'start_time', 'end_time', 'is_active')
#     list_filter = ('day_of_week', 'is_active')
#     raw_id_fields = ('doctor',)

# @admin.register(DoctorLeave)
# class DoctorLeaveAdmin(admin.ModelAdmin):
#     list_display = ('doctor', 'leave_date', 'reason', 'is_full_day', 'approved_by')
#     list_filter = ('leave_date', 'is_full_day')
#     raw_id_fields = ('doctor', 'approved_by')


# apps/doctors/admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import Doctor, DoctorSchedule, DoctorLeave
from django.utils   import timezone

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('doctor_id', 'full_name', 'specialization', 'primary_branch', 'is_active', 'is_license_valid')
    list_filter = ('specialization', 'is_active', 'primary_branch', 'is_accepting_new_patients')
    search_fields = ('doctor_id', 'user__email', 'user__full_name', 'license_number', 'registration_number')
    readonly_fields = ('doctor_id', 'is_license_valid', 'created_at', 'updated_at', 'created_by', 'updated_by')
    raw_id_fields = ('user', 'primary_branch')
    filter_horizontal = ('secondary_branches',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'doctor_id', 'title', 'specialization', 'bio')
        }),
        ('Professional Details', {
            'fields': ('qualification', 'education', 'certifications', 'years_of_experience',
                      'license_number', 'license_expiry', 'license_issuing_authority',
                      'registration_number', 'npi_number')
        }),
        ('Branch & Availability', {
            'fields': ('primary_branch', 'secondary_branches', 'is_active', 
                      'is_accepting_new_patients', 'consultation_fee', 'follow_up_fee')
        }),
        ('Contact & Preferences', {
            'fields': ('preferred_contact_method', 'languages_spoken', 'emergency_contact_name',
                      'emergency_contact_phone', 'emergency_contact_relation')
        }),
        ('Awards & Signature', {
            'fields': ('awards', 'signature_image')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by', 'is_deleted'),
            'classes': ('collapse',)
        }),
    )
    
    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Full Name'
    
    def is_license_valid(self, obj):
        return obj.is_license_valid
    is_license_valid.boolean = True
    is_license_valid.short_description = 'License Valid'


@admin.register(DoctorSchedule)
class DoctorScheduleAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'branch', 'day_of_week', 'start_time', 'end_time', 'is_active', 'working_hours')
    list_filter = ('day_of_week', 'is_active', 'branch')
    search_fields = ('doctor__doctor_id', 'doctor__user__full_name', 'room_number')
    raw_id_fields = ('doctor', 'branch')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('doctor', 'branch', 'day_of_week', 'is_active')
        }),
        ('Working Hours', {
            'fields': ('start_time', 'end_time', 'break_start', 'break_end')
        }),
        ('Appointment Settings', {
            'fields': ('slot_duration', 'max_patients_per_slot')
        }),
        ('Room Details', {
            'fields': ('room_number', 'chair_number')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def working_hours(self, obj):
        return f"{obj.working_hours:.1f} hours"
    working_hours.short_description = 'Working Hours'


@admin.register(DoctorLeave)
class DoctorLeaveAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'leave_type', 'start_date', 'end_date', 'status', 'total_days', 'approved_by')
    list_filter = ('leave_type', 'status', 'start_date', 'is_full_day')
    search_fields = ('doctor__doctor_id', 'doctor__user__full_name', 'reason')
    raw_id_fields = ('doctor', 'approved_by', 'covering_doctor')
    readonly_fields = ('total_days', 'approved_at', 'created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Leave Information', {
            'fields': ('doctor', 'leave_type', 'start_date', 'end_date', 'is_full_day',
                      'start_time', 'end_time', 'reason')
        }),
        ('Approval Process', {
            'fields': ('status', 'approved_by', 'approved_at', 'rejection_reason',
                      'covering_doctor')
        }),
        ('Calculated Fields', {
            'fields': ('total_days',)
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_leaves', 'reject_leaves']
    
    def approve_leaves(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(
            status='APPROVED',
            approved_by=request.user,
            approved_at=timezone.now()
        )
        self.message_user(request, f"{updated} leaves approved.")
    approve_leaves.short_description = "Approve selected leaves"
    
    def reject_leaves(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(
            status='REJECTED',
            approved_by=request.user,
            approved_at=timezone.now()
        )
        self.message_user(request, f"{updated} leaves rejected.")
    reject_leaves.short_description = "Reject selected leaves"