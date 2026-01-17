# payments/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone

from .models import (
    PaymentMethod, Payment, Refund, 
    PaymentReceipt, PaymentReconciliation
)


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'requires_approval', 
                   'approval_amount_limit', 'sort_order')
    list_filter = ('is_active', 'requires_approval')
    list_editable = ('is_active', 'sort_order')
    search_fields = ('name', 'code')
    ordering = ('sort_order', 'name')


class RefundInline(admin.TabularInline):
    model = Refund
    extra = 0
    fields = ('refund_number', 'amount', 'status', 'requested_at', 
             'approved_at', 'refund_method')
    readonly_fields = ('refund_number', 'amount', 'status', 
                      'requested_at', 'approved_at', 'refund_method')
    can_delete = False
    show_change_link = True
    max_num = 0


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('payment_number', 'patient_link', 'invoice_link', 
                   'amount', 'method_display', 'status', 
                   'payment_date', 'branch', 'eod_locked', 'reconciled')
    list_filter = ('status', 'payment_method', 'branch', 'eod_locked',
                  'reconciled', 'payment_date')
    search_fields = ('payment_number', 'patient__first_name', 
                    'patient__last_name', 'invoice__invoice_number',
                    'reference_number')
    readonly_fields = ('payment_number', 'created_at', 'updated_at',
                      'eod_locked', 'locked_eod_id')
    raw_id_fields = ('patient', 'invoice', 'approved_by', 'reconciled_by')
    date_hierarchy = 'payment_date'
    inlines = [RefundInline]
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('payment_number', 'invoice', 'patient', 
                      'amount', 'payment_method', 'method_display')
        }),
        ('Payment Details', {
            'fields': ('reference_number', 'card_last_four', 'card_type',
                      'upi_id', 'bank_name', 'cheque_number',
                      'insurance_provider', 'insurance_claim_id')
        }),
        ('Status & Timing', {
            'fields': ('status', 'payment_date', 'completed_at',
                      'failed_at', 'failure_reason')
        }),
        ('Approval & Control', {
            'fields': ('requires_approval', 'approved_by', 'approved_at',
                      'approval_notes', 'receipt_generated', 
                      'receipt_number', 'receipt_reprint_count')
        }),
        ('Reconciliation & Locking', {
            'fields': ('reconciled', 'reconciled_by', 'reconciled_at',
                      'eod_locked', 'locked_eod_id')
        }),
        ('Audit Information', {
            'fields': ('notes', 'created_at', 'updated_at',
                      'created_by', 'updated_by')
        }),
    )
    
    def patient_link(self, obj):
        url = reverse('admin:patients_patient_change', args=[obj.patient.id])
        return format_html('<a href="{}">{}</a>', url, obj.patient)
    patient_link.short_description = 'Patient'
    patient_link.admin_order_field = 'patient'
    
    def invoice_link(self, obj):
        url = reverse('admin:billing_invoice_change', args=[obj.invoice.id])
        return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
    invoice_link.short_description = 'Invoice'
    invoice_link.admin_order_field = 'invoice'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by user's branch
        if hasattr(request.user, 'branch'):
            return qs.filter(branch=request.user.branch)
        return qs.none()


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ('refund_number', 'payment_link', 'invoice_link',
                   'amount', 'refund_method', 'status', 
                   'requested_by', 'requested_at', 'approved_by',
                   'eod_locked')
    list_filter = ('status', 'refund_method', 'branch', 'eod_locked',
                  'requested_at')
    search_fields = ('refund_number', 'payment__payment_number',
                    'invoice__invoice_number', 'reference_number')
    readonly_fields = ('refund_number', 'created_at', 'updated_at')
    raw_id_fields = ('payment', 'invoice', 'requested_by', 'approved_by',
                    'rejected_by', 'completed_by')
    date_hierarchy = 'requested_at'
    
    fieldsets = (
        ('Refund Information', {
            'fields': ('refund_number', 'payment', 'invoice', 'amount',
                      'refund_method', 'reason')
        }),
        ('Workflow Status', {
            'fields': ('status', 'requested_by', 'requested_at',
                      'approved_by', 'approved_at', 'approval_notes',
                      'rejected_by', 'rejected_at', 'rejection_reason',
                      'completed_by', 'completed_at')
        }),
        ('Refund Details', {
            'fields': ('reference_number', 'bank_name', 'account_number',
                      'ifsc_code', 'cheque_number', 'credit_note_number',
                      'credit_note_valid_until')
        }),
        ('System Information', {
            'fields': ('notes', 'eod_locked', 'created_at', 'updated_at',
                      'created_by', 'updated_by')
        }),
    )
    
    def payment_link(self, obj):
        url = reverse('admin:payments_payment_change', args=[obj.payment.id])
        return format_html('<a href="{}">{}</a>', url, obj.payment.payment_number)
    payment_link.short_description = 'Payment'
    payment_link.admin_order_field = 'payment'
    
    def invoice_link(self, obj):
        url = reverse('admin:billing_invoice_change', args=[obj.invoice.id])
        return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
    invoice_link.short_description = 'Invoice'
    invoice_link.admin_order_field = 'invoice'
    
    actions = ['approve_refunds', 'reject_refunds']
    
    def approve_refunds(self, request, queryset):
        """Action to approve selected refunds"""
        for refund in queryset.filter(status=Refund.REQUESTED):
            refund.approve(request.user, "Bulk approval via admin")
        self.message_user(request, f"{queryset.count()} refund(s) approved.")
    approve_refunds.short_description = "Approve selected refunds"
    
    def reject_refunds(self, request, queryset):
        """Action to reject selected refunds"""
        for refund in queryset.filter(status=Refund.REQUESTED):
            refund.reject(request.user, "Bulk rejection via admin")
        self.message_user(request, f"{queryset.count()} refund(s) rejected.")
    reject_refunds.short_description = "Reject selected refunds"


@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'payment_link', 'is_duplicate',
                   'original_receipt_link', 'reprint_count',
                   'generated_by', 'generated_at')
    list_filter = ('is_duplicate', 'branch', 'generated_at')
    search_fields = ('receipt_number', 'payment__payment_number',
                    'security_code')
    readonly_fields = ('receipt_number', 'generated_at', 'security_code',
                      'qr_code_data', 'is_duplicate', 'original_receipt',
                      'reprint_count')
    raw_id_fields = ('payment', 'original_receipt', 'generated_by')
    date_hierarchy = 'generated_at'
    
    def payment_link(self, obj):
        url = reverse('admin:payments_payment_change', args=[obj.payment.id])
        return format_html('<a href="{}">{}</a>', url, obj.payment.payment_number)
    payment_link.short_description = 'Payment'
    payment_link.admin_order_field = 'payment'
    
    def original_receipt_link(self, obj):
        if obj.original_receipt:
            url = reverse('admin:payments_paymentreceipt_change', 
                         args=[obj.original_receipt.id])
            return format_html('<a href="{}">{}</a>', url, 
                              obj.original_receipt.receipt_number)
        return "-"
    original_receipt_link.short_description = 'Original Receipt'


@admin.register(PaymentReconciliation)
class PaymentReconciliationAdmin(admin.ModelAdmin):
    list_display = ('reconciliation_number', 'reconciliation_date',
                   'branch', 'status', 'opening_cash', 'expected_cash',
                   'actual_cash', 'cash_difference', 'prepared_by',
                   'reviewed_by')
    list_filter = ('status', 'branch', 'reconciliation_date',
                  'discrepancy_resolved')
    search_fields = ('reconciliation_number', 'prepared_by__username')
    readonly_fields = ('reconciliation_number', 'cash_difference',
                      'reviewed_at', 'resolved_at')
    raw_id_fields = ('branch', 'prepared_by', 'reviewed_by',
                    'resolved_by', 'eod_lock')
    date_hierarchy = 'reconciliation_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('reconciliation_number', 'reconciliation_date',
                      'branch', 'status')
        }),
        ('Cash Handling', {
            'fields': ('opening_cash', 'expected_cash', 'actual_cash',
                      'cash_difference')
        }),
        ('Payment Method Totals', {
            'fields': ('cash_total', 'card_total', 'upi_total',
                      'bank_transfer_total', 'insurance_total',
                      'cheque_total', 'payment_plan_total')
        }),
        ('Transaction Summary', {
            'fields': ('total_transactions', 'total_refunds',
                      'refund_total')
        }),
        ('Personnel', {
            'fields': ('prepared_by', 'reviewed_by', 'reviewed_at',
                      'resolved_by', 'resolved_at')
        }),
        ('Discrepancy Handling', {
            'fields': ('discrepancy_notes', 'discrepancy_resolved',
                      'resolution_notes')
        }),
        ('System Integration', {
            'fields': ('eod_lock', 'created_at', 'updated_at',
                      'created_by', 'updated_by')
        }),
    )
    
    actions = ['recalculate_totals', 'mark_as_completed']
    
    def recalculate_totals(self, request, queryset):
        """Action to recalculate totals for selected reconciliations"""
        for recon in queryset:
            recon.calculate_totals()
        self.message_user(request, 
                         f"{queryset.count()} reconciliation(s) recalculated.")
    recalculate_totals.short_description = "Recalculate totals"
    
    def mark_as_completed(self, request, queryset):
        """Action to mark reconciliations as completed"""
        for recon in queryset.filter(status=PaymentReconciliation.STATUS_OPEN):
            recon.status = PaymentReconciliation.STATUS_COMPLETED
            recon.reviewed_by = request.user
            recon.reviewed_at = timezone.now()
            recon.save()
        self.message_user(request, 
                         f"{queryset.count()} reconciliation(s) marked as completed.")
    mark_as_completed.short_description = "Mark as completed"