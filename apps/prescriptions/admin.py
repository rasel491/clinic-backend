# # apps/prescriptions/admin.py (Simple version)

# from django.contrib import admin
# from .models import Prescription, Medicine, PrescriptionMedicine, PrescriptionDispense

# class PrescriptionMedicineInline(admin.TabularInline):
#     model = PrescriptionMedicine
#     extra = 1
#     raw_id_fields = ('medicine',)

# class PrescriptionDispenseInline(admin.TabularInline):
#     model = PrescriptionDispense
#     extra = 0
#     readonly_fields = ('dispense_id', 'dispensed_date')
#     raw_id_fields = ('verified_by',)

# @admin.register(Prescription)
# class PrescriptionAdmin(admin.ModelAdmin):
#     list_display = ('prescription_id', 'patient', 'doctor', 'status', 'prescription_type', 'created_at')
#     list_filter = ('status', 'prescription_type', 'doctor', 'created_at')
#     search_fields = ('prescription_id', 'patient__user__full_name', 'doctor__user__full_name', 'diagnosis')
#     readonly_fields = ('prescription_id', 'verification_code', 'pdf_hash', 'is_signed', 'total_medicines', 'is_dispensable')
#     raw_id_fields = ('visit', 'patient', 'doctor')
#     inlines = [PrescriptionMedicineInline]
    
#     fieldsets = (
#         ('Basic Info', {
#             'fields': ('prescription_id', 'visit', 'patient', 'doctor', 'status', 'prescription_type')
#         }),
#         ('Clinical Details', {
#             'fields': ('diagnosis', 'symptoms', 'clinical_findings', 'advice'),
#             'classes': ('collapse',)
#         }),
#         ('Follow-up', {
#             'fields': ('next_review_date', 'follow_up_instructions'),
#             'classes': ('collapse',)
#         }),
#         ('Pharmacy', {
#             'fields': ('pharmacy_notes', 'is_pharmacy_copy_sent', 'pharmacy_sent_at'),
#             'classes': ('collapse',)
#         }),
#         ('Digital Signature', {
#             'fields': ('doctor_signature', 'signed_at', 'is_signed'),
#             'classes': ('collapse',)
#         }),
#         ('Documents', {
#             'fields': ('pdf_file', 'pdf_hash', 'qr_code', 'verification_code'),
#             'classes': ('collapse',)
#         }),
#         ('Status', {
#             'fields': ('total_medicines', 'is_dispensable'),
#             'classes': ('collapse',)
#         }),
#     )

# @admin.register(Medicine)
# class MedicineAdmin(admin.ModelAdmin):
#     list_display = ('name', 'generic_name', 'brand', 'medicine_type', 'strength', 'is_controlled', 'is_active')
#     list_filter = ('medicine_type', 'is_controlled', 'is_active', 'schedule')
#     search_fields = ('name', 'generic_name', 'brand')
#     readonly_fields = ('created_at', 'updated_at')

# @admin.register(PrescriptionMedicine)
# class PrescriptionMedicineAdmin(admin.ModelAdmin):
#     list_display = ('prescription', 'medicine', 'dosage', 'frequency', 'duration_display', 'quantity')
#     list_filter = ('frequency', 'route', 'is_repeat')
#     search_fields = ('prescription__prescription_id', 'medicine__name')
#     raw_id_fields = ('prescription', 'medicine')
#     readonly_fields = ('duration_display', 'timing_display')

# @admin.register(PrescriptionDispense)
# class PrescriptionDispenseAdmin(admin.ModelAdmin):
#     list_display = ('dispense_id', 'prescription_medicine', 'dispensed_date', 'dispensed_quantity', 'pharmacy_name')
#     list_filter = ('dispensed_date', 'pharmacy_name')
#     search_fields = ('dispense_id', 'prescription_medicine__medicine__name', 'pharmacy_name')
#     readonly_fields = ('dispense_id', 'dispensed_date')
#     raw_id_fields = ('prescription_medicine', 'verified_by')
#     inlines = []




# apps/prescriptions/admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Prescription, Medication, PrescriptionItem, 
    PrescriptionTemplate, TemplateMedication
)


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = (
        'prescription_id', 'patient', 'doctor', 'issue_date', 
        'status', 'is_valid', 'items_count', 'total_amount'
    )
    list_filter = ('status', 'prescription_type', 'issue_date', 'doctor')
    search_fields = (
        'prescription_id', 'patient__patient_id', 'patient__user__full_name',
        'doctor__doctor_id', 'doctor__user__full_name'
    )
    readonly_fields = ('prescription_id', 'is_valid', 'items_count', 'total_quantity')
    raw_id_fields = ('patient', 'doctor', 'visit', 'dispensing_pharmacy', 'dispensed_by')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('prescription_id', 'prescription_type', 'patient', 'doctor', 'visit')
        }),
        ('Prescription Details', {
            'fields': ('diagnosis', 'notes', 'instructions')
        }),
        ('Status & Dates', {
            'fields': ('status', 'issue_date', 'valid_until', 'is_valid')
        }),
        ('Refill Information', {
            'fields': ('is_refillable', 'max_refills', 'refills_remaining', 'last_refill_date')
        }),
        ('Digital Signature', {
            'fields': ('is_signed', 'signed_at')
        }),
        ('Pharmacy Details', {
            'fields': ('dispensing_pharmacy', 'dispensed_by', 'dispensed_at')
        }),
        ('Billing Information', {
            'fields': ('total_amount', 'insurance_covered', 'patient_payable')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by', 'deleted_at', 'deleted_by'),
            'classes': ('collapse',)
        }),
    )
    
    def is_valid(self, obj):
        return obj.is_valid
    is_valid.boolean = True
    is_valid.short_description = 'Valid'


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = (
        'medicine_id', 'name', 'brand', 'category', 'form', 
        'strength', 'in_stock', 'current_stock', 'unit_price'
    )
    list_filter = ('category', 'form', 'requires_prescription', 'is_active', 'in_stock')
    search_fields = ('medicine_id', 'name', 'generic_name', 'brand')
    readonly_fields = ('stock_status', 'needs_restocking', 'is_expired')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('medicine_id', 'name', 'generic_name', 'brand')
        }),
        ('Medical Information', {
            'fields': ('category', 'form', 'strength', 'unit')
        }),
        ('Stock Information', {
            'fields': ('in_stock', 'current_stock', 'stock_status', 
                      'min_stock_level', 'max_stock_level', 'needs_restocking')
        }),
        ('Pricing', {
            'fields': ('unit_price', 'cost_price')
        }),
        ('Medical Details', {
            'fields': ('indications', 'contraindications', 'side_effects', 
                      'dosage_instructions', 'storage_instructions'),
            'classes': ('collapse',)
        }),
        ('Regulatory Information', {
            'fields': ('requires_prescription', 'schedule', 'mfg_date', 
                      'expiry_date', 'batch_number', 'is_expired')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def stock_status(self, obj):
        return obj.stock_status
    stock_status.short_description = 'Stock Status'
    
    def needs_restocking(self, obj):
        return obj.needs_restocking
    needs_restocking.boolean = True
    needs_restocking.short_description = 'Needs Restocking'
    
    def is_expired(self, obj):
        return obj.is_expired
    is_expired.boolean = True
    is_expired.short_description = 'Expired'


@admin.register(PrescriptionItem)
class PrescriptionItemAdmin(admin.ModelAdmin):
    list_display = (
        'prescription', 'medication', 'dosage', 'frequency', 
        'duration', 'quantity', 'is_dispensed', 'total_price'
    )
    list_filter = ('is_dispensed', 'frequency')
    search_fields = ('prescription__prescription_id', 'medication__name')
    raw_id_fields = ('prescription', 'medication', 'dispensed_by')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('prescription', 'medication')
        }),
        ('Dosage Information', {
            'fields': ('dosage', 'frequency', 'duration', 'duration_unit')
        }),
        ('Quantity & Instructions', {
            'fields': ('quantity', 'instructions', 'remaining_quantity')
        }),
        ('Pricing', {
            'fields': ('unit_price', 'total_price')
        }),
        ('Dispensing', {
            'fields': ('is_dispensed', 'dispensed_quantity', 'dispensed_by', 'dispensed_at')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def remaining_quantity(self, obj):
        return obj.remaining_quantity
    remaining_quantity.short_description = 'Remaining'


@admin.register(PrescriptionTemplate)
class PrescriptionTemplateAdmin(admin.ModelAdmin):
    list_display = ('template_id', 'name', 'specialization', 'is_active', 'usage_count')
    list_filter = ('specialization', 'is_active')
    search_fields = ('template_id', 'name', 'diagnoses')
    readonly_fields = ('template_id', 'usage_count')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('template_id', 'name', 'description', 'specialization')
        }),
        ('Common Diagnoses', {
            'fields': ('diagnoses',)
        }),
        ('Template Content', {
            'fields': ('default_diagnosis', 'default_notes', 'default_instructions')
        }),
        ('Status', {
            'fields': ('is_active', 'usage_count')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TemplateMedication)
class TemplateMedicationAdmin(admin.ModelAdmin):
    list_display = ('template', 'medication', 'default_dosage', 'default_frequency', 'display_order')
    list_filter = ('template__specialization',)
    search_fields = ('template__name', 'medication__name')
    raw_id_fields = ('template', 'medication')