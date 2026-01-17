# apps/eod/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.contrib import messages

from .models import EodLock, DailySummary, CashReconciliation, EodException


@admin.register(EodLock)
class EodLockAdmin(admin.ModelAdmin):
    list_display = ('lock_number', 'branch', 'lock_date', 'status',
                   'total_invoice_amount', 'total_payment_amount',
                   'net_cash_position', 'has_discrepancies',
                   'locked_by', 'locked_at')
    list_filter = ('status', 'branch', 'lock_date', 'has_discrepancies')
    search_fields = ('lock_number', 'branch__name', 'notes')
    readonly_fields = ('lock_number', 'created_at', 'updated_at',
                      'net_cash_position', 'cash_difference',
                      'prepared_at', 'reviewed_at', 'locked_at',
                      'reversed_at')
    raw_id_fields = ('branch', 'prepared_by', 'reviewed_by', 'locked_by',
                    'reversed_by', 'cash_verified_by', 'digital_verified_by',
                    'invoices_verified_by', 'discrepancy_resolved_by',
                    'front_desk_counter')
    date_hierarchy = 'lock_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('lock_number', 'branch', 'lock_date', 'status')
        }),
        ('Financial Summary', {
            'fields': ('total_invoices', 'total_invoice_amount',
                      'total_payments', 'total_payment_amount',
                      'total_refunds', 'total_refund_amount')
        }),
        ('Cash Handling', {
            'fields': ('opening_cash', 'expected_cash', 'actual_cash',
                      'cash_difference', 'total_cash_collected',
                      'total_cash_refunded', 'net_cash_position')
        }),
        ('Digital Payments', {
            'fields': ('card_collections', 'upi_collections',
                      'bank_transfers', 'insurance_collections',
                      'cheque_collections')
        }),
        ('Workflow & Personnel', {
            'fields': ('prepared_by', 'prepared_at',
                      'reviewed_by', 'reviewed_at', 'review_notes',
                      'locked_by', 'locked_at')
        }),
        ('Verifications', {
            'fields': ('cash_verified', 'cash_verified_by', 'cash_verified_at',
                      'digital_payments_verified', 'digital_verified_by',
                      'digital_verified_at',
                      'invoices_verified', 'invoices_verified_by',
                      'invoices_verified_at')
        }),
        ('Discrepancies', {
            'fields': ('has_discrepancies', 'discrepancy_notes',
                      'discrepancy_resolved', 'discrepancy_resolved_by',
                      'discrepancy_resolved_at', 'resolution_notes')
        }),
        ('Reversal', {
            'fields': ('reversed_by', 'reversed_at', 'reversal_reason')
        }),
        ('Additional Information', {
            'fields': ('front_desk_counter', 'notes', 'created_at',
                      'updated_at', 'created_by', 'updated_by')
        }),
    )
    
    actions = ['calculate_totals', 'mark_as_reviewed', 'lock_eod',
              'verify_cash', 'verify_digital_payments']
    
    def calculate_totals(self, request, queryset):
        """Action to calculate totals for selected EODs"""
        for eod in queryset:
            try:
                eod.calculate_totals()
            except Exception as e:
                self.message_user(
                    request,
                    f"Error calculating totals for {eod.lock_number}: {str(e)}",
                    messages.ERROR
                )
        self.message_user(request, f"{queryset.count()} EOD(s) totals calculated.")
    calculate_totals.short_description = "Calculate totals"
    
    def mark_as_reviewed(self, request, queryset):
        """Action to mark EODs as reviewed"""
        for eod in queryset.filter(status=EodLock.PREPARED):
            eod.status = EodLock.REVIEWED
            eod.reviewed_by = request.user
            eod.reviewed_at = timezone.now()
            eod.save()
        self.message_user(request, f"{queryset.count()} EOD(s) marked as reviewed.")
    mark_as_reviewed.short_description = "Mark as reviewed"
    
    def lock_eod(self, request, queryset):
        """Action to lock EODs"""
        for eod in queryset.filter(status=EodLock.REVIEWED):
            try:
                eod.lock(request.user)
            except Exception as e:
                self.message_user(
                    request,
                    f"Error locking {eod.lock_number}: {str(e)}",
                    messages.ERROR
                )
        self.message_user(request, f"{queryset.count()} EOD(s) locked.")
    lock_eod.short_description = "Lock EOD"
    
    def verify_cash(self, request, queryset):
        """Action to verify cash for selected EODs"""
        for eod in queryset:
            eod.cash_verified = True
            eod.cash_verified_by = request.user
            eod.cash_verified_at = timezone.now()
            eod.save()
        self.message_user(request, f"{queryset.count()} EOD(s) cash verified.")
    verify_cash.short_description = "Verify cash"
    
    def verify_digital_payments(self, request, queryset):
        """Action to verify digital payments for selected EODs"""
        for eod in queryset:
            eod.digital_payments_verified = True
            eod.digital_verified_by = request.user
            eod.digital_verified_at = timezone.now()
            eod.save()
        self.message_user(request, f"{queryset.count()} EOD(s) digital payments verified.")
    verify_digital_payments.short_description = "Verify digital payments"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by user's branch
        if hasattr(request.user, 'branch'):
            return qs.filter(branch=request.user.branch)
        return qs.none()


@admin.register(DailySummary)
class DailySummaryAdmin(admin.ModelAdmin):
    list_display = ('summary_number', 'branch', 'summary_date',
                   'summary_type_display', 'custom_name',
                   'invoices_amount', 'payments_amount',
                   'generated_by', 'generated_at')
    list_filter = ('summary_type', 'branch', 'summary_date')
    search_fields = ('summary_number', 'custom_name', 'notes')
    readonly_fields = ('summary_number', 'generated_at', 'created_at',
                      'updated_at')
    raw_id_fields = ('branch', 'eod_lock', 'generated_by', 'created_by',
                    'updated_by')
    date_hierarchy = 'summary_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('summary_number', 'branch', 'summary_date',
                      'summary_type', 'custom_name')
        }),
        ('Time Period', {
            'fields': ('period_start', 'period_end')
        }),
        ('Financial Summary', {
            'fields': ('invoices_count', 'invoices_amount',
                      'payments_count', 'payments_amount',
                      'refunds_count', 'refunds_amount')
        }),
        ('Appointment Summary', {
            'fields': ('appointments_total', 'appointments_completed',
                      'appointments_cancelled', 'appointments_no_show')
        }),
        ('Patient Summary', {
            'fields': ('new_patients', 'returning_patients')
        }),
        ('Doctor Summary', {
            'fields': ('doctors_active', 'doctor_utilization')
        }),
        ('Detailed Data', {
            'fields': ('invoice_details', 'payment_details',
                      'appointment_details'),
            'classes': ('collapse',)
        }),
        ('Related Information', {
            'fields': ('eod_lock', 'generated_by', 'generated_at',
                      'notes', 'created_at', 'updated_at',
                      'created_by', 'updated_by')
        }),
    )
    
    def summary_type_display(self, obj):
        return dict(DailySummary.SUMMARY_TYPE_CHOICES)[obj.summary_type]
    summary_type_display.short_description = 'Summary Type'
    
    actions = ['regenerate_summary']
    
    def regenerate_summary(self, request, queryset):
        """Action to regenerate summary data"""
        for summary in queryset:
            try:
                # This would need to be implemented based on your actual data
                # For now, just mark that it needs regeneration
                summary.notes = f"Regeneration requested by {request.user} at {timezone.now()}"
                summary.save()
            except Exception as e:
                self.message_user(
                    request,
                    f"Error regenerating {summary.summary_number}: {str(e)}",
                    messages.ERROR
                )
        self.message_user(request, f"{queryset.count()} summary(ies) marked for regeneration.")
    regenerate_summary.short_description = "Regenerate summary data"


@admin.register(CashReconciliation)
class CashReconciliationAdmin(admin.ModelAdmin):
    list_display = ('reconciliation_number', 'branch', 'reconciliation_date',
                   'reconciliation_type_display', 'cashier',
                   'declared_cash', 'counted_cash', 'difference',
                   'verified', 'supervisor', 'counter')
    list_filter = ('reconciliation_type', 'branch', 'reconciliation_date',
                  'verified')
    search_fields = ('reconciliation_number', 'cashier__username',
                    'supervisor__username', 'notes')
    readonly_fields = ('reconciliation_number', 'difference',
                      'supervised_at', 'created_at', 'updated_at')
    raw_id_fields = ('branch', 'cashier', 'supervisor', 'counter',
                    'eod_lock', 'created_by', 'updated_by')
    date_hierarchy = 'reconciliation_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('reconciliation_number', 'branch',
                      'reconciliation_date', 'reconciliation_type')
        }),
        ('Cash Amounts', {
            'fields': ('declared_cash', 'counted_cash', 'difference')
        }),
        ('Denomination Breakdown', {
            'fields': ('denomination_breakdown',),
            'classes': ('collapse',)
        }),
        ('Personnel', {
            'fields': ('cashier', 'counter', 'supervisor', 'supervised_at')
        }),
        ('Verification', {
            'fields': ('verified', 'verification_notes')
        }),
        ('Related Information', {
            'fields': ('eod_lock', 'notes')
        }),
        ('Attachments', {
            'fields': ('cash_count_image', 'signature_image')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by')
        }),
    )
    
    def reconciliation_type_display(self, obj):
        return dict(CashReconciliation.RECONCILIATION_TYPE_CHOICES)[obj.reconciliation_type]
    reconciliation_type_display.short_description = 'Reconciliation Type'
    
    actions = ['verify_reconciliations', 'calculate_difference']
    
    def verify_reconciliations(self, request, queryset):
        """Action to verify selected reconciliations"""
        for recon in queryset.filter(verified=False):
            recon.verified = True
            recon.supervisor = request.user
            recon.supervised_at = timezone.now()
            recon.save()
        self.message_user(request, f"{queryset.count()} reconciliation(s) verified.")
    verify_reconciliations.short_description = "Verify reconciliations"
    
    def calculate_difference(self, request, queryset):
        """Action to calculate difference for selected reconciliations"""
        for recon in queryset:
            if recon.counted_cash is not None:
                recon.difference = recon.counted_cash - recon.declared_cash
                recon.save()
        self.message_user(request, f"{queryset.count()} reconciliation(s) difference calculated.")
    calculate_difference.short_description = "Calculate difference"


@admin.register(EodException)
class EodExceptionAdmin(admin.ModelAdmin):
    list_display = ('exception_number', 'branch', 'exception_date',
                   'exception_type_display', 'severity_display',
                   'status_display', 'title', 'amount_involved',
                   'assigned_to', 'resolved_by')
    list_filter = ('exception_type', 'severity', 'status', 'branch',
                  'exception_date')
    search_fields = ('exception_number', 'title', 'description',
                    'resolution_notes')
    readonly_fields = ('exception_number', 'created_at', 'updated_at',
                      'assigned_at', 'resolved_at')
    raw_id_fields = ('branch', 'related_invoice', 'related_payment',
                    'related_refund', 'assigned_to', 'resolved_by',
                    'eod_lock', 'created_by', 'updated_by')
    date_hierarchy = 'exception_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('exception_number', 'branch', 'exception_date',
                      'exception_type', 'severity', 'status')
        }),
        ('Description', {
            'fields': ('title', 'description', 'amount_involved')
        }),
        ('Related Records', {
            'fields': ('related_invoice', 'related_payment', 'related_refund')
        }),
        ('Assignment', {
            'fields': ('assigned_to', 'assigned_at')
        }),
        ('Resolution', {
            'fields': ('resolved_by', 'resolved_at', 'resolution_notes',
                      'resolution_action')
        }),
        ('Related Information', {
            'fields': ('eod_lock', 'attachment')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by')
        }),
    )
    
    def exception_type_display(self, obj):
        return dict(EodException.EXCEPTION_TYPE_CHOICES)[obj.exception_type]
    exception_type_display.short_description = 'Exception Type'
    
    def severity_display(self, obj):
        return dict(EodException.SEVERITY_CHOICES)[obj.severity]
    severity_display.short_description = 'Severity'
    
    def status_display(self, obj):
        return dict(EodException.STATUS_CHOICES)[obj.status]
    status_display.short_description = 'Status'
    
    actions = ['assign_to_me', 'mark_as_resolved', 'escalate_severity']
    
    def assign_to_me(self, request, queryset):
        """Action to assign exceptions to current user"""
        for exception in queryset.filter(status=EodException.OPEN):
            exception.assign(request.user)
        self.message_user(request, f"{queryset.count()} exception(s) assigned to you.")
    assign_to_me.short_description = "Assign to me"
    
    def mark_as_resolved(self, request, queryset):
        """Action to mark exceptions as resolved"""
        for exception in queryset.filter(status=EodException.IN_PROGRESS):
            exception.resolve(
                request.user,
                "Resolved via admin action",
                "Manual resolution"
            )
        self.message_user(request, f"{queryset.count()} exception(s) marked as resolved.")
    mark_as_resolved.short_description = "Mark as resolved"
    
    def escalate_severity(self, request, queryset):
        """Action to escalate severity of exceptions"""
        for exception in queryset:
            if exception.severity == EodException.LOW:
                exception.severity = EodException.MEDIUM
            elif exception.severity == EodException.MEDIUM:
                exception.severity = EodException.HIGH
            elif exception.severity == EodException.HIGH:
                exception.severity = EodException.CRITICAL
            exception.save()
        self.message_user(request, f"{queryset.count()} exception(s) severity escalated.")
    escalate_severity.short_description = "Escalate severity"