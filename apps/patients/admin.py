from django.contrib import admin
from .models import Patient

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('patient_id', 'user', 'date_of_birth', 'gender', 'registered_branch')
    list_filter = ('gender', 'registered_branch', 'is_insurance_verified')
    search_fields = ('patient_id', 'user__email', 'user__full_name', 'insurance_id')
    readonly_fields = ('patient_id', 'registered_at')
    raw_id_fields = ('user', 'registered_branch')
    
    fieldsets = (
        ('Personal Info', {
            'fields': ('user', 'patient_id', 'date_of_birth', 'gender', 'blood_group')
        }),
        ('Emergency Contact', {
            'fields': ('emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relation'),
            'classes': ('collapse',)
        }),
        ('Medical Info', {
            'fields': ('allergies', 'chronic_conditions', 'current_medications'),
            'classes': ('collapse',)
        }),
        ('Registration', {
            'fields': ('registered_at', 'registered_branch')
        }),
        ('Insurance', {
            'fields': ('is_insurance_verified', 'insurance_provider', 'insurance_id'),
            'classes': ('collapse',)
        }),
    )