# apps/billing/admin.py (Simple version)

from django.contrib import admin
from .models import Invoice, InvoiceItem, DiscountPolicy, AppliedDiscount

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    readonly_fields = ('total_amount', 'tax_amount', 'discount_amount', 'doctor_commission_amount')
    raw_id_fields = ('treatment', 'treatment_plan_item', 'doctor')

class AppliedDiscountInline(admin.TabularInline):
    model = AppliedDiscount
    extra = 0
    readonly_fields = ('discount_amount', 'approved_at', 'approved_by', 'is_reversed')
    raw_id_fields = ('discount_policy', 'approved_by', 'reversed_by')

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'patient', 'branch', 'status', 'total_amount', 
                   'paid_amount', 'balance_amount', 'invoice_date', 'is_locked')
    list_filter = ('status', 'branch', 'is_locked', 'is_final', 'invoice_date')
    search_fields = ('invoice_number', 'patient__user__full_name', 'visit__visit_id')
    readonly_fields = ('invoice_number', 'subtotal', 'discount_amount', 'tax_amount', 
                      'total_amount', 'balance_amount', 'is_paid', 'is_overdue', 'can_modify')
    raw_id_fields = ('branch', 'visit', 'patient', 'override_by')
    inlines = [InvoiceItemInline, AppliedDiscountInline]
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('invoice_number', 'branch', 'visit', 'patient', 'status')
        }),
        ('Dates', {
            'fields': ('invoice_date', 'due_date', 'payment_due_date', 'last_payment_date')
        }),
        ('Financials', {
            'fields': ('subtotal', 'discount_percentage', 'discount_amount', 
                      'tax_percentage', 'tax_amount', 'total_amount', 
                      'paid_amount', 'balance_amount')
        }),
        ('Control', {
            'fields': ('is_locked', 'is_final', 'can_modify', 'eod_lock')
        }),
        ('Override', {
            'fields': ('override_reason', 'override_by'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_paid', 'is_overdue'),
            'classes': ('collapse',)
        }),
    )
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of paid or locked invoices
        if obj and (obj.is_locked or obj.status == 'PAID'):
            return False
        return super().has_delete_permission(request, obj)

@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'description', 'item_type', 'quantity', 'unit_price', 'total_amount')
    list_filter = ('item_type',)
    search_fields = ('invoice__invoice_number', 'description', 'code')
    readonly_fields = ('total_amount', 'tax_amount', 'discount_amount', 'doctor_commission_amount')
    raw_id_fields = ('invoice', 'treatment', 'treatment_plan_item', 'doctor')

@admin.register(DiscountPolicy)
class DiscountPolicyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'discount_type', 'applicable_to', 'is_active', 
                   'valid_from', 'valid_until', 'used_count')
    list_filter = ('discount_type', 'applicable_to', 'is_active', 'requires_approval')
    search_fields = ('code', 'name')
    readonly_fields = ('used_count',)

@admin.register(AppliedDiscount)
class AppliedDiscountAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'discount_policy', 'discount_amount', 'approved_by', 
                   'is_reversed', 'created_at')
    list_filter = ('is_reversed', 'discount_policy')
    search_fields = ('invoice__invoice_number', 'discount_policy__code')
    readonly_fields = ('discount_amount', 'original_amount', 'approved_at', 'reversed_at')
    raw_id_fields = ('invoice', 'discount_policy', 'approved_by', 'reversed_by')