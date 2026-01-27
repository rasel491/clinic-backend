# # apps/billing/admin.py (Simple version)

# from django.contrib import admin
# from django.core.exceptions import PermissionDenied
# from .models import Invoice, InvoiceItem, DiscountPolicy, AppliedDiscount

# class InvoiceItemInline(admin.TabularInline):
#     model = InvoiceItem
#     extra = 1
#     readonly_fields = ('total_amount', 'tax_amount', 'discount_amount', 'doctor_commission_amount')
#     raw_id_fields = ('treatment', 'treatment_plan_item', 'doctor')

# class AppliedDiscountInline(admin.TabularInline):
#     model = AppliedDiscount
#     extra = 0
#     readonly_fields = ('discount_amount', 'approved_at', 'approved_by', 'is_reversed')
#     raw_id_fields = ('discount_policy', 'approved_by', 'reversed_by')


# class EODReadOnlyAdmin(admin.ModelAdmin):

#     def has_change_permission(self, request, obj=None):
#         if obj and obj.branch.is_eod_locked:
#             return False
#         return super().has_change_permission(request, obj)

#     def has_delete_permission(self, request, obj=None):
#         if obj and obj.branch.is_eod_locked:
#             return False
#         return super().has_delete_permission(request, obj)

#     def save_model(self, request, obj, form, change):
#         if obj.branch.is_eod_locked:
#             raise PermissionDenied("EOD locked: admin modification forbidden")
#         super().save_model(request, obj, form, change)

# @admin.register(Invoice)
# class InvoiceAdmin(EODReadOnlyAdmin):
#     list_display = ("invoice_number", "branch", "status", "total_amount", "is_locked")
#     readonly_fields = ("invoice_number", "total_amount", "balance_amount")

# # @admin.register(Invoice)
# # class InvoiceAdmin(admin.ModelAdmin):
# #     list_display = ('invoice_number', 'patient', 'branch', 'status', 'total_amount', 
# #                    'paid_amount', 'balance_amount', 'invoice_date', 'is_locked')
# #     list_filter = ('status', 'branch', 'is_locked', 'is_final', 'invoice_date')
# #     search_fields = ('invoice_number', 'patient__user__full_name', 'visit__visit_id')
# #     readonly_fields = ('invoice_number', 'subtotal', 'discount_amount', 'tax_amount', 
# #                       'total_amount', 'balance_amount', 'is_paid', 'is_overdue', 'can_modify')
# #     raw_id_fields = ('branch', 'visit', 'patient', 'override_by')
# #     inlines = [InvoiceItemInline, AppliedDiscountInline]
    
# #     fieldsets = (
# #         ('Basic Info', {
# #             'fields': ('invoice_number', 'branch', 'visit', 'patient', 'status')
# #         }),
# #         ('Dates', {
# #             'fields': ('invoice_date', 'due_date', 'payment_due_date', 'last_payment_date')
# #         }),
# #         ('Financials', {
# #             'fields': ('subtotal', 'discount_percentage', 'discount_amount', 
# #                       'tax_percentage', 'tax_amount', 'total_amount', 
# #                       'paid_amount', 'balance_amount')
# #         }),
# #         ('Control', {
# #             'fields': ('is_locked', 'is_final', 'can_modify', 'eod_lock')
# #         }),
# #         ('Override', {
# #             'fields': ('override_reason', 'override_by'),
# #             'classes': ('collapse',)
# #         }),
# #         ('Status', {
# #             'fields': ('is_paid', 'is_overdue'),
# #             'classes': ('collapse',)
# #         }),
# #     )
    
# #     def has_delete_permission(self, request, obj=None):
# #         # Prevent deletion of paid or locked invoices
# #         if obj and (obj.is_locked or obj.status == 'PAID'):
# #             return False
# #         return super().has_delete_permission(request, obj)

# @admin.register(InvoiceItem)
# class InvoiceItemAdmin(admin.ModelAdmin):
#     list_display = ('invoice', 'description', 'item_type', 'quantity', 'unit_price', 'total_amount')
#     list_filter = ('item_type',)
#     search_fields = ('invoice__invoice_number', 'description', 'code')
#     readonly_fields = ('total_amount', 'tax_amount', 'discount_amount', 'doctor_commission_amount')
#     raw_id_fields = ('invoice', 'treatment', 'treatment_plan_item', 'doctor')

# @admin.register(DiscountPolicy)
# class DiscountPolicyAdmin(admin.ModelAdmin):
#     list_display = ('code', 'name', 'discount_type', 'applicable_to', 'is_active', 
#                    'valid_from', 'valid_until', 'used_count')
#     list_filter = ('discount_type', 'applicable_to', 'is_active', 'requires_approval')
#     search_fields = ('code', 'name')
#     readonly_fields = ('used_count',)

# @admin.register(AppliedDiscount)
# class AppliedDiscountAdmin(admin.ModelAdmin):
#     list_display = ('invoice', 'discount_policy', 'discount_amount', 'approved_by', 
#                    'is_reversed', 'created_at')
#     list_filter = ('is_reversed', 'discount_policy')
#     search_fields = ('invoice__invoice_number', 'discount_policy__code')
#     readonly_fields = ('discount_amount', 'original_amount', 'approved_at', 'reversed_at')
#     raw_id_fields = ('invoice', 'discount_policy', 'approved_by', 'reversed_by')


# from django.contrib import admin
# from django.utils.html import format_html
# from django.urls import reverse
# from django.utils import timezone
# from django.db.models import Sum, Count, Q
# from django.contrib import messages
# from django.http import HttpResponseRedirect

# from .models import Invoice, InvoiceItem, DiscountPolicy, AppliedDiscount


# # ===========================================
# # INLINE ADMIN CLASSES
# # ===========================================
# class InvoiceItemInline(admin.TabularInline):
#     """Inline for invoice items"""
#     model = InvoiceItem
#     extra = 0
#     readonly_fields = ['total_amount', 'doctor_commission_amount']
#     fields = [
#         'item_type', 'description', 'unit_price', 'quantity',
#         'total_amount', 'doctor', 'doctor_commission_amount'
#     ]
#     raw_id_fields = ['treatment', 'doctor']


# class AppliedDiscountInline(admin.TabularInline):
#     """Inline for applied discounts"""
#     model = AppliedDiscount
#     extra = 0
#     fields = ['discount_policy', 'discount_amount', 'approved_by', 'approved_at', 'is_reversed']
#     readonly_fields = ['approved_by', 'approved_at', 'is_reversed']
#     raw_id_fields = ['discount_policy', 'approved_by']  # Add this
    
#     def has_add_permission(self, request, obj=None):
#         """Disable adding discounts through inline - use main form"""
#         return False
    
#     def has_change_permission(self, request, obj=None):
#         """Disable editing through inline"""
#         return False

# # ===========================================
# # CUSTOM FILTERS
# # ===========================================
# class InvoiceStatusFilter(admin.SimpleListFilter):
#     """Filter invoices by status"""
#     title = 'Status'
#     parameter_name = 'status'
    
#     def lookups(self, request, model_admin):
#         return Invoice.STATUS_CHOICES
    
#     def queryset(self, request, queryset):
#         if self.value():
#             return queryset.filter(status=self.value())
#         return queryset


# class OverdueFilter(admin.SimpleListFilter):
#     """Filter for overdue invoices"""
#     title = 'Overdue'
#     parameter_name = 'overdue'
    
#     def lookups(self, request, model_admin):
#         return [
#             ('overdue', 'Overdue'),
#             ('not_overdue', 'Not Overdue'),
#         ]
    
#     def queryset(self, request, queryset):
#         if self.value() == 'overdue':
#             return queryset.filter(status='OVERDUE')
#         elif self.value() == 'not_overdue':
#             return queryset.exclude(status='OVERDUE')
#         return queryset


# # ===========================================
# # CUSTOM ACTIONS
# # ===========================================
# @admin.action(description='Mark selected invoices as paid')
# def mark_as_paid(modeladmin, request, queryset):
#     """Mark invoices as paid"""
#     for invoice in queryset.filter(status__in=['UNPAID', 'PARTIALLY_PAID']):
#         invoice.paid_amount = invoice.total_amount
#         invoice.status = 'PAID'
#         invoice.is_final = True
#         invoice.save()
    
#     modeladmin.message_user(request, f'{queryset.count()} invoices marked as paid.')


# @admin.action(description='Send payment reminders')
# def send_payment_reminders(modeladmin, request, queryset):
#     """Send payment reminders for selected invoices"""
#     overdue_invoices = queryset.filter(status='OVERDUE')
#     unpaid_invoices = queryset.filter(status__in=['UNPAID', 'PARTIALLY_PAID'])
    
#     # In a real implementation, this would send emails/SMS
#     modeladmin.message_user(
#         request,
#         f'Payment reminders would be sent for {overdue_invoices.count()} overdue '
#         f'and {unpaid_invoices.count()} unpaid invoices.'
#     )


# @admin.action(description='Generate reports for selected invoices')
# def generate_reports(modeladmin, request, queryset):
#     """Generate reports for selected invoices"""
#     # This would typically redirect to a report generation view
#     modeladmin.message_user(
#         request,
#         f'Reports would be generated for {queryset.count()} invoices.'
#     )


# # ===========================================
# # ADMIN CLASSES
# # ===========================================
# @admin.register(Invoice)
# class InvoiceAdmin(admin.ModelAdmin):
#     """Admin for Invoice"""
    
#     list_display = [
#         'invoice_number', 'patient_link', 'branch', 'invoice_date',
#         'due_date', 'status', 'total_amount', 'paid_amount',
#         'balance_amount', 'is_overdue', 'is_locked'
#     ]
    
#     list_filter = [
#         InvoiceStatusFilter, OverdueFilter, 'branch',
#         'is_locked', 'is_final', 'payment_terms', 'invoice_date'
#     ]
    
#     search_fields = [
#         'invoice_number', 'patient__user__first_name',
#         'patient__user__last_name', 'patient__patient_id'
#     ]
    
#     readonly_fields = [
#         'invoice_number', 'balance_amount', 'is_paid', 'is_overdue',
#         'can_modify', 'created_at', 'updated_at', 'created_by', 'updated_by',
#         'discount_amount', 'tax_amount', 'total_amount'
#     ]
    
#     fieldsets = (
#         ('Basic Information', {
#             'fields': (
#                 'invoice_number', 'patient', 'branch', 'visit',
#                 'invoice_date', 'due_date', 'status'
#             )
#         }),
#         ('Financial Information', {
#             'fields': (
#                 'subtotal', 'discount_percentage', 'discount_amount',
#                 'tax_percentage', 'tax_amount', 'total_amount',
#                 'paid_amount', 'advance_paid', 'balance_amount',
#                 'late_fee_percentage', 'late_fee_amount'
#             )
#         }),
#         ('Insurance & Payment', {
#             'fields': (
#                 'insurance_claim_amount', 'insurance_claim_status',
#                 'payment_terms', 'payment_due_date', 'last_payment_date'
#             )
#         }),
#         ('Referral & Notes', {
#             'fields': (
#                 'referred_by', 'referral_commission',
#                 'notes', 'internal_notes'
#             )
#         }),
#         ('Status & Control', {
#             'fields': (
#                 'is_locked', 'is_final', 'override_reason', 'override_by',
#                 'is_paid', 'is_overdue', 'can_modify'
#             )
#         }),
#     )
    
#     inlines = [InvoiceItemInline]
    
#     actions = [mark_as_paid, send_payment_reminders, generate_reports]
    
#     def patient_link(self, obj):
#         url = reverse('admin:patients_patient_change', args=[obj.patient.id])
#         return format_html('<a href="{}">{}</a>', url, obj.patient)
#     patient_link.short_description = 'Patient'
#     patient_link.admin_order_field = 'patient'
    
#     def is_overdue(self, obj):
#         return obj.is_overdue
#     is_overdue.boolean = True
#     is_overdue.short_description = 'Overdue'
    
#     def save_model(self, request, obj, form, change):
#         if not obj.pk:
#             obj.created_by = request.user
#         obj.updated_by = request.user
#         super().save_model(request, obj, form, change)
    
#     def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
#         """Add custom context for invoice form"""
#         extra_context = extra_context or {}
        
#         if object_id:
#             invoice = Invoice.objects.get(id=object_id)
#             extra_context['can_modify'] = invoice.can_modify
        
#         return super().changeform_view(request, object_id, form_url, extra_context)


# @admin.register(InvoiceItem)
# class InvoiceItemAdmin(admin.ModelAdmin):
#     """Admin for InvoiceItem"""
    
#     list_display = [
#         'invoice', 'item_type', 'description', 'unit_price',
#         'quantity', 'total_amount', 'doctor', 'doctor_commission_amount'
#     ]
    
#     list_filter = ['item_type', 'invoice__branch', 'is_taxable']
    
#     search_fields = [
#         'description', 'code', 'invoice__invoice_number',
#         'treatment__name', 'doctor__user__first_name'
#     ]
    
#     readonly_fields = [
#         'total_amount', 'doctor_commission_amount',
#         'created_at', 'updated_at', 'created_by', 'updated_by'
#     ]
    
#     fieldsets = (
#         ('Item Information', {
#             'fields': (
#                 'invoice', 'item_type', 'description', 'code',
#                 'treatment', 'treatment_plan_item'
#             )
#         }),
#         ('Pricing', {
#             'fields': (
#                 'unit_price', 'quantity', 'discount_percentage',
#                 'discount_amount', 'tax_percentage', 'tax_amount',
#                 'total_amount'
#             )
#         }),
#         ('Doctor Commission', {
#             'fields': (
#                 'doctor', 'doctor_commission_percentage',
#                 'doctor_commission_amount'
#             )
#         }),
#         ('Additional Information', {
#             'fields': (
#                 'is_taxable', 'hsn_code', 'batch_number', 'expiry_date'
#             )
#         }),
#     )
    
#     raw_id_fields = ['invoice', 'treatment', 'doctor']
    
#     def save_model(self, request, obj, form, change):
#         if not obj.pk:
#             obj.created_by = request.user
#         obj.updated_by = request.user
#         super().save_model(request, obj, form, change)


# @admin.register(DiscountPolicy)
# class DiscountPolicyAdmin(admin.ModelAdmin):
#     """Admin for DiscountPolicy"""
    
#     list_display = [
#         'name', 'code', 'discount_type', 'get_discount_value',
#         'applicable_to', 'is_active', 'valid_from', 'valid_until',
#         'usage_limit', 'used_count'
#     ]
    
#     list_filter = ['is_active', 'discount_type', 'applicable_to', 'requires_approval']
    
#     search_fields = ['name', 'code', 'description']
    
#     list_editable = ['is_active']
    
#     readonly_fields = ['used_count', 'created_at', 'updated_at', 'created_by', 'updated_by']
    
#     fieldsets = (
#         ('Policy Information', {
#             'fields': ('name', 'code', 'description')
#         }),
#         ('Discount Details', {
#             'fields': ('discount_type', 'percentage', 'fixed_amount')
#         }),
#         ('Applicability', {
#             'fields': ('applicable_to', 'minimum_amount', 'maximum_discount')
#         }),
#         ('Validity', {
#             'fields': ('valid_from', 'valid_until', 'is_active')
#         }),
#         ('Approval & Usage', {
#             'fields': ('requires_approval', 'min_approval_level', 'usage_limit', 'used_count')
#         }),
#     )
    
#     def get_discount_value(self, obj):
#         if obj.discount_type == 'PERCENTAGE':
#             return f'{obj.percentage}%'
#         elif obj.discount_type == 'FIXED':
#             return f'₹{obj.fixed_amount}'
#         elif obj.discount_type == 'FREE':
#             return 'FREE'
#         return '-'
#     get_discount_value.short_description = 'Discount Value'
    
#     def save_model(self, request, obj, form, change):
#         if not obj.pk:
#             obj.created_by = request.user
#         obj.updated_by = request.user
#         super().save_model(request, obj, form, change)


# @admin.register(AppliedDiscount)
# class AppliedDiscountAdmin(admin.ModelAdmin):
#     """Admin for AppliedDiscount"""
    
#     list_display = [
#         'invoice', 'discount_policy', 'discount_amount',
#         'approved_by', 'approved_at', 'is_reversed'
#     ]
    
#     list_filter = ['is_reversed', 'discount_policy', 'approved_at']
    
#     search_fields = [
#         'invoice__invoice_number', 'discount_policy__name',
#         'discount_policy__code', 'approval_notes'
#     ]
    
#     readonly_fields = [
#         'created_at', 'updated_at', 'created_by', 'updated_by'
#     ]
    
#     fieldsets = (
#         ('Discount Application', {
#             'fields': ('invoice', 'discount_policy')
#         }),
#         ('Discount Details', {
#             'fields': ('discount_amount', 'original_amount')
#         }),
#         ('Approval', {
#             'fields': ('approved_by', 'approved_at', 'approval_notes')
#         }),
#         ('Reversal', {
#             'fields': ('is_reversed', 'reversed_by', 'reversed_at', 'reversal_reason')
#         }),
#     )
    
#     raw_id_fields = ['invoice', 'discount_policy', 'approved_by', 'reversed_by']
    
#     def save_model(self, request, obj, form, change):
#         if not obj.pk:
#             obj.created_by = request.user
#         obj.updated_by = request.user
#         super().save_model(request, obj, form, change)

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count
from .models import Invoice, InvoiceItem, DiscountPolicy, AppliedDiscount


# ===========================================
# SIMPLE INLINE CLASSES
# ===========================================
class InvoiceItemInline(admin.TabularInline):
    """Inline for invoice items"""
    model = InvoiceItem
    extra = 0
    readonly_fields = ['total_amount', 'doctor_commission_amount']
    fields = ['item_type', 'description', 'unit_price', 'quantity', 'total_amount']
    can_delete = True
    show_change_link = True


# ===========================================
# SIMPLE FILTERS
# ===========================================
class StatusFilter(admin.SimpleListFilter):
    """Filter by status"""
    title = 'Status'
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        status_choices = []
        if model_admin.model == Invoice:
            status_choices = Invoice.STATUS_CHOICES
        elif model_admin.model == DiscountPolicy:
            return [('active', 'Active'), ('inactive', 'Inactive')]
        return status_choices
    
    def queryset(self, request, queryset):
        if self.value():
            if hasattr(queryset.model, 'status'):
                return queryset.filter(status=self.value())
            elif hasattr(queryset.model, 'is_active'):
                if self.value() == 'active':
                    return queryset.filter(is_active=True)
                elif self.value() == 'inactive':
                    return queryset.filter(is_active=False)
        return queryset


# ===========================================
# CUSTOM ACTIONS
# ===========================================
@admin.action(description='Mark selected invoices as paid')
def mark_as_paid(modeladmin, request, queryset):
    updated = queryset.filter(status__in=['DRAFT', 'ISSUED', 'UNPAID', 'PARTIALLY_PAID']).update(
        status='PAID',
        is_final=True
    )
    modeladmin.message_user(request, f'{updated} invoices marked as paid.')


@admin.action(description='Mark selected as active')
def make_active(modeladmin, request, queryset):
    queryset.update(is_active=True)
    modeladmin.message_user(request, f'{queryset.count()} items marked as active.')


@admin.action(description='Mark selected as inactive')
def make_inactive(modeladmin, request, queryset):
    queryset.update(is_active=False)
    modeladmin.message_user(request, f'{queryset.count()} items marked as inactive.')


# ===========================================
# ADMIN CLASSES
# ===========================================
@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Admin for Invoice"""
    
    list_display = [
        'invoice_number', 'patient_display', 'branch', 'invoice_date',
        'due_date', 'status_badge', 'total_amount', 'paid_amount',
        'balance_amount', 'is_locked_display'
    ]
    
    list_filter = [StatusFilter, 'branch', 'is_locked', 'payment_terms']
    
    search_fields = [
        'invoice_number', 'patient__user__first_name',
        'patient__user__last_name', 'patient__patient_id'
    ]
    
    readonly_fields = [
        'invoice_number', 'balance_amount', 'is_paid', 'is_overdue',
        'can_modify', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('invoice_number', 'patient', 'branch', 'visit', 'invoice_date', 'due_date', 'status')
        }),
        ('Financial Information', {
            'fields': ('subtotal', 'discount_percentage', 'discount_amount', 'tax_percentage', 
                      'tax_amount', 'total_amount', 'paid_amount', 'advance_paid', 'balance_amount')
        }),
        ('Status', {
            'fields': ('is_locked', 'is_final', 'is_paid', 'is_overdue', 'can_modify')
        }),
        ('Notes', {
            'fields': ('notes', 'internal_notes')
        }),
    )
    
    inlines = [InvoiceItemInline]
    actions = [mark_as_paid]
    
    def patient_display(self, obj):
        return str(obj.patient)
    patient_display.short_description = 'Patient'
    patient_display.admin_order_field = 'patient'
    
    def status_badge(self, obj):
        colors = {
            'DRAFT': 'gray',
            'ISSUED': 'blue',
            'UNPAID': 'orange',
            'PARTIALLY_PAID': 'yellow',
            'PAID': 'green',
            'OVERDUE': 'red',
            'VOID': 'black',
            'CANCELLED': 'darkred',
            'REFUNDED': 'purple',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 10px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def is_locked_display(self, obj):
        return obj.is_locked
    is_locked_display.boolean = True
    is_locked_display.short_description = 'Locked'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    """Admin for InvoiceItem"""
    
    list_display = [
        'id', 'invoice_link', 'item_type', 'description',
        'unit_price', 'quantity', 'total_amount'
    ]
    
    list_filter = ['item_type', 'is_taxable']
    
    search_fields = [
        'description', 'code', 'invoice__invoice_number'
    ]
    
    readonly_fields = ['total_amount', 'doctor_commission_amount']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('invoice', 'item_type', 'description', 'code')
        }),
        ('Links', {
            'fields': ('treatment', 'treatment_plan_item', 'doctor')
        }),
        ('Pricing', {
            'fields': ('unit_price', 'quantity', 'discount_percentage', 
                      'tax_percentage', 'total_amount', 'is_taxable', 'hsn_code')
        }),
        ('Doctor Commission', {
            'fields': ('doctor_commission_percentage', 'doctor_commission_amount')
        }),
    )
    
    def invoice_link(self, obj):
        url = reverse('admin:billing_invoice_change', args=[obj.invoice.id])
        return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
    invoice_link.short_description = 'Invoice'
    invoice_link.admin_order_field = 'invoice'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DiscountPolicy)
class DiscountPolicyAdmin(admin.ModelAdmin):
    """Admin for DiscountPolicy"""
    
    list_display = [
        'name', 'code', 'discount_type_display', 'applicable_to',
        'valid_from', 'valid_until', 'is_active_badge', 'used_count'
    ]
    
    list_filter = [StatusFilter, 'discount_type', 'applicable_to', 'requires_approval']
    
    search_fields = ['name', 'code', 'description']
    
    # list_editable = ['is_active']
    
    readonly_fields = ['used_count', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'description', 'is_active')
        }),
        ('Discount Details', {
            'fields': ('discount_type', 'percentage', 'fixed_amount')
        }),
        ('Applicability', {
            'fields': ('applicable_to', 'minimum_amount', 'maximum_discount')
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_until')
        }),
        ('Approval & Usage', {
            'fields': ('requires_approval', 'min_approval_level', 'usage_limit', 'used_count')
        }),
    )
    
    actions = [make_active, make_inactive]
    
    def discount_type_display(self, obj):
        if obj.discount_type == 'PERCENTAGE':
            return f'{obj.percentage}%'
        elif obj.discount_type == 'FIXED':
            return f'₹{obj.fixed_amount}'
        return obj.get_discount_type_display()
    discount_type_display.short_description = 'Discount'
    
    def is_active_badge(self, obj):
        color = 'green' if obj.is_active else 'red'
        text = 'Active' if obj.is_active else 'Inactive'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 10px;">{}</span>',
            color, text
        )
    is_active_badge.short_description = 'Status'
    is_active_badge.admin_order_field = 'is_active'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AppliedDiscount)
class AppliedDiscountAdmin(admin.ModelAdmin):
    """Admin for AppliedDiscount"""
    
    list_display = [
        'id', 'invoice_link', 'discount_policy', 'discount_amount',
        'approved_by_display', 'approved_at', 'is_reversed_badge'
    ]
    
    list_filter = ['is_reversed', 'discount_policy']
    
    search_fields = [
        'invoice__invoice_number', 'discount_policy__name',
        'discount_policy__code'
    ]
    
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Application', {
            'fields': ('invoice', 'discount_policy')
        }),
        ('Discount Details', {
            'fields': ('discount_amount', 'original_amount')
        }),
        ('Approval', {
            'fields': ('approved_by', 'approved_at', 'approval_notes')
        }),
        ('Reversal', {
            'fields': ('is_reversed', 'reversed_by', 'reversed_at', 'reversal_reason')
        }),
    )
    
    def invoice_link(self, obj):
        url = reverse('admin:billing_invoice_change', args=[obj.invoice.id])
        return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
    invoice_link.short_description = 'Invoice'
    invoice_link.admin_order_field = 'invoice'
    
    def approved_by_display(self, obj):
        return obj.approved_by.get_full_name() if obj.approved_by else '-'
    approved_by_display.short_description = 'Approved By'
    
    def is_reversed_badge(self, obj):
        if obj.is_reversed:
            return format_html(
                '<span style="background-color: red; color: white; padding: 2px 8px; border-radius: 10px;">Reversed</span>'
            )
        return format_html(
            '<span style="background-color: green; color: white; padding: 2px 8px; border-radius: 10px;">Active</span>'
        )
    is_reversed_badge.short_description = 'Status'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)