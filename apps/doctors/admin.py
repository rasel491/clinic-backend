from django.contrib import admin
from .models import Doctor, DoctorSchedule, DoctorLeave

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('doctor_id', 'user', 'specialization', 'primary_branch', 'is_active')
    list_filter = ('specialization', 'is_active', 'primary_branch')
    search_fields = ('doctor_id', 'user__email', 'user__full_name', 'license_number')
    readonly_fields = ('doctor_id',)
    raw_id_fields = ('user', 'primary_branch')

@admin.register(DoctorSchedule)
class DoctorScheduleAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'day_of_week', 'start_time', 'end_time', 'is_active')
    list_filter = ('day_of_week', 'is_active')
    raw_id_fields = ('doctor',)

@admin.register(DoctorLeave)
class DoctorLeaveAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'leave_date', 'reason', 'is_full_day', 'approved_by')
    list_filter = ('leave_date', 'is_full_day')
    raw_id_fields = ('doctor', 'approved_by')