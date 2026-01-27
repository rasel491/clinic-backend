# #apps/visits/admin.py (Simple version)

# from django.contrib import admin
# from .models import Visit, Appointment

# @admin.register(Visit)
# class VisitAdmin(admin.ModelAdmin):
#     list_display = ('visit_id', 'patient', 'doctor', 'branch', 'status', 'scheduled_date', 'scheduled_time')
#     list_filter = ('status', 'branch', 'doctor', 'appointment_source', 'scheduled_date')
#     search_fields = ('visit_id', 'patient__user__full_name', 'chief_complaint')
#     readonly_fields = ('visit_id', 'total_duration', 'is_active', 'can_checkout')
#     raw_id_fields = ('patient', 'doctor', 'branch', 'follow_up_of')
    
#     fieldsets = (
#         ('Basic Info', {
#             'fields': ('visit_id', 'patient', 'doctor', 'branch', 'status')
#         }),
#         ('Timing', {
#             'fields': ('scheduled_date', 'scheduled_time', 'actual_checkin', 
#                       'actual_checkout', 'wait_duration', 'consultation_duration',
#                       'total_duration')
#         }),
#         ('Visit Details', {
#             'fields': ('appointment_source', 'chief_complaint', 'symptoms')
#         }),
#         ('Follow-up', {
#             'fields': ('is_follow_up', 'follow_up_of', 'next_follow_up_date'),
#             'classes': ('collapse',)
#         }),
#         ('Status', {
#             'fields': ('is_active', 'can_checkout'),
#             'classes': ('collapse',)
#         }),
#     )

# @admin.register(Appointment)
# class AppointmentAdmin(admin.ModelAdmin):
#     list_display = ('appointment_id', 'patient', 'doctor', 'branch', 'status', 'appointment_date', 'start_time')
#     list_filter = ('status', 'branch', 'doctor', 'appointment_date')
#     search_fields = ('appointment_id', 'patient__user__full_name', 'purpose')
#     readonly_fields = ('appointment_id', 'is_upcoming', 'is_today')
#     raw_id_fields = ('patient', 'doctor', 'branch', 'visit')
    
#     fieldsets = (
#         ('Basic Info', {
#             'fields': ('appointment_id', 'patient', 'doctor', 'branch', 'status')
#         }),
#         ('Timing', {
#             'fields': ('appointment_date', 'start_time', 'end_time', 'duration')
#         }),
#         ('Details', {
#             'fields': ('purpose', 'notes')
#         }),
#         ('Reminders', {
#             'fields': ('reminder_sent', 'reminder_sent_at'),
#             'classes': ('collapse',)
#         }),
#         ('Cancellation', {
#             'fields': ('cancelled_at', 'cancellation_reason'),
#             'classes': ('collapse',)
#         }),
#         ('Status', {
#             'fields': ('is_upcoming', 'is_today'),
#             'classes': ('collapse',)
#         }),
#     )


# apps/visits/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.db.models import Count, Avg, DurationField, ExpressionWrapper, F
from datetime import timedelta
import json

from .models import (
    Visit, Appointment, Queue, VisitDocument, VisitVitalSign
)


class VisitDocumentInline(admin.TabularInline):
    """Inline for visit documents"""
    model = VisitDocument
    extra = 0
    fields = ['document_type', 'title', 'file', 'uploaded_by', 'uploaded_at']
    readonly_fields = ['uploaded_by', 'uploaded_at']
    
    def has_add_permission(self, request, obj=None):
        return request.user.role in ['SUPER_ADMIN', 'CLINIC_MANAGER', 'DOCTOR']
    
    def has_change_permission(self, request, obj=None):
        return request.user.role in ['SUPER_ADMIN', 'CLINIC_MANAGER', 'DOCTOR']
    
    def has_delete_permission(self, request, obj=None):
        return request.user.role in ['SUPER_ADMIN', 'CLINIC_MANAGER']


class VisitVitalSignInline(admin.TabularInline):
    """Inline for vital signs"""
    model = VisitVitalSign
    extra = 0
    fields = [
        'blood_pressure_systolic', 'blood_pressure_diastolic',
        'heart_rate', 'temperature', 'weight', 'height',
        'oxygen_saturation', 'respiratory_rate', 'recorded_by', 'recorded_at'
    ]
    readonly_fields = ['recorded_by', 'recorded_at', 'bmi', 'blood_pressure']
    
    def bmi(self, obj):
        return obj.bmi
    bmi.short_description = 'BMI'
    
    def blood_pressure(self, obj):
        return obj.blood_pressure
    blood_pressure.short_description = 'Blood Pressure'
    
    def has_add_permission(self, request, obj=None):
        return request.user.role in ['SUPER_ADMIN', 'DOCTOR']
    
    def has_change_permission(self, request, obj=None):
        return request.user.role in ['SUPER_ADMIN', 'DOCTOR']
    
    def has_delete_permission(self, request, obj=None):
        return request.user.role in ['SUPER_ADMIN', 'CLINIC_MANAGER']


class VisitAdmin(admin.ModelAdmin):
    """Admin interface for Visit model"""
    
    list_display = [
        'visit_id', 'patient_link', 'doctor_link', 'branch', 
        'status_badge', 'scheduled_date', 'scheduled_time',
        'visit_type', 'queue_display', 'duration_display'
    ]
    
    list_filter = [
        'status', 'appointment_source', 'visit_type', 'priority',
        'branch', 'doctor', 'scheduled_date', 'is_follow_up'
    ]
    
    search_fields = [
        'visit_id', 'patient__user__first_name', 'patient__user__last_name',
        'patient__user__email', 'doctor__user__first_name', 'doctor__user__last_name',
        'chief_complaint', 'symptoms'
    ]
    
    readonly_fields = [
        'visit_id', 'created_at', 'updated_at', 'total_duration',
        'is_active', 'can_checkout', 'current_status_info',
        'wait_duration', 'consultation_duration'
    ]
    
    raw_id_fields = ['patient', 'doctor', 'branch', 'follow_up_of', 'treatment_plan']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'visit_id', 'patient', 'doctor', 'branch', 
                'status', 'appointment_source', 'visit_type', 'priority'
            )
        }),
        ('Timing', {
            'fields': (
                'scheduled_date', 'scheduled_time', 
                'actual_checkin', 'actual_checkout',
                'wait_duration', 'consultation_duration', 'total_duration'
            )
        }),
        ('Visit Details', {
            'fields': (
                'chief_complaint', 'symptoms', 'dental_issues',
                'diagnosis', 'clinical_notes', 'recommendations'
            )
        }),
        ('Vital Signs', {
            'fields': (
                'blood_pressure', 'heart_rate', 'temperature',
                'weight', 'height'
            ),
            'classes': ('collapse',)
        }),
        ('Follow-up Information', {
            'fields': (
                'is_follow_up', 'follow_up_of', 'next_follow_up_date',
                'follow_up_instructions'
            ),
            'classes': ('collapse',)
        }),
        ('Queue Management', {
            'fields': (
                'queue_number', 'estimated_wait_time', 'assigned_counter'
            ),
            'classes': ('collapse',)
        }),
        ('Insurance & Referral', {
            'fields': (
                'insurance_verified', 'insurance_notes',
                'referred_by', 'referral_reason'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': (
                'created_at', 'updated_at', 'is_active', 
                'can_checkout', 'current_status_info'
            ),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [VisitVitalSignInline, VisitDocumentInline]
    
    actions = [
        'mark_as_checked_in', 'mark_as_in_consultation', 
        'mark_as_ready_for_billing', 'mark_as_completed',
        'mark_as_cancelled', 'export_selected_visits'
    ]
    
    def patient_link(self, obj):
        """Display patient as clickable link"""
        url = reverse('admin:patients_patient_change', args=[obj.patient.id])
        return format_html('<a href="{}">{}</a>', url, obj.patient.user.get_full_name())
    patient_link.short_description = 'Patient'
    patient_link.admin_order_field = 'patient__user__first_name'
    
    def doctor_link(self, obj):
        """Display doctor as clickable link"""
        if obj.doctor:
            url = reverse('admin:doctors_doctor_change', args=[obj.doctor.id])
            return format_html('<a href="{}">Dr. {}</a>', url, obj.doctor.user.get_full_name())
        return "Not Assigned"
    doctor_link.short_description = 'Doctor'
    doctor_link.admin_order_field = 'doctor__user__first_name'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        status_colors = {
            'REGISTERED': 'blue',
            'IN_CONSULTATION': 'orange',
            'READY_FOR_BILLING': 'purple',
            'TREATMENT_COMPLETED': 'yellow',
            'PAID': 'green',
            'COMPLETED': 'darkgreen',
            'CANCELLED': 'red',
            'NO_SHOW': 'gray',
        }
        color = status_colors.get(obj.status, 'black')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 12px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def queue_display(self, obj):
        """Display queue number if exists"""
        if obj.queue_number:
            return f"#{obj.queue_number}"
        return "-"
    queue_display.short_description = 'Queue'
    
    def duration_display(self, obj):
        """Display total duration in minutes"""
        if obj.total_duration:
            minutes = int(obj.total_duration.total_seconds() / 60)
            return f"{minutes} min"
        return "-"
    duration_display.short_description = 'Duration'
    
    # Custom actions
    def mark_as_checked_in(self, request, queryset):
        """Mark selected visits as checked in"""
        count = 0
        for visit in queryset:
            if visit.status == 'REGISTERED':
                visit.mark_checked_in()
                count += 1
        
        if count:
            self.message_user(request, f'{count} visit(s) marked as checked in.')
        else:
            self.message_user(request, 'No visits were eligible for check-in.', level=messages.WARNING)
    mark_as_checked_in.short_description = "Mark as checked in"
    
    def mark_as_in_consultation(self, request, queryset):
        """Mark selected visits as in consultation"""
        count = 0
        for visit in queryset:
            if visit.status == 'REGISTERED':
                visit.status = 'IN_CONSULTATION'
                visit.actual_checkin = timezone.now()
                visit.save()
                count += 1
        
        self.message_user(request, f'{count} visit(s) marked as in consultation.')
    mark_as_in_consultation.short_description = "Mark as in consultation"
    
    def mark_as_ready_for_billing(self, request, queryset):
        """Mark selected visits as ready for billing"""
        count = 0
        for visit in queryset:
            if visit.status == 'IN_CONSULTATION':
                visit.status = 'READY_FOR_BILLING'
                visit.actual_checkout = timezone.now()
                visit.save()
                count += 1
        
        self.message_user(request, f'{count} visit(s) marked as ready for billing.')
    mark_as_ready_for_billing.short_description = "Mark as ready for billing"
    
    def mark_as_completed(self, request, queryset):
        """Mark selected visits as completed"""
        count = 0
        for visit in queryset:
            if visit.status == 'PAID':
                visit.status = 'COMPLETED'
                visit.save()
                count += 1
        
        if count:
            self.message_user(request, f'{count} visit(s) marked as completed.')
        else:
            self.message_user(request, 'Only paid visits can be marked as completed.', level=messages.WARNING)
    mark_as_completed.short_description = "Mark as completed"
    
    def mark_as_cancelled(self, request, queryset):
        """Mark selected visits as cancelled"""
        count = 0
        for visit in queryset:
            if visit.status not in ['COMPLETED', 'CANCELLED', 'PAID']:
                visit.status = 'CANCELLED'
                visit.save()
                count += 1
        
        self.message_user(request, f'{count} visit(s) marked as cancelled.')
    mark_as_cancelled.short_description = "Mark as cancelled"
    
    def export_selected_visits(self, request, queryset):
        """Export selected visits to Excel"""
        import pandas as pd
        from django.http import HttpResponse
        
        data = []
        for visit in queryset:
            data.append({
                'Visit ID': visit.visit_id,
                'Patient': visit.patient.user.get_full_name(),
                'Doctor': visit.doctor.user.get_full_name() if visit.doctor else '',
                'Branch': visit.branch.name,
                'Date': visit.scheduled_date,
                'Time': visit.scheduled_time.strftime('%H:%M'),
                'Status': visit.get_status_display(),
                'Type': visit.get_visit_type_display(),
                'Chief Complaint': visit.chief_complaint,
                'Diagnosis': visit.diagnosis,
                'Check-in': visit.actual_checkin.strftime('%Y-%m-%d %H:%M') if visit.actual_checkin else '',
                'Check-out': visit.actual_checkout.strftime('%Y-%m-%d %H:%M') if visit.actual_checkout else '',
                'Wait Time (min)': visit.wait_duration.total_seconds() / 60 if visit.wait_duration else 0,
                'Consultation Time (min)': visit.consultation_duration.total_seconds() / 60 if visit.consultation_duration else 0,
            })
        
        df = pd.DataFrame(data)
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=visits_export.xlsx'
        
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Visits', index=False)
        
        return response
    export_selected_visits.short_description = "Export selected visits to Excel"
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """Custom change view with additional context"""
        extra_context = extra_context or {}
        extra_context['show_save_and_add_another'] = False
        extra_context['show_save_and_continue'] = True
        
        # Add action buttons based on status
        obj = self.get_object(request, object_id)
        extra_context['can_check_in'] = obj.status == 'REGISTERED'
        extra_context['can_complete_consultation'] = obj.status == 'IN_CONSULTATION'
        extra_context['can_complete_visit'] = obj.status == 'PAID'
        
        return super().change_view(request, object_id, form_url, extra_context)
    
    def save_model(self, request, obj, form, change):
        """Override save to handle status changes"""
        if not change:  # Creating new
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


class AppointmentAdmin(admin.ModelAdmin):
    """Admin interface for Appointment model"""
    
    list_display = [
        'appointment_id', 'patient_link', 'doctor_link', 'branch',
        'status_badge', 'appointment_date', 'start_time', 'duration_display',
        'is_upcoming_badge', 'reminder_sent_badge'
    ]
    
    list_filter = [
        'status', 'visit_type', 'branch', 'doctor', 
        'appointment_date', 'is_waiting_list', 'is_recurring'
    ]
    
    search_fields = [
        'appointment_id', 'patient__user__first_name', 'patient__user__last_name',
        'patient__user__email', 'doctor__user__first_name', 'doctor__user__last_name',
        'purpose', 'notes'
    ]
    
    readonly_fields = [
        'appointment_id', 'created_at', 'updated_at', 
        'is_upcoming', 'is_today', 'is_past_due',
        'reminder_sent', 'reminder_sent_at',
        'cancelled_at', 'cancelled_by'
    ]
    
    raw_id_fields = ['patient', 'doctor', 'branch', 'visit', 'parent_appointment']
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'appointment_id', 'patient', 'doctor', 'branch',
                'status', 'visit_type'
            )
        }),
        ('Timing', {
            'fields': (
                'appointment_date', 'start_time', 'end_time', 'duration'
            )
        }),
        ('Appointment Details', {
            'fields': (
                'purpose', 'notes', 'expected_procedures'
            )
        }),
        ('Reminders', {
            'fields': (
                'reminder_sent', 'reminder_sent_at'
            ),
            'classes': ('collapse',)
        }),
        ('Cancellation', {
            'fields': (
                'cancelled_at', 'cancellation_reason', 'cancelled_by'
            ),
            'classes': ('collapse',)
        }),
        ('Recurrence', {
            'fields': (
                'is_recurring', 'recurrence_pattern', 'recurrence_end_date',
                'parent_appointment'
            ),
            'classes': ('collapse',)
        }),
        ('Waiting List', {
            'fields': (
                'is_waiting_list', 'preferred_times'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': (
                'created_at', 'updated_at', 'is_upcoming', 
                'is_today', 'is_past_due'
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'confirm_appointments', 'cancel_appointments', 'send_reminders',
        'convert_to_visits', 'export_selected_appointments'
    ]
    
    def patient_link(self, obj):
        """Display patient as clickable link"""
        url = reverse('admin:patients_patient_change', args=[obj.patient.id])
        return format_html('<a href="{}">{}</a>', url, obj.patient.user.get_full_name())
    patient_link.short_description = 'Patient'
    
    def doctor_link(self, obj):
        """Display doctor as clickable link"""
        url = reverse('admin:doctors_doctor_change', args=[obj.doctor.id])
        return format_html('<a href="{}">Dr. {}</a>', url, obj.doctor.user.get_full_name())
    doctor_link.short_description = 'Doctor'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        status_colors = {
            'SCHEDULED': 'blue',
            'CONFIRMED': 'green',
            'CHECKED_IN': 'orange',
            'NO_SHOW': 'gray',
            'CANCELLED': 'red',
            'COMPLETED': 'darkgreen',
        }
        color = status_colors.get(obj.status, 'black')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 12px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def duration_display(self, obj):
        """Display duration"""
        return f"{obj.duration} min"
    duration_display.short_description = 'Duration'
    
    def is_upcoming_badge(self, obj):
        """Display upcoming status"""
        if obj.is_upcoming:
            return format_html(
                '<span style="background-color: green; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">UPCOMING</span>'
            )
        elif obj.is_today:
            return format_html(
                '<span style="background-color: orange; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">TODAY</span>'
            )
        return ''
    is_upcoming_badge.short_description = 'Timing'
    
    def reminder_sent_badge(self, obj):
        """Display reminder status"""
        if obj.reminder_sent:
            return format_html(
                '<span style="background-color: green; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">SENT</span>'
            )
        return format_html(
            '<span style="background-color: gray; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">PENDING</span>'
        )
    reminder_sent_badge.short_description = 'Reminder'
    
    # Custom actions
    def confirm_appointments(self, request, queryset):
        """Confirm selected appointments"""
        count = 0
        for appointment in queryset:
            if appointment.status == 'SCHEDULED':
                appointment.status = 'CONFIRMED'
                appointment.save()
                count += 1
        
        self.message_user(request, f'{count} appointment(s) confirmed.')
    confirm_appointments.short_description = "Confirm selected appointments"
    
    def cancel_appointments(self, request, queryset):
        """Cancel selected appointments"""
        count = 0
        for appointment in queryset:
            if appointment.status in ['SCHEDULED', 'CONFIRMED']:
                appointment.status = 'CANCELLED'
                appointment.cancelled_at = timezone.now()
                appointment.cancelled_by = request.user
                appointment.save()
                count += 1
        
        self.message_user(request, f'{count} appointment(s) cancelled.')
    cancel_appointments.short_description = "Cancel selected appointments"
    
    # def send_reminders(self, request, queryset):
    #     """Send reminders for selected appointments"""
    #     from core.utils.notifications import NotificationService
        
    #     count = 0
    #     for appointment in queryset:
    #         if appointment.status in ['SCHEDULED', 'CONFIRMED'] and not appointment.reminder_sent:
    #             if NotificationService.send_appointment_reminder(appointment):
    #                 appointment.reminder_sent = True
    #                 appointment.reminder_sent_at = timezone.now()
    #                 appointment.save()
    #                 count += 1
        
    #     self.message_user(request, f'Reminders sent for {count} appointment(s).')
    # send_reminders.short_description = "Send reminders"
    
    def convert_to_visits(self, request, queryset):
        """Convert appointments to visits"""
        count = 0
        for appointment in queryset:
            if appointment.status in ['SCHEDULED', 'CONFIRMED'] and not appointment.visit:
                appointment.convert_to_visit()
                count += 1
        
        self.message_user(request, f'{count} appointment(s) converted to visits.')
    convert_to_visits.short_description = "Convert to visits"
    
    def export_selected_appointments(self, request, queryset):
        """Export selected appointments to Excel"""
        import pandas as pd
        from django.http import HttpResponse
        
        data = []
        for appointment in queryset:
            data.append({
                'Appointment ID': appointment.appointment_id,
                'Patient': appointment.patient.user.get_full_name(),
                'Doctor': appointment.doctor.user.get_full_name(),
                'Branch': appointment.branch.name,
                'Date': appointment.appointment_date,
                'Time': appointment.start_time.strftime('%H:%M'),
                'Duration': appointment.duration,
                'Status': appointment.get_status_display(),
                'Type': appointment.get_visit_type_display(),
                'Purpose': appointment.purpose,
                'Reminder Sent': 'Yes' if appointment.reminder_sent else 'No',
                'Recurring': 'Yes' if appointment.is_recurring else 'No',
                'Waiting List': 'Yes' if appointment.is_waiting_list else 'No',
            })
        
        df = pd.DataFrame(data)
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=appointments_export.xlsx'
        
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Appointments', index=False)
        
        return response
    export_selected_appointments.short_description = "Export selected appointments to Excel"


class QueueAdmin(admin.ModelAdmin):
    """Admin interface for Queue model"""
    
    list_display = [
        'queue_number', 'branch', 'doctor_link', 'patient_link',
        'status_badge', 'wait_time_display', 'estimated_wait',
        'counter_display', 'joined_time'
    ]
    
    list_filter = [
        'branch', 'doctor', 'status', 'counter',
        ('joined_at', admin.DateFieldListFilter),  # Changed this line
    ]
    
    search_fields = [
        'visit__patient__user__first_name', 'visit__patient__user__last_name',
        'visit__patient__user__email', 'doctor__user__first_name',
        'doctor__user__last_name', 'notes'
    ]
    
    readonly_fields = [
        'joined_at', 'called_at', 'started_at', 'completed_at',
        'wait_time'
    ]
    
    raw_id_fields = ['branch', 'doctor', 'visit', 'counter']
    
    fieldsets = (
        ('Queue Information', {
            'fields': (
                'branch', 'doctor', 'visit', 'queue_number', 'status'
            )
        }),
        ('Timing', {
            'fields': (
                'joined_at', 'called_at', 'started_at', 'completed_at',
                'estimated_wait_minutes', 'wait_time'
            )
        }),
        ('Counter Assignment', {
            'fields': ('counter',)
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )
    
    actions = [
        'call_patients', 'start_consultations', 'complete_queue',
        'skip_patients', 'reset_queue'
    ]
    
    def doctor_link(self, obj):
        """Display doctor as clickable link"""
        if obj.doctor:
            url = reverse('admin:doctors_doctor_change', args=[obj.doctor.id])
            return format_html('<a href="{}">Dr. {}</a>', url, obj.doctor.user.get_full_name())
        return "Not Assigned"
    doctor_link.short_description = 'Doctor'
    
    def patient_link(self, obj):
        """Display patient as clickable link"""
        if obj.visit and obj.visit.patient:
            url = reverse('admin:patients_patient_change', args=[obj.visit.patient.id])
            return format_html('<a href="{}">{}</a>', url, obj.visit.patient.user.get_full_name())
        return "No Patient"
    patient_link.short_description = 'Patient'
    
    def status_badge(self, obj):
        """Display status as colored badge"""
        status_colors = {
            'WAITING': 'orange',
            'IN_PROGRESS': 'green',
            'COMPLETED': 'darkgreen',
            'SKIPPED': 'gray',
            'CANCELLED': 'red',
        }
        color = status_colors.get(obj.status, 'black')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 12px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def wait_time_display(self, obj):
        """Display wait time"""
        if obj.wait_time:
            minutes = int(obj.wait_time.total_seconds() / 60)
            return f"{minutes} min"
        return "-"
    wait_time_display.short_description = 'Wait Time'
    
    def estimated_wait(self, obj):
        """Display estimated wait"""
        return f"{obj.estimated_wait_minutes} min"
    estimated_wait.short_description = 'Estimated'
    
    def counter_display(self, obj):
        """Display counter"""
        if obj.counter:
            return f"Counter {obj.counter.number}"
        return "-"
    counter_display.short_description = 'Counter'
    
    def joined_time(self, obj):
        """Display joined time"""
        return obj.joined_at.strftime('%H:%M') if obj.joined_at else "-"
    joined_time.short_description = 'Joined At'
    
    # Custom actions
    def call_patients(self, request, queryset):
        """Call selected patients"""
        count = 0
        for queue in queryset:
            if queue.status == 'WAITING':
                queue.mark_called()
                count += 1
        
        self.message_user(request, f'{count} patient(s) called.')
    call_patients.short_description = "Call patients"
    
    def start_consultations(self, request, queryset):
        """Start consultations for selected queue entries"""
        count = 0
        for queue in queryset:
            if queue.status == 'IN_PROGRESS' and not queue.started_at:
                queue.started_at = timezone.now()
                queue.save()
                count += 1
        
        self.message_user(request, f'Consultations started for {count} patient(s).')
    start_consultations.short_description = "Start consultations"
    
    def complete_queue(self, request, queryset):
        """Complete selected queue entries"""
        count = 0
        for queue in queryset:
            if queue.status in ['WAITING', 'IN_PROGRESS']:
                queue.mark_completed()
                count += 1
        
        self.message_user(request, f'{count} queue entry(s) completed.')
    complete_queue.short_description = "Complete queue entries"
    
    def skip_patients(self, request, queryset):
        """Skip selected patients in queue"""
        count = 0
        for queue in queryset:
            if queue.status == 'WAITING':
                queue.skip()
                count += 1
        
        self.message_user(request, f'{count} patient(s) skipped.')
    skip_patients.short_description = "Skip patients"
    
    def reset_queue(self, request, queryset):
        """Reset selected queue entries"""
        count = 0
        for queue in queryset:
            queue.status = 'WAITING'
            queue.called_at = None
            queue.started_at = None
            queue.completed_at = None
            queue.save()
            count += 1
        
        self.message_user(request, f'{count} queue entry(s) reset.')
    reset_queue.short_description = "Reset queue entries"
    
    def changelist_view(self, request, extra_context=None):
        """Add today's queue summary to context"""
        extra_context = extra_context or {}
        today = timezone.now().date()
        
        # Get queue statistics for today
        today_queues = Queue.objects.filter(joined_at__date=today)
        total = today_queues.count()
        waiting = today_queues.filter(status='WAITING').count()
        in_progress = today_queues.filter(status='IN_PROGRESS').count()
        completed = today_queues.filter(status='COMPLETED').count()
        
        extra_context['queue_stats'] = {
            'total': total,
            'waiting': waiting,
            'in_progress': in_progress,
            'completed': completed,
            'date': today
        }
        
        return super().changelist_view(request, extra_context=extra_context)


class VisitVitalSignAdmin(admin.ModelAdmin):
    """Admin interface for VisitVitalSign model"""
    
    list_display = [
        'visit_link', 'recorded_by_link', 'recorded_at',
        'blood_pressure_display', 'heart_rate', 'temperature',
        'bmi_display', 'weight_height'
    ]
    
    list_filter = [
        ('recorded_at', admin.DateFieldListFilter),  # Changed this line
        'visit__doctor', 'visit__branch'
    ]
    
    search_fields = [
        'visit__visit_id', 'visit__patient__user__first_name',
        'visit__patient__user__last_name', 'notes'
    ]
    
    readonly_fields = ['recorded_by', 'recorded_at', 'bmi', 'blood_pressure']
    
    raw_id_fields = ['visit', 'recorded_by']
    
    fieldsets = (
        ('Vital Signs', {
            'fields': (
                'visit', 'recorded_by', 'recorded_at',
                'blood_pressure_systolic', 'blood_pressure_diastolic',
                'heart_rate', 'temperature', 'weight', 'height',
                'oxygen_saturation', 'respiratory_rate'
            )
        }),
        ('Calculated Values', {
            'fields': ('bmi', 'blood_pressure'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )
    
    def visit_link(self, obj):
        """Display visit as clickable link"""
        url = reverse('admin:visits_visit_change', args=[obj.visit.id])
        return format_html('<a href="{}">{}</a>', url, obj.visit.visit_id)
    visit_link.short_description = 'Visit'
    
    def recorded_by_link(self, obj):
        """Display recorded by as clickable link"""
        if obj.recorded_by:
            url = reverse('admin:accounts_user_change', args=[obj.recorded_by.id])
            return format_html('<a href="{}">{}</a>', url, obj.recorded_by.get_full_name())
        return "-"
    recorded_by_link.short_description = 'Recorded By'
    
    def blood_pressure_display(self, obj):
        """Display blood pressure"""
        return obj.blood_pressure or "-"
    blood_pressure_display.short_description = 'Blood Pressure'
    
    def bmi_display(self, obj):
        """Display BMI with color coding"""
        bmi = obj.bmi
        if bmi:
            if bmi < 18.5:
                color = 'blue'
                category = 'Underweight'
            elif bmi < 25:
                color = 'green'
                category = 'Normal'
            elif bmi < 30:
                color = 'orange'
                category = 'Overweight'
            else:
                color = 'red'
                category = 'Obese'
            
            return format_html(
                '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{} ({})</span>',
                color, round(bmi, 1), category
            )
        return "-"
    bmi_display.short_description = 'BMI'
    
    def weight_height(self, obj):
        """Display weight and height"""
        weight = f"{obj.weight} kg" if obj.weight else "-"
        height = f"{obj.height} cm" if obj.height else "-"
        return f"{weight} / {height}"
    weight_height.short_description = 'Weight / Height'
    
    def save_model(self, request, obj, form, change):
        """Set recorded_by if creating new"""
        if not change:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)


class VisitDocumentAdmin(admin.ModelAdmin):
    """Admin interface for VisitDocument model"""
    
    list_display = [
        'title', 'visit_link', 'document_type_badge', 
        'uploaded_by_link', 'uploaded_at', 'file_size_display'  # Changed to file_size_display
    ]
    
    list_filter = [
        'document_type',
        ('uploaded_at', admin.DateFieldListFilter),  # Changed this line
        'visit__branch'
    ]
    
    search_fields = [
        'title', 'description', 'visit__visit_id',
        'visit__patient__user__first_name', 'visit__patient__user__last_name'
    ]
    
    readonly_fields = ['uploaded_by', 'uploaded_at', 'document_url']
    
    raw_id_fields = ['visit', 'uploaded_by']
    
    fieldsets = (
        ('Document Information', {
            'fields': (
                'visit', 'document_type', 'title', 'description'
            )
        }),
        ('File Upload', {
            'fields': (
                'file', 'thumbnail'
            )
        }),
        ('Doctor Notes', {
            'fields': ('doctor_notes',)
        }),
        ('Metadata', {
            'fields': (
                'uploaded_by', 'uploaded_at', 'file_size', 'document_url'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def visit_link(self, obj):
        """Display visit as clickable link"""
        url = reverse('admin:visits_visit_change', args=[obj.visit.id])
        return format_html('<a href="{}">{}</a>', url, obj.visit.visit_id)
    visit_link.short_description = 'Visit'
    
    def document_type_badge(self, obj):
        """Display document type as badge"""
        type_colors = {
            'PRESCRIPTION': 'green',
            'REPORT': 'blue',
            'XRAY': 'purple',
            'SCAN': 'orange',
            'PHOTO': 'teal',
            'CONSENT': 'gray',
            'REFERRAL': 'brown',
            'CERTIFICATE': 'darkblue',
            'OTHER': 'black',
        }
        color = type_colors.get(obj.document_type, 'black')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_document_type_display()
        )
    document_type_badge.short_description = 'Type'
    
    def uploaded_by_link(self, obj):
        """Display uploaded by as clickable link"""
        if obj.uploaded_by:
            url = reverse('admin:accounts_user_change', args=[obj.uploaded_by.id])
            return format_html('<a href="{}">{}</a>', url, obj.uploaded_by.get_full_name())
        return "-"
    uploaded_by_link.short_description = 'Uploaded By'
    
    def file_size_display(self, obj):
        """Display file size"""
        return obj.file_size or "-"
    file_size_display.short_description = 'File Size'
    
    def document_url(self, obj):
        """Display document URL"""
        if obj.file:
            return format_html('<a href="{}" target="_blank">Download</a>', obj.file.url)
        return "-"
    document_url.short_description = 'File URL'
    
    def save_model(self, request, obj, form, change):
        """Set uploaded_by if creating new"""
        if not change:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


# Register models with admin
admin.site.register(Visit, VisitAdmin)
admin.site.register(Appointment, AppointmentAdmin)
admin.site.register(Queue, QueueAdmin)
admin.site.register(VisitVitalSign, VisitVitalSignAdmin)
admin.site.register(VisitDocument, VisitDocumentAdmin)

# Custom admin site header and title
admin.site.site_header = "Dental Clinic Management System"
admin.site.site_title = "Visits Administration"
admin.site.index_title = "Visits Module Administration"