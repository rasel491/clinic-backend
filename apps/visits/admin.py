#apps/visits/admin.py (Simple version)

from django.contrib import admin
from .models import Visit, Appointment

@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ('visit_id', 'patient', 'doctor', 'branch', 'status', 'scheduled_date', 'scheduled_time')
    list_filter = ('status', 'branch', 'doctor', 'appointment_source', 'scheduled_date')
    search_fields = ('visit_id', 'patient__user__full_name', 'chief_complaint')
    readonly_fields = ('visit_id', 'total_duration', 'is_active', 'can_checkout')
    raw_id_fields = ('patient', 'doctor', 'branch', 'follow_up_of')
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('visit_id', 'patient', 'doctor', 'branch', 'status')
        }),
        ('Timing', {
            'fields': ('scheduled_date', 'scheduled_time', 'actual_checkin', 
                      'actual_checkout', 'wait_duration', 'consultation_duration',
                      'total_duration')
        }),
        ('Visit Details', {
            'fields': ('appointment_source', 'chief_complaint', 'symptoms')
        }),
        ('Follow-up', {
            'fields': ('is_follow_up', 'follow_up_of', 'next_follow_up_date'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'can_checkout'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('appointment_id', 'patient', 'doctor', 'branch', 'status', 'appointment_date', 'start_time')
    list_filter = ('status', 'branch', 'doctor', 'appointment_date')
    search_fields = ('appointment_id', 'patient__user__full_name', 'purpose')
    readonly_fields = ('appointment_id', 'is_upcoming', 'is_today')
    raw_id_fields = ('patient', 'doctor', 'branch', 'visit')
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('appointment_id', 'patient', 'doctor', 'branch', 'status')
        }),
        ('Timing', {
            'fields': ('appointment_date', 'start_time', 'end_time', 'duration')
        }),
        ('Details', {
            'fields': ('purpose', 'notes')
        }),
        ('Reminders', {
            'fields': ('reminder_sent', 'reminder_sent_at'),
            'classes': ('collapse',)
        }),
        ('Cancellation', {
            'fields': ('cancelled_at', 'cancellation_reason'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_upcoming', 'is_today'),
            'classes': ('collapse',)
        }),
    )