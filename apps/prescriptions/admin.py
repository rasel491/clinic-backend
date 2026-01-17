# apps/prescriptions/admin.py (Simple version)

from django.contrib import admin
from .models import Prescription, Medicine, PrescriptionMedicine, PrescriptionDispense

class PrescriptionMedicineInline(admin.TabularInline):
    model = PrescriptionMedicine
    extra = 1
    raw_id_fields = ('medicine',)

class PrescriptionDispenseInline(admin.TabularInline):
    model = PrescriptionDispense
    extra = 0
    readonly_fields = ('dispense_id', 'dispensed_date')
    raw_id_fields = ('verified_by',)

@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ('prescription_id', 'patient', 'doctor', 'status', 'prescription_type', 'created_at')
    list_filter = ('status', 'prescription_type', 'doctor', 'created_at')
    search_fields = ('prescription_id', 'patient__user__full_name', 'doctor__user__full_name', 'diagnosis')
    readonly_fields = ('prescription_id', 'verification_code', 'pdf_hash', 'is_signed', 'total_medicines', 'is_dispensable')
    raw_id_fields = ('visit', 'patient', 'doctor')
    inlines = [PrescriptionMedicineInline]
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('prescription_id', 'visit', 'patient', 'doctor', 'status', 'prescription_type')
        }),
        ('Clinical Details', {
            'fields': ('diagnosis', 'symptoms', 'clinical_findings', 'advice'),
            'classes': ('collapse',)
        }),
        ('Follow-up', {
            'fields': ('next_review_date', 'follow_up_instructions'),
            'classes': ('collapse',)
        }),
        ('Pharmacy', {
            'fields': ('pharmacy_notes', 'is_pharmacy_copy_sent', 'pharmacy_sent_at'),
            'classes': ('collapse',)
        }),
        ('Digital Signature', {
            'fields': ('doctor_signature', 'signed_at', 'is_signed'),
            'classes': ('collapse',)
        }),
        ('Documents', {
            'fields': ('pdf_file', 'pdf_hash', 'qr_code', 'verification_code'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('total_medicines', 'is_dispensable'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('name', 'generic_name', 'brand', 'medicine_type', 'strength', 'is_controlled', 'is_active')
    list_filter = ('medicine_type', 'is_controlled', 'is_active', 'schedule')
    search_fields = ('name', 'generic_name', 'brand')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(PrescriptionMedicine)
class PrescriptionMedicineAdmin(admin.ModelAdmin):
    list_display = ('prescription', 'medicine', 'dosage', 'frequency', 'duration_display', 'quantity')
    list_filter = ('frequency', 'route', 'is_repeat')
    search_fields = ('prescription__prescription_id', 'medicine__name')
    raw_id_fields = ('prescription', 'medicine')
    readonly_fields = ('duration_display', 'timing_display')

@admin.register(PrescriptionDispense)
class PrescriptionDispenseAdmin(admin.ModelAdmin):
    list_display = ('dispense_id', 'prescription_medicine', 'dispensed_date', 'dispensed_quantity', 'pharmacy_name')
    list_filter = ('dispensed_date', 'pharmacy_name')
    search_fields = ('dispense_id', 'prescription_medicine__medicine__name', 'pharmacy_name')
    readonly_fields = ('dispense_id', 'dispensed_date')
    raw_id_fields = ('prescription_medicine', 'verified_by')
    inlines = []