# #apps/treatments/admin.py
# from django.contrib import admin
# from .models import TreatmentCategory, Treatment, TreatmentPlan, TreatmentPlanItem

# @admin.register(TreatmentCategory)
# class TreatmentCategoryAdmin(admin.ModelAdmin):
#     list_display = ('name', 'code', 'is_active')
#     list_filter = ('is_active',)
#     search_fields = ('name', 'code')

# @admin.register(Treatment)
# class TreatmentAdmin(admin.ModelAdmin):
#     list_display = ('code', 'name', 'category', 'base_price', 'total_price', 'is_active')
#     list_filter = ('category', 'is_active', 'difficulty')
#     search_fields = ('code', 'name', 'description')
#     readonly_fields = ('doctor_fee', 'tax_amount', 'total_price', 'duration_display')
#     fieldsets = (
#         ('Basic Info', {
#             'fields': ('code', 'name', 'category', 'description')
#         }),
#         ('Pricing', {
#             'fields': ('base_price', 'doctor_fee_percentage', 'tax_percentage', 
#                       'doctor_fee', 'tax_amount', 'total_price')
#         }),
#         ('Procedure Details', {
#             'fields': ('difficulty', 'duration_value', 'duration_unit', 
#                       'duration_display', 'procedure_steps', 'materials_required', 
#                       'precautions'),
#             'classes': ('collapse',)
#         }),
#         ('Status', {
#             'fields': ('is_active', 'requires_lab', 'lab_days')
#         }),
#     )

# class TreatmentPlanItemInline(admin.TabularInline):
#     model = TreatmentPlanItem
#     extra = 1
#     raw_id_fields = ('treatment', 'scheduled_visit')
#     readonly_fields = ('actual_amount',)

# @admin.register(TreatmentPlan)
# class TreatmentPlanAdmin(admin.ModelAdmin):
#     list_display = ('plan_id', 'patient', 'doctor', 'status', 'final_amount', 'paid_amount', 'balance_amount')
#     list_filter = ('status', 'doctor')
#     search_fields = ('plan_id', 'patient__user__full_name', 'name')
#     readonly_fields = ('plan_id', 'total_estimated_amount', 'discount_amount', 
#                       'final_amount', 'balance_amount', 'is_paid', 'progress_percentage')
#     raw_id_fields = ('patient', 'doctor')
#     inlines = [TreatmentPlanItemInline]
    
#     fieldsets = (
#         ('Basic Info', {
#             'fields': ('plan_id', 'patient', 'doctor', 'name', 'status')
#         }),
#         ('Financial', {
#             'fields': ('total_estimated_amount', 'discount_percentage', 'discount_amount', 
#                       'final_amount', 'paid_amount', 'balance_amount', 'is_paid')
#         }),
#         ('Timeline', {
#             'fields': ('estimated_start_date', 'estimated_end_date', 
#                       'actual_start_date', 'actual_end_date')
#         }),
#         ('Clinical Notes', {
#             'fields': ('diagnosis', 'treatment_goals', 'notes'),
#             'classes': ('collapse',)
#         }),
#         ('Progress', {
#             'fields': ('progress_percentage',),
#             'classes': ('collapse',)
#         }),
#     )

# @admin.register(TreatmentPlanItem)
# class TreatmentPlanItemAdmin(admin.ModelAdmin):
#     list_display = ('treatment_plan', 'visit_number', 'treatment', 'status', 'scheduled_date', 'is_paid')
#     list_filter = ('status', 'is_paid')
#     search_fields = ('treatment_plan__plan_id', 'treatment__name')
#     raw_id_fields = ('treatment_plan', 'treatment', 'scheduled_visit')

from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.shortcuts import redirect

from .models import (
    TreatmentCategory, Treatment, ToothChart,
    TreatmentPlan, TreatmentPlanItem, TreatmentNote,
    TreatmentTemplate, TemplateTreatment
)


# ===========================================
# INLINE ADMIN CLASSES
# ===========================================
class TreatmentPlanItemInline(admin.TabularInline):
    """Inline for treatment plan items"""
    model = TreatmentPlanItem
    extra = 0
    readonly_fields = ['duration_minutes', 'doctor_commission']
    fields = [
        'treatment', 'visit_number', 'order', 'status', 'phase',
        'scheduled_date', 'actual_amount', 'is_paid', 'duration_minutes',
        'doctor_commission'
    ]
    raw_id_fields = ['treatment', 'scheduled_visit', 'performed_by']


class TreatmentNoteInline(admin.TabularInline):
    """Inline for treatment notes"""
    model = TreatmentNote
    extra = 0
    fields = ['note_type', 'content', 'is_critical', 'created_by', 'created_at']
    readonly_fields = ['created_by', 'created_at']


class TemplateTreatmentInline(admin.TabularInline):
    """Inline for template treatments"""
    model = TemplateTreatment
    extra = 0
    fields = ['treatment', 'order', 'visit_number']


# ===========================================
# CUSTOM FILTERS
# ===========================================
class TreatmentCategoryFilter(SimpleListFilter):
    """Filter treatments by category"""
    title = 'Category'
    parameter_name = 'category'

    def lookups(self, request, model_admin):
        categories = TreatmentCategory.objects.filter(is_active=True)
        return [(cat.id, cat.name) for cat in categories]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(category_id=self.value())
        return queryset


class TreatmentPlanStatusFilter(SimpleListFilter):
    """Filter treatment plans by status"""
    title = 'Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return TreatmentPlan.STATUS_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class TreatmentPlanItemStatusFilter(SimpleListFilter):
    """Filter treatment plan items by status"""
    title = 'Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return TreatmentPlanItem.STATUS_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


# ===========================================
# CUSTOM ACTIONS
# ===========================================
@admin.action(description='Mark selected categories as active')
def make_category_active(modeladmin, request, queryset):
    queryset.update(is_active=True)
    modeladmin.message_user(request, f'{queryset.count()} categories marked as active.')


@admin.action(description='Mark selected categories as inactive')
def make_category_inactive(modeladmin, request, queryset):
    queryset.update(is_active=False)
    modeladmin.message_user(request, f'{queryset.count()} categories marked as inactive.')


@admin.action(description='Mark selected treatments as active')
def make_treatment_active(modeladmin, request, queryset):
    queryset.update(is_active=True)
    modeladmin.message_user(request, f'{queryset.count()} treatments marked as active.')


@admin.action(description='Mark selected treatments as inactive')
def make_treatment_inactive(modeladmin, request, queryset):
    queryset.update(is_active=False)
    modeladmin.message_user(request, f'{queryset.count()} treatments marked as inactive.')


@admin.action(description='Mark selected treatments as popular')
def make_treatment_popular(modeladmin, request, queryset):
    queryset.update(is_popular=True)
    modeladmin.message_user(request, f'{queryset.count()} treatments marked as popular.')


@admin.action(description='Mark selected treatment plans as in progress')
def start_treatment_plans(modeladmin, request, queryset):
    updated = queryset.filter(status__in=['ACCEPTED', 'CONTRACT_SIGNED']).update(status='IN_PROGRESS')
    modeladmin.message_user(request, f'{updated} treatment plans started.')


@admin.action(description='Mark selected treatment plans as completed')
def complete_treatment_plans(modeladmin, request, queryset):
    updated = queryset.filter(status='IN_PROGRESS').update(
        status='COMPLETED',
        actual_end_date=timezone.now().date()
    )
    modeladmin.message_user(request, f'{updated} treatment plans completed.')


@admin.action(description='Generate invoice for selected plans')
def generate_invoice(modeladmin, request, queryset):
    # This would typically redirect to an invoice generation view
    # For now, we'll just show a message
    modeladmin.message_user(
        request, 
        f'Invoice generation would be triggered for {queryset.count()} plans.'
    )


# ===========================================
# ADMIN CLASSES
# ===========================================
@admin.register(TreatmentCategory)
class TreatmentCategoryAdmin(admin.ModelAdmin):
    """Admin for TreatmentCategory"""
    
    list_display = [
        'name', 'code', 'order', 'is_active', 'treatment_count',
        'display_in_portal', 'created_at'
    ]
    
    list_filter = ['is_active', 'display_in_portal', 'created_at']
    
    search_fields = ['name', 'code', 'description']
    
    list_editable = ['order', 'is_active', 'display_in_portal']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description', 'order')
        }),
        ('Display Settings', {
            'fields': ('icon', 'color', 'display_in_portal')
        }),
        ('SEO & Analytics', {
            'fields': ('keywords', 'is_active')
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
    actions = [make_category_active, make_category_inactive]
    
    def treatment_count(self, obj):
        return obj.treatments.count()
    treatment_count.short_description = 'Treatments'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Treatment)
class TreatmentAdmin(admin.ModelAdmin):
    """Admin for Treatment"""
    
    list_display = [
        'code', 'name', 'category', 'base_price', 'total_price',
        'duration_display', 'difficulty', 'is_active', 'is_popular'
    ]
    
    list_filter = [
        TreatmentCategoryFilter, 'is_active', 'is_popular', 'difficulty',
        'requires_lab', 'display_in_portal'
    ]
    
    search_fields = [
        'code', 'name', 'display_name', 'description',
        'procedure_steps', 'category__name'
    ]
    
    list_editable = ['is_active', 'is_popular', 'base_price']
    
    readonly_fields = [
        'doctor_fee', 'assistant_fee', 'tax_amount', 'total_price',
        'clinic_cost', 'duration_display', 'popularity_score',
        'created_at', 'updated_at', 'created_by', 'updated_by'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'code', 'name', 'display_name', 'category',
                'description', 'procedure_steps'
            )
        }),
        ('Pricing & Financials', {
            'fields': (
                'base_price', 'min_price', 'max_price',
                'doctor_fee_percentage', 'assistant_fee_percentage',
                'tax_percentage', 'doctor_fee', 'assistant_fee',
                'tax_amount', 'total_price', 'clinic_cost'
            )
        }),
        ('Operational Details', {
            'fields': (
                'difficulty', 'duration_value', 'duration_unit',
                'duration_display', 'num_sessions', 'recovery_days'
            )
        }),
        ('Clinical Information', {
            'fields': (
                'contraindications', 'post_op_instructions',
                'success_rate', 'medical_conditions'
            )
        }),
        ('Patient Demographics', {
            'fields': (
                'suitable_for_age', 'suitable_for_gender'
            )
        }),
        ('Inventory & Lab', {
            'fields': (
                'requires_lab', 'lab_type', 'lab_days',
                'materials_required', 'equipment_required',
                'inventory_items'
            )
        }),
        ('Status & Display', {
            'fields': (
                'is_active', 'is_popular', 'popularity_score',
                'order', 'display_in_portal', 'version'
            )
        }),
    )
    
    actions = [
        make_treatment_active, make_treatment_inactive,
        make_treatment_popular
    ]
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ToothChart)
class ToothChartAdmin(admin.ModelAdmin):
    """Admin for ToothChart"""
    
    list_display = [
        'fdi_notation', 'universal_notation', 'tooth_number',
        'quadrant', 'name', 'type', 'is_active'
    ]
    
    list_filter = ['quadrant', 'type', 'is_active']
    
    search_fields = [
        'fdi_notation', 'universal_notation', 'name',
        'tooth_number'
    ]
    
    list_editable = ['is_active']
    
    fieldsets = (
        ('Tooth Identification', {
            'fields': ('tooth_number', 'quadrant', 'fdi_notation', 'universal_notation')
        }),
        ('Tooth Information', {
            'fields': ('name', 'type', 'is_active')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('quadrant', 'tooth_number')


@admin.register(TreatmentPlan)
class TreatmentPlanAdmin(admin.ModelAdmin):
    """Admin for TreatmentPlan"""
    
    list_display = [
        'plan_id', 'patient_link', 'doctor_link', 'branch',
        'status', 'priority', 'total_estimated_amount', 'paid_amount',
        'balance_amount', 'progress_percentage', 'estimated_duration_days',
        'created_at'
    ]
    
    list_filter = [
        TreatmentPlanStatusFilter, 'priority', 'branch',
        'insurance_approved', 'created_at', 'estimated_start_date'
    ]
    
    search_fields = [
        'plan_id', 'patient__user__first_name', 'patient__user__last_name',
        'patient__patient_id', 'doctor__user__first_name',
        'doctor__user__last_name', 'name', 'diagnosis'
    ]
    
    readonly_fields = [
        'plan_id', 'balance_amount', 'is_paid', 'progress_percentage',
        'estimated_duration_days', 'discount_amount', 'final_amount',
        'created_at', 'updated_at', 'created_by', 'updated_by'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'plan_id', 'patient', 'doctor', 'branch', 'referred_by',
                'name', 'status', 'priority', 'version', 'parent_plan'
            )
        }),
        ('Financial Information', {
            'fields': (
                'total_estimated_amount', 'discount_percentage',
                'discount_amount', 'tax_amount', 'final_amount',
                'paid_amount', 'balance_amount', 'is_paid',
                'payment_plan', 'insurance_coverage',
                'insurance_approved', 'insurance_notes'
            )
        }),
        ('Timeline', {
            'fields': (
                'estimated_start_date', 'estimated_end_date',
                'actual_start_date', 'actual_end_date',
                'next_review_date', 'estimated_duration_days'
            )
        }),
        ('Clinical Information', {
            'fields': (
                'diagnosis', 'diagnosis_codes', 'treatment_goals',
                'clinical_notes', 'pre_op_instructions',
                'post_op_instructions', 'risks_and_complications',
                'dental_chart', 'progress_percentage'
            )
        }),
        ('Documents', {
            'fields': (
                'consent_form_signed', 'consent_form_url',
                'xray_images'
            )
        }),
        ('Analytics', {
            'fields': (
                'complexity_score', 'satisfaction_score'
            )
        }),
    )
    
    # inlines = [TreatmentPlanItemInline, TreatmentNoteInline]
    inlines = [TreatmentPlanItemInline]
    
    actions = [
        start_treatment_plans, complete_treatment_plans,
        generate_invoice
    ]
    
    def patient_link(self, obj):
        url = reverse('admin:patients_patient_change', args=[obj.patient.id])
        return format_html('<a href="{}">{}</a>', url, obj.patient)
    patient_link.short_description = 'Patient'
    patient_link.admin_order_field = 'patient'
    
    def doctor_link(self, obj):
        url = reverse('admin:doctors_doctor_change', args=[obj.doctor.id])
        return format_html('<a href="{}">{}</a>', url, obj.doctor.full_name)
    doctor_link.short_description = 'Doctor'
    doctor_link.admin_order_field = 'doctor'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TreatmentPlanItem)
class TreatmentPlanItemAdmin(admin.ModelAdmin):
    """Admin for TreatmentPlanItem"""
    
    list_display = [
        'treatment_plan', 'treatment', 'visit_number',
        'status', 'phase', 'scheduled_date', 'actual_amount',
        'is_paid', 'duration_minutes', 'performed_by_link'
    ]
    
    list_filter = [
        TreatmentPlanItemStatusFilter, 'phase',
        'follow_up_required', 'is_paid', 'scheduled_date'
    ]
    
    search_fields = [
        'treatment_plan__plan_id', 'treatment__name',
        'treatment__code', 'procedure_notes'
    ]
    
    readonly_fields = [
        'duration_minutes', 'doctor_commission',
        'created_at', 'updated_at', 'created_by', 'updated_by'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'treatment_plan', 'treatment', 'visit_number',
                'order', 'status', 'phase'
            )
        }),
        ('Scheduling', {
            'fields': (
                'scheduled_date', 'scheduled_visit', 'depends_on',
                'start_time', 'end_time', 'duration_minutes',
                'completed_date'
            )
        }),
        ('Financial', {
            'fields': (
                'actual_amount', 'discount_applied', 'is_paid',
                'payment_reference', 'doctor_commission'
            )
        }),
        ('Clinical Details', {
            'fields': (
                'tooth_number', 'surface', 'quadrant', 'tooth_condition',
                'materials_used', 'equipment_used', 'procedure_notes',
                'complications', 'anesthesia_type', 'anesthesia_amount'
            )
        }),
        ('Staff & Quality', {
            'fields': (
                'performed_by', 'assistant', 'quality_score',
                'patient_feedback'
            )
        }),
        ('Follow-up', {
            'fields': (
                'follow_up_required', 'follow_up_days',
                'follow_up_notes'
            )
        }),
    )
    
    raw_id_fields = [
        'treatment_plan', 'treatment', 'scheduled_visit',
        'performed_by', 'assistant', 'depends_on'
    ]
    
    def performed_by_link(self, obj):
        if obj.performed_by:
            url = reverse('admin:doctors_doctor_change', args=[obj.performed_by.id])
            return format_html('<a href="{}">{}</a>', url, obj.performed_by.full_name)
        return '-'
    performed_by_link.short_description = 'Performed By'
    performed_by_link.admin_order_field = 'performed_by'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TreatmentNote)
class TreatmentNoteAdmin(admin.ModelAdmin):
    """Admin for TreatmentNote"""
    
    list_display = [
        'treatment_plan_item', 'note_type', 'is_critical',
        'created_by', 'created_at'
    ]
    
    list_filter = ['note_type', 'is_critical', 'created_at']
    
    search_fields = ['content', 'treatment_plan_item__treatment__name']
    
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    
    fieldsets = (
        ('Note Information', {
            'fields': (
                'treatment_plan_item', 'note_type', 'content',
                'is_critical', 'attachments'
            )
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_by', 'updated_at')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TreatmentTemplate)
class TreatmentTemplateAdmin(admin.ModelAdmin):
    """Admin for TreatmentTemplate"""
    
    list_display = [
        'name', 'code', 'category', 'total_price',
        'treatment_count', 'is_active'
    ]
    
    list_filter = ['category', 'is_active']
    
    search_fields = ['name', 'code', 'description']
    
    inlines = [TemplateTreatmentInline]
    
    readonly_fields = [
        'total_price', 'created_at', 'updated_at',
        'created_by', 'updated_by'
    ]
    
    fieldsets = (
        ('Template Information', {
            'fields': ('name', 'code', 'description', 'category')
        }),
        ('Financial', {
            'fields': ('total_price',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def treatment_count(self, obj):
        return obj.treatments.count()
    treatment_count.short_description = 'Treatments'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Optional: Register TemplateTreatment if you want it separately
@admin.register(TemplateTreatment)
class TemplateTreatmentAdmin(admin.ModelAdmin):
    """Admin for TemplateTreatment"""
    
    list_display = ['template', 'treatment', 'order', 'visit_number']
    
    list_filter = ['template', 'visit_number']
    
    search_fields = ['template__name', 'treatment__name']
    
    fieldsets = (
        ('Template Treatment Mapping', {
            'fields': ('template', 'treatment', 'order', 'visit_number')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('template', 'treatment')