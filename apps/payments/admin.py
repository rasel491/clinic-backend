# # payments/admin.py
# from django.contrib import admin
# from django.utils.html import format_html
# from django.urls import reverse
# from django.utils import timezone

# from .models import (
#     PaymentMethod, Payment, Refund, 
#     PaymentReceipt, PaymentReconciliation
# )


# @admin.register(PaymentMethod)
# class PaymentMethodAdmin(admin.ModelAdmin):
#     list_display = ('name', 'code', 'is_active', 'requires_approval', 
#                    'approval_amount_limit', 'sort_order')
#     list_filter = ('is_active', 'requires_approval')
#     list_editable = ('is_active', 'sort_order')
#     search_fields = ('name', 'code')
#     ordering = ('sort_order', 'name')


# class RefundInline(admin.TabularInline):
#     model = Refund
#     extra = 0
#     fields = ('refund_number', 'amount', 'status', 'requested_at', 
#              'approved_at', 'refund_method')
#     readonly_fields = ('refund_number', 'amount', 'status', 
#                       'requested_at', 'approved_at', 'refund_method')
#     can_delete = False
#     show_change_link = True
#     max_num = 0


# @admin.register(Payment)
# class PaymentAdmin(admin.ModelAdmin):
#     list_display = ('payment_number', 'patient_link', 'invoice_link', 
#                    'amount', 'method_display', 'status', 
#                    'payment_date', 'branch', 'eod_locked', 'reconciled')
#     list_filter = ('status', 'payment_method', 'branch', 'eod_locked',
#                   'reconciled', 'payment_date')
#     search_fields = ('payment_number', 'patient__first_name', 
#                     'patient__last_name', 'invoice__invoice_number',
#                     'reference_number')
#     readonly_fields = ('payment_number', 'created_at', 'updated_at',
#                       'eod_locked', 'locked_eod_id')
#     raw_id_fields = ('patient', 'invoice', 'approved_by', 'reconciled_by')
#     date_hierarchy = 'payment_date'
#     inlines = [RefundInline]
    
#     fieldsets = (
#         ('Payment Information', {
#             'fields': ('payment_number', 'invoice', 'patient', 
#                       'amount', 'payment_method', 'method_display')
#         }),
#         ('Payment Details', {
#             'fields': ('reference_number', 'card_last_four', 'card_type',
#                       'upi_id', 'bank_name', 'cheque_number',
#                       'insurance_provider', 'insurance_claim_id')
#         }),
#         ('Status & Timing', {
#             'fields': ('status', 'payment_date', 'completed_at',
#                       'failed_at', 'failure_reason')
#         }),
#         ('Approval & Control', {
#             'fields': ('requires_approval', 'approved_by', 'approved_at',
#                       'approval_notes', 'receipt_generated', 
#                       'receipt_number', 'receipt_reprint_count')
#         }),
#         ('Reconciliation & Locking', {
#             'fields': ('reconciled', 'reconciled_by', 'reconciled_at',
#                       'eod_locked', 'locked_eod_id')
#         }),
#         ('Audit Information', {
#             'fields': ('notes', 'created_at', 'updated_at',
#                       'created_by', 'updated_by')
#         }),
#     )
    
#     def patient_link(self, obj):
#         url = reverse('admin:patients_patient_change', args=[obj.patient.id])
#         return format_html('<a href="{}">{}</a>', url, obj.patient)
#     patient_link.short_description = 'Patient'
#     patient_link.admin_order_field = 'patient'
    
#     def invoice_link(self, obj):
#         url = reverse('admin:billing_invoice_change', args=[obj.invoice.id])
#         return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
#     invoice_link.short_description = 'Invoice'
#     invoice_link.admin_order_field = 'invoice'
    
#     def get_queryset(self, request):
#         qs = super().get_queryset(request)
#         if request.user.is_superuser:
#             return qs
#         # Filter by user's branch
#         if hasattr(request.user, 'branch'):
#             return qs.filter(branch=request.user.branch)
#         return qs.none()


# @admin.register(Refund)
# class RefundAdmin(admin.ModelAdmin):
#     list_display = ('refund_number', 'payment_link', 'invoice_link',
#                    'amount', 'refund_method', 'status', 
#                    'requested_by', 'requested_at', 'approved_by',
#                    'eod_locked')
#     list_filter = ('status', 'refund_method', 'branch', 'eod_locked',
#                   'requested_at')
#     search_fields = ('refund_number', 'payment__payment_number',
#                     'invoice__invoice_number', 'reference_number')
#     readonly_fields = ('refund_number', 'created_at', 'updated_at')
#     raw_id_fields = ('payment', 'invoice', 'requested_by', 'approved_by',
#                     'rejected_by', 'completed_by')
#     date_hierarchy = 'requested_at'
    
#     fieldsets = (
#         ('Refund Information', {
#             'fields': ('refund_number', 'payment', 'invoice', 'amount',
#                       'refund_method', 'reason')
#         }),
#         ('Workflow Status', {
#             'fields': ('status', 'requested_by', 'requested_at',
#                       'approved_by', 'approved_at', 'approval_notes',
#                       'rejected_by', 'rejected_at', 'rejection_reason',
#                       'completed_by', 'completed_at')
#         }),
#         ('Refund Details', {
#             'fields': ('reference_number', 'bank_name', 'account_number',
#                       'ifsc_code', 'cheque_number', 'credit_note_number',
#                       'credit_note_valid_until')
#         }),
#         ('System Information', {
#             'fields': ('notes', 'eod_locked', 'created_at', 'updated_at',
#                       'created_by', 'updated_by')
#         }),
#     )
    
#     def payment_link(self, obj):
#         url = reverse('admin:payments_payment_change', args=[obj.payment.id])
#         return format_html('<a href="{}">{}</a>', url, obj.payment.payment_number)
#     payment_link.short_description = 'Payment'
#     payment_link.admin_order_field = 'payment'
    
#     def invoice_link(self, obj):
#         url = reverse('admin:billing_invoice_change', args=[obj.invoice.id])
#         return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number)
#     invoice_link.short_description = 'Invoice'
#     invoice_link.admin_order_field = 'invoice'
    
#     actions = ['approve_refunds', 'reject_refunds']
    
#     def approve_refunds(self, request, queryset):
#         """Action to approve selected refunds"""
#         for refund in queryset.filter(status=Refund.REQUESTED):
#             refund.approve(request.user, "Bulk approval via admin")
#         self.message_user(request, f"{queryset.count()} refund(s) approved.")
#     approve_refunds.short_description = "Approve selected refunds"
    
#     def reject_refunds(self, request, queryset):
#         """Action to reject selected refunds"""
#         for refund in queryset.filter(status=Refund.REQUESTED):
#             refund.reject(request.user, "Bulk rejection via admin")
#         self.message_user(request, f"{queryset.count()} refund(s) rejected.")
#     reject_refunds.short_description = "Reject selected refunds"


# @admin.register(PaymentReceipt)
# class PaymentReceiptAdmin(admin.ModelAdmin):
#     list_display = ('receipt_number', 'payment_link', 'is_duplicate',
#                    'original_receipt_link', 'reprint_count',
#                    'generated_by', 'generated_at')
#     list_filter = ('is_duplicate', 'branch', 'generated_at')
#     search_fields = ('receipt_number', 'payment__payment_number',
#                     'security_code')
#     readonly_fields = ('receipt_number', 'generated_at', 'security_code',
#                       'qr_code_data', 'is_duplicate', 'original_receipt',
#                       'reprint_count')
#     raw_id_fields = ('payment', 'original_receipt', 'generated_by')
#     date_hierarchy = 'generated_at'
    
#     def payment_link(self, obj):
#         url = reverse('admin:payments_payment_change', args=[obj.payment.id])
#         return format_html('<a href="{}">{}</a>', url, obj.payment.payment_number)
#     payment_link.short_description = 'Payment'
#     payment_link.admin_order_field = 'payment'
    
#     def original_receipt_link(self, obj):
#         if obj.original_receipt:
#             url = reverse('admin:payments_paymentreceipt_change', 
#                          args=[obj.original_receipt.id])
#             return format_html('<a href="{}">{}</a>', url, 
#                               obj.original_receipt.receipt_number)
#         return "-"
#     original_receipt_link.short_description = 'Original Receipt'


# @admin.register(PaymentReconciliation)
# class PaymentReconciliationAdmin(admin.ModelAdmin):
#     list_display = ('reconciliation_number', 'reconciliation_date',
#                    'branch', 'status', 'opening_cash', 'expected_cash',
#                    'actual_cash', 'cash_difference', 'prepared_by',
#                    'reviewed_by')
#     list_filter = ('status', 'branch', 'reconciliation_date',
#                   'discrepancy_resolved')
#     search_fields = ('reconciliation_number', 'prepared_by__username')
#     readonly_fields = ('reconciliation_number', 'cash_difference',
#                       'reviewed_at', 'resolved_at')
#     raw_id_fields = ('branch', 'prepared_by', 'reviewed_by',
#                     'resolved_by', 'eod_lock')
#     date_hierarchy = 'reconciliation_date'
    
#     fieldsets = (
#         ('Basic Information', {
#             'fields': ('reconciliation_number', 'reconciliation_date',
#                       'branch', 'status')
#         }),
#         ('Cash Handling', {
#             'fields': ('opening_cash', 'expected_cash', 'actual_cash',
#                       'cash_difference')
#         }),
#         ('Payment Method Totals', {
#             'fields': ('cash_total', 'card_total', 'upi_total',
#                       'bank_transfer_total', 'insurance_total',
#                       'cheque_total', 'payment_plan_total')
#         }),
#         ('Transaction Summary', {
#             'fields': ('total_transactions', 'total_refunds',
#                       'refund_total')
#         }),
#         ('Personnel', {
#             'fields': ('prepared_by', 'reviewed_by', 'reviewed_at',
#                       'resolved_by', 'resolved_at')
#         }),
#         ('Discrepancy Handling', {
#             'fields': ('discrepancy_notes', 'discrepancy_resolved',
#                       'resolution_notes')
#         }),
#         ('System Integration', {
#             'fields': ('eod_lock', 'created_at', 'updated_at',
#                       'created_by', 'updated_by')
#         }),
#     )
    
#     actions = ['recalculate_totals', 'mark_as_completed']
    
#     def recalculate_totals(self, request, queryset):
#         """Action to recalculate totals for selected reconciliations"""
#         for recon in queryset:
#             recon.calculate_totals()
#         self.message_user(request, 
#                          f"{queryset.count()} reconciliation(s) recalculated.")
#     recalculate_totals.short_description = "Recalculate totals"
    
#     def mark_as_completed(self, request, queryset):
#         """Action to mark reconciliations as completed"""
#         for recon in queryset.filter(status=PaymentReconciliation.STATUS_OPEN):
#             recon.status = PaymentReconciliation.STATUS_COMPLETED
#             recon.reviewed_by = request.user
#             recon.reviewed_at = timezone.now()
#             recon.save()
#         self.message_user(request, 
#                          f"{queryset.count()} reconciliation(s) marked as completed.")
#     mark_as_completed.short_description = "Mark as completed"


from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.contrib import messages

from .models import (
    PaymentMethod, Payment, Refund, 
    PaymentReceipt, PaymentSplit
)


# ===========================================
# INLINE ADMIN CLASSES
# ===========================================
class PaymentSplitInline(admin.TabularInline):
    """Inline for payment splits"""
    model = PaymentSplit
    extra = 0
    fields = ['payment_method', 'amount', 'reference_number', 'notes']
    readonly_fields = ['payment_method', 'amount', 'reference_number', 'notes']


class RefundInline(admin.TabularInline):
    """Inline for refunds"""
    model = Refund
    extra = 0
    fields = ['refund_number', 'amount', 'status', 'refund_method', 'requested_at']
    readonly_fields = ['refund_number', 'amount', 'status', 'refund_method', 'requested_at']
    can_delete = False
    show_change_link = True
    max_num = 0


# ===========================================
# CUSTOM FILTERS
# ===========================================
class PaymentStatusFilter(admin.SimpleListFilter):
    """Filter payments by status"""
    title = 'Status'
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return Payment.STATUS_CHOICES
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class RefundStatusFilter(admin.SimpleListFilter):
    """Filter refunds by status"""
    title = 'Status'
    parameter_name = 'status'
    
    def lookups(self, request, model_admin):
        return Refund.STATUS_CHOICES
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class ReconciledFilter(admin.SimpleListFilter):
    """Filter for reconciled payments"""
    title = 'Reconciled'
    parameter_name = 'reconciled'
    
    def lookups(self, request, model_admin):
        return [
            ('yes', 'Yes'),
            ('no', 'No'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(reconciled=True)
        elif self.value() == 'no':
            return queryset.filter(reconciled=False)
        return queryset


# ===========================================
# CUSTOM ACTIONS
# ===========================================
@admin.action(description='Mark selected payments as completed')
def mark_as_completed(modeladmin, request, queryset):
    """Mark payments as completed"""
    for payment in queryset.filter(status=Payment.PENDING):
        payment.status = Payment.COMPLETED
        payment.completed_at = timezone.now()
        payment.save()
    
    modeladmin.message_user(request, f'{queryset.count()} payments marked as completed.')


@admin.action(description='Reconcile selected payments')
def reconcile_payments(modeladmin, request, queryset):
    """Reconcile payments"""
    for payment in queryset.filter(status=Payment.COMPLETED, reconciled=False):
        payment.reconciled = True
        payment.reconciled_at = timezone.now()
        payment.reconciled_by = request.user
        payment.save()
    
    modeladmin.message_user(request, f'{queryset.count()} payments reconciled.')


@admin.action(description='Approve selected refunds')
def approve_refunds(modeladmin, request, queryset):
    """Approve refund requests"""
    for refund in queryset.filter(status=Refund.REQUESTED):
        refund.approve(request.user, "Bulk approval via admin")
    
    modeladmin.message_user(request, f'{queryset.count()} refunds approved.')


@admin.action(description='Generate receipts for selected payments')
def generate_receipts(modeladmin, request, queryset):
    """Generate receipts for payments"""
    generated = 0
    for payment in queryset.filter(status=Payment.COMPLETED, receipt_generated=False):
        try:
            payment.generate_receipt(request.user)
            generated += 1
        except ValueError as e:
            modeladmin.message_user(request, f'Error for payment {payment}: {str(e)}', level=messages.ERROR)
    
    modeladmin.message_user(request, f'{generated} receipts generated.')


# ===========================================
# ADMIN CLASSES
# ===========================================
@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    """Admin for PaymentMethod"""
    
    list_display = [
        'code', 'name', 'is_active_badge', 'requires_approval',
        'approval_amount_limit', 'sort_order', 'payment_count'
    ]
    
    list_filter = ['is_active', 'requires_approval']
    
    search_fields = ['name', 'code', 'description']
    
    # FIXED: is_active_badge is a method, not a field, so can't be in list_editable
    # Remove list_editable or use actual field names
    # list_editable = ['is_active', 'sort_order']  # Removed because is_active not in list_display as field
    
    # FIXED: PaymentMethod doesn't have created_at/updated_at fields
    # readonly_fields = ['payment_count']  # Only payment_count is a method
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description', 'icon_class')
        }),
        ('Configuration', {
            'fields': ('is_active', 'requires_approval', 'approval_amount_limit',
                      'requires_reference', 'sort_order')
        }),
        ('Statistics', {
            'fields': ('payment_count',)  # This will show as read-only automatically
        }),
    )
    
    def is_active_badge(self, obj):
        color = 'green' if obj.is_active else 'red'
        text = 'Active' if obj.is_active else 'Inactive'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 10px;">{}</span>',
            color, text
        )
    is_active_badge.short_description = 'Status'
    is_active_badge.admin_order_field = 'is_active'
    
    def payment_count(self, obj):
        return obj.payments.count()
    payment_count.short_description = 'Payments'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only for new objects
            # Try to set created_by if user is authenticated
            if request.user.is_authenticated:
                # PaymentMethod doesn't have created_by field, so we'll just save
                pass
        super().save_model(request, obj, form, change)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin for Payment"""
    
    list_display = [
        'payment_number', 'patient_link', 'invoice_link', 'amount_badge',
        'method_display', 'status_badge', 'payment_date', 'branch',
        'reconciled_badge', 'is_locked_badge'
    ]
    
    list_filter = [
        PaymentStatusFilter, ReconciledFilter, 'payment_method',
        'branch', 'is_locked', 'payment_date'
    ]
    
    search_fields = [
        'payment_number', 'patient__user__first_name',
        'patient__user__last_name', 'invoice__invoice_number',
        'reference_number'
    ]
    
    readonly_fields = [
        'payment_number', 'refundable_amount', 'can_refund',
        'completed_at', 'failed_at', 'approved_at', 'reconciled_at',
        'last_reprinted_at', 'is_locked', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('payment_number', 'invoice', 'patient', 'branch', 'counter')
        }),
        ('Amount & Method', {
            'fields': ('amount', 'payment_method', 'method_display')
        }),
        ('Payment Details', {
            'fields': ('reference_number', 'card_last_four', 'card_type',
                      'upi_id', 'bank_name', 'cheque_number', 'cheque_date',
                      'insurance_provider', 'insurance_claim_id')
        }),
        ('Status & Timing', {
            'fields': ('status', 'payment_date', 'completed_at',
                      'failed_at', 'failure_reason')
        }),
        ('Approval & Control', {
            'fields': ('requires_approval', 'approved_by', 'approved_at',
                      'approval_notes')
        }),
        ('Receipt Management', {
            'fields': ('receipt_generated', 'receipt_number',
                      'receipt_reprint_count', 'last_reprinted_at',
                      'last_reprinted_by')
        }),
        ('Reconciliation', {
            'fields': ('reconciled', 'reconciled_by', 'reconciled_at')
        }),
        ('Refund Information', {
            'fields': ('refundable_amount', 'can_refund')
        }),
        ('System Control', {
            'fields': ('is_locked', 'notes', 'internal_notes')
        }),
    )
    
    inlines = [PaymentSplitInline, RefundInline]
    
    actions = [mark_as_completed, reconcile_payments, generate_receipts]
    
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
    
    def amount_badge(self, obj):
        color = 'green' if obj.status == Payment.COMPLETED else 'orange'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; border-radius: 15px; font-weight: bold;">₹{}</span>',
            color, obj.amount
        )
    amount_badge.short_description = 'Amount'
    amount_badge.admin_order_field = 'amount'
    
    def status_badge(self, obj):
        colors = {
            'PENDING': 'gray',
            'COMPLETED': 'green',
            'FAILED': 'red',
            'REFUNDED': 'purple',
            'PARTIALLY_REFUNDED': 'orange',
            'CANCELLED': 'darkred',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 10px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def reconciled_badge(self, obj):
        if obj.reconciled:
            return format_html(
                '<span style="background-color: green; color: white; padding: 2px 8px; border-radius: 10px;">✓</span>'
            )
        return format_html(
            '<span style="background-color: orange; color: white; padding: 2px 8px; border-radius: 10px;">✗</span>'
        )
    reconciled_badge.short_description = 'Reconciled'
    reconciled_badge.boolean = True
    
    def is_locked_badge(self, obj):
        if obj.is_locked:
            return format_html(
                '<span style="background-color: red; color: white; padding: 2px 8px; border-radius: 10px;">LOCKED</span>'
            )
        return format_html(
            '<span style="background-color: green; color: white; padding: 2px 8px; border-radius: 10px;">OPEN</span>'
        )
    is_locked_badge.short_description = 'Locked'
    is_locked_badge.boolean = True
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """Add custom context for payment form"""
        extra_context = extra_context or {}
        
        if object_id:
            payment = Payment.objects.get(id=object_id)
            extra_context['can_modify'] = not payment.is_locked
        
        return super().changeform_view(request, object_id, form_url, extra_context)


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    """Admin for Refund"""
    
    list_display = [
        'refund_number', 'payment_link', 'invoice_link', 'amount_badge',
        'refund_method', 'status_badge', 'requested_by', 'requested_at',
        'approved_by', 'is_locked_badge'
    ]
    
    list_filter = [
        RefundStatusFilter, 'refund_method', 'branch', 'is_locked', 'requested_at'
    ]
    
    search_fields = [
        'refund_number', 'payment__payment_number',
        'invoice__invoice_number', 'reference_number'
    ]
    
    readonly_fields = [
        'refund_number', 'requested_at', 'approved_at', 'rejected_at',
        'completed_at', 'is_locked', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Refund Information', {
            'fields': ('refund_number', 'payment', 'invoice', 'branch')
        }),
        ('Amount & Method', {
            'fields': ('amount', 'refund_method')
        }),
        ('Workflow Status', {
            'fields': ('status', 'requested_by', 'requested_at',
                      'approved_by', 'approved_at', 'approval_notes',
                      'rejected_by', 'rejected_at', 'rejection_reason',
                      'completed_by', 'completed_at')
        }),
        ('Refund Details', {
            'fields': ('reference_number', 'bank_name', 'account_number',
                      'ifsc_code', 'cheque_number', 'cheque_date',
                      'credit_note_number', 'credit_note_valid_until')
        }),
        ('Reason & Notes', {
            'fields': ('reason', 'notes')
        }),
        ('System Information', {
            'fields': ('is_locked', 'created_at', 'updated_at',
                      'created_by', 'updated_by')
        }),
    )
    
    actions = [approve_refunds]
    
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
    
    def amount_badge(self, obj):
        color = 'red'  # Refunds are always red
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; border-radius: 15px; font-weight: bold;">-₹{}</span>',
            color, obj.amount
        )
    amount_badge.short_description = 'Amount'
    amount_badge.admin_order_field = 'amount'
    
    def status_badge(self, obj):
        colors = {
            'REQUESTED': 'orange',
            'APPROVED': 'blue',
            'REJECTED': 'red',
            'COMPLETED': 'green',
            'CANCELLED': 'darkred',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 10px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'
    
    def is_locked_badge(self, obj):
        if obj.is_locked:
            return format_html(
                '<span style="background-color: red; color: white; padding: 2px 8px; border-radius: 10px;">LOCKED</span>'
            )
        return format_html(
            '<span style="background-color: green; color: white; padding: 2px 8px; border-radius: 10px;">OPEN</span>'
        )
    is_locked_badge.short_description = 'Locked'
    is_locked_badge.boolean = True
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(admin.ModelAdmin):
    """Admin for PaymentReceipt"""
    
    list_display = [
        'receipt_number', 'payment_link', 'is_duplicate_badge',
        'original_receipt_link', 'reprint_count', 'generated_by',
        'generated_at', 'security_code_short'
    ]
    
    list_filter = ['is_duplicate', 'branch', 'generated_at']
    
    search_fields = [
        'receipt_number', 'payment__payment_number',
        'security_code', 'qr_code_data'
    ]
    
    readonly_fields = [
        'receipt_number', 'security_code', 'qr_code_data',
        'is_duplicate', 'original_receipt', 'reprint_count',
        'generated_at', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Receipt Information', {
            'fields': ('receipt_number', 'payment', 'branch', 'is_duplicate', 'original_receipt')
        }),
        ('Receipt Content', {
            'fields': ('receipt_data', 'html_template', 'generated_html', 'pdf_file')
        }),
        ('Reprint Control', {
            'fields': ('reprint_count',)
        }),
        ('Security', {
            'fields': ('security_code', 'qr_code_data')
        }),
        ('Generation Info', {
            'fields': ('generated_by', 'generated_at')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by')
        }),
    )
    
    def payment_link(self, obj):
        url = reverse('admin:payments_payment_change', args=[obj.payment.id])
        return format_html('<a href="{}">{}</a>', url, obj.payment.payment_number)
    payment_link.short_description = 'Payment'
    payment_link.admin_order_field = 'payment'
    
    def original_receipt_link(self, obj):
        if obj.original_receipt:
            url = reverse('admin:payments_paymentreceipt_change', args=[obj.original_receipt.id])
            return format_html('<a href="{}">{}</a>', url, obj.original_receipt.receipt_number)
        return "-"
    original_receipt_link.short_description = 'Original Receipt'
    
    def is_duplicate_badge(self, obj):
        if obj.is_duplicate:
            return format_html(
                '<span style="background-color: orange; color: white; padding: 2px 8px; border-radius: 10px;">DUPLICATE</span>'
            )
        return format_html(
            '<span style="background-color: green; color: white; padding: 2px 8px; border-radius: 10px;">ORIGINAL</span>'
        )
    is_duplicate_badge.short_description = 'Type'
    is_duplicate_badge.boolean = True
    
    def security_code_short(self, obj):
        return obj.security_code[:4] + "..." if len(obj.security_code) > 4 else obj.security_code
    security_code_short.short_description = 'Security Code'
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)