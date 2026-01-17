from django.contrib import admin
from .models import TreatmentCategory, Treatment, TreatmentPlan, TreatmentPlanItem

@admin.register(TreatmentCategory)
class TreatmentCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')

@admin.register(Treatment)
class TreatmentAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'base_price', 'total_price', 'is_active')
    list_filter = ('category', 'is_active', 'difficulty')
    search_fields = ('code', 'name', 'description')
    readonly_fields = ('doctor_fee', 'tax_amount', 'total_price', 'duration_display')
    fieldsets = (
        ('Basic Info', {
            'fields': ('code', 'name', 'category', 'description')
        }),
        ('Pricing', {
            'fields': ('base_price', 'doctor_fee_percentage', 'tax_percentage', 
                      'doctor_fee', 'tax_amount', 'total_price')
        }),
        ('Procedure Details', {
            'fields': ('difficulty', 'duration_value', 'duration_unit', 
                      'duration_display', 'procedure_steps', 'materials_required', 
                      'precautions'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'requires_lab', 'lab_days')
        }),
    )

class TreatmentPlanItemInline(admin.TabularInline):
    model = TreatmentPlanItem
    extra = 1
    raw_id_fields = ('treatment', 'scheduled_visit')
    readonly_fields = ('actual_amount',)

@admin.register(TreatmentPlan)
class TreatmentPlanAdmin(admin.ModelAdmin):
    list_display = ('plan_id', 'patient', 'doctor', 'status', 'final_amount', 'paid_amount', 'balance_amount')
    list_filter = ('status', 'doctor')
    search_fields = ('plan_id', 'patient__user__full_name', 'name')
    readonly_fields = ('plan_id', 'total_estimated_amount', 'discount_amount', 
                      'final_amount', 'balance_amount', 'is_paid', 'progress_percentage')
    raw_id_fields = ('patient', 'doctor')
    inlines = [TreatmentPlanItemInline]
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('plan_id', 'patient', 'doctor', 'name', 'status')
        }),
        ('Financial', {
            'fields': ('total_estimated_amount', 'discount_percentage', 'discount_amount', 
                      'final_amount', 'paid_amount', 'balance_amount', 'is_paid')
        }),
        ('Timeline', {
            'fields': ('estimated_start_date', 'estimated_end_date', 
                      'actual_start_date', 'actual_end_date')
        }),
        ('Clinical Notes', {
            'fields': ('diagnosis', 'treatment_goals', 'notes'),
            'classes': ('collapse',)
        }),
        ('Progress', {
            'fields': ('progress_percentage',),
            'classes': ('collapse',)
        }),
    )

@admin.register(TreatmentPlanItem)
class TreatmentPlanItemAdmin(admin.ModelAdmin):
    list_display = ('treatment_plan', 'visit_number', 'treatment', 'status', 'scheduled_date', 'is_paid')
    list_filter = ('status', 'is_paid')
    search_fields = ('treatment_plan__plan_id', 'treatment__name')
    raw_id_fields = ('treatment_plan', 'treatment', 'scheduled_visit')