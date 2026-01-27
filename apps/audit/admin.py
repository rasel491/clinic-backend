
# apps/audit/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.http import HttpResponseForbidden

from apps.audit.models import AuditLog
from apps.audit.filters import AuditLogFilter


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Immutable audit log admin.
    """
    # readonly_fields = [f.name for f in AuditLog._meta.fields]

    list_display = (
        "timestamp",
        "branch",
        "user_email",
        "action",
        "model_name",
        "object_id",
        "ip_address",
        "device_id",
        "duration_ms",
    )

    list_filter = (
        "branch",
        "action",
        "model_name",
        "timestamp",
    )

    search_fields = (
        "user__email",
        "model_name",
        "object_id",
        "ip_address",
        "device_id",
    )

    ordering = ("-timestamp",)
    date_hierarchy = "timestamp"

    readonly_fields = (
        "branch",
        "user",
        "device_id",
        "ip_address",
        "action",
        "model_name",
        "object_id",
        "before",
        "after",
        "timestamp",
        "duration",
    )

    fieldsets = (
        ("Context", {
            "fields": (
                "branch",
                "user",
                "device_id",
                "ip_address",
            )
        }),
        ("Action", {
            "fields": (
                "action",
                "model_name",
                "object_id",
            )
        }),
        ("Data", {
            "fields": (
                "before",
                "after",
            )
        }),
        ("Timing", {
            "fields": (
                "timestamp",
                "duration",
            )
        }),
    )

    # -----------------------------
    # Permissions (IMMUTABLE)
    # -----------------------------

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # -----------------------------
    # Custom display helpers
    # -----------------------------

    @admin.display(description="User")
    def user_email(self, obj):
        if obj.user:
            return obj.user.email
        return "—"

    @admin.display(description="Duration (ms)")
    def duration_ms(self, obj):
        if not obj.duration:
            return "—"
        return int(obj.duration.total_seconds() * 1000)

    # -----------------------------
    # Extra protection
    # -----------------------------

    def get_actions(self, request):
        """
        Remove bulk delete.
        """
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions





# apps/audit/admin.py

# from django.contrib import admin
# from django.utils.html import format_html
# from django.urls import reverse
# from django.utils import timezone
# from datetime import timedelta
# import json

# from .models import AuditLog


# @admin.register(AuditLog)
# class AuditLogAdmin(admin.ModelAdmin):
#     """
#     Admin interface for AuditLog.
#     Read-only admin with hash verification.
#     """
    
#     # Make admin read-only
#     def has_add_permission(self, request):
#         return False
    
#     def has_change_permission(self, request, obj=None):
#         return False
    
#     def has_delete_permission(self, request, obj=None):
#         return False
    
#     # Display configuration
#     list_display = (
#         'id', 'timestamp', 'action', 'model_name',
#         'object_link', 'user_email', 'branch_name',
#         'device_id_short', 'duration_display', 'hash_valid'
#     )
    
#     list_filter = (
#         'action', 'model_name', 'branch', 'timestamp',
#         ('user', admin.RelatedOnlyFieldListFilter),
#     )
    
#     search_fields = (
#         'model_name', 'object_id', 'action',
#         'user__email', 'device_id', 'ip_address',
#         'record_hash'
#     )
    
#     readonly_fields = (
#         'id', 'timestamp', 'branch', 'user',
#         'device_id', 'ip_address', 'action',
#         'model_name', 'object_id', 'before_prettified',
#         'after_prettified', 'previous_hash', 'record_hash',
#         'duration', 'hash_valid_display', 'object_admin_link',
#         'chain_links'
#     )
    
#     fieldsets = (
#         ('Basic Information', {
#             'fields': (
#                 'id', 'timestamp', 'action', 
#                 'model_name', 'object_admin_link',
#                 'duration'
#             )
#         }),
#         ('User Context', {
#             'fields': (
#                 'user', 'branch', 'device_id', 'ip_address'
#             )
#         }),
#         ('Data Changes', {
#             'fields': (
#                 'before_prettified', 'after_prettified'
#             ),
#             'classes': ('collapse',)
#         }),
#         ('Hash Chain Security', {
#             'fields': (
#                 'previous_hash', 'record_hash',
#                 'hash_valid_display', 'chain_links'
#             )
#         }),
#     )
    
#     ordering = ('-timestamp',)
#     date_hierarchy = 'timestamp'
    
#     # Custom methods for display
#     def user_email(self, obj):
#         return obj.user.email if obj.user else 'System'
#     user_email.short_description = 'User'
#     user_email.admin_order_field = 'user__email'
    
#     def branch_name(self, obj):
#         return obj.branch.name if obj.branch else 'System'
#     branch_name.short_description = 'Branch'
#     branch_name.admin_order_field = 'branch__name'
    
#     def device_id_short(self, obj):
#         if obj.device_id:
#             return obj.device_id[:15] + '...' if len(obj.device_id) > 15 else obj.device_id
#         return '-'
#     device_id_short.short_description = 'Device ID'
    
#     def duration_display(self, obj):
#         if obj.duration:
#             seconds = obj.duration.total_seconds()
#             if seconds < 1:
#                 return f"{seconds*1000:.0f}ms"
#             elif seconds < 60:
#                 return f"{seconds:.1f}s"
#             else:
#                 minutes = seconds / 60
#                 return f"{minutes:.1f}min"
#         return '-'
#     duration_display.short_description = 'Duration'
    
#     def hash_valid(self, obj):
#         from .services import verify_chain_for_log
#         return verify_chain_for_log(obj)
#     hash_valid.boolean = True
#     hash_valid.short_description = 'Hash Valid'
    
#     def hash_valid_display(self, obj):
#         is_valid = self.hash_valid(obj)
#         color = 'green' if is_valid else 'red'
#         text = '✓ Valid' if is_valid else '✗ Invalid'
#         return format_html(
#             '<span style="color: {}; font-weight: bold;">{}</span>',
#             color, text
#         )
#     hash_valid_display.short_description = 'Hash Chain Status'
    
#     def before_prettified(self, obj):
#         return self._prettify_json(obj.before)
#     before_prettified.short_description = 'Before State'
    
#     def after_prettified(self, obj):
#         return self._prettify_json(obj.after)
#     after_prettified.short_description = 'After State'
    
#     def object_link(self, obj):
#         """Create clickable link to object in admin"""
#         app_label = self._get_app_label(obj.model_name)
#         model_name_lower = obj.model_name.lower()
        
#         try:
#             url = reverse(f'admin:{app_label}_{model_name_lower}_change', args=[obj.object_id])
#             return format_html('<a href="{}">{}</a>', url, obj.object_id)
#         except:
#             return obj.object_id
#     object_link.short_description = 'Object ID'
#     object_link.admin_order_field = 'object_id'
    
#     def object_admin_link(self, obj):
#         return self.object_link(obj)
#     object_admin_link.short_description = 'View Object in Admin'
    
#     def chain_links(self, obj):
#         """Show previous and next hash links"""
#         links = []
        
#         # Previous log
#         prev_log = AuditLog.objects.filter(
#             id__lt=obj.id
#         ).order_by('-id').first()
        
#         if prev_log:
#             url = reverse('admin:audit_auditlog_change', args=[prev_log.id])
#             links.append(
#                 format_html(
#                     '<strong>Previous:</strong> <a href="{}">#{}</a> ({})<br>',
#                     url, prev_log.id, prev_log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
#                 )
#             )
        
#         # Next log
#         next_log = AuditLog.objects.filter(
#             id__gt=obj.id
#         ).order_by('id').first()
        
#         if next_log:
#             url = reverse('admin:audit_auditlog_change', args=[next_log.id])
#             links.append(
#                 format_html(
#                     '<strong>Next:</strong> <a href="{}">#{}</a> ({})',
#                     url, next_log.id, next_log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
#                 )
#             )
        
#         return format_html(''.join(links)) if links else '-'
#     chain_links.short_description = 'Chain Links'
    
#     # Helper methods
#     def _prettify_json(self, data):
#         """Format JSON data for display"""
#         if not data:
#             return format_html('<em>No data</em>')
        
#         try:
#             if isinstance(data, str):
#                 data = json.loads(data)
            
#             formatted = json.dumps(data, indent=2, ensure_ascii=False)
#             return format_html('<pre style="max-height: 300px; overflow: auto;">{}</pre>', formatted)
#         except:
#             return format_html('<pre>{}</pre>', str(data))
    
#     def _get_app_label(self, model_name):
#         """Guess app label from model name"""
#         model_to_app = {
#             'User': 'accounts',
#             'Patient': 'patients',
#             'Doctor': 'doctors',
#             'Appointment': 'visits',
#             'Invoice': 'billing',
#             'Payment': 'payments',
#             'Prescription': 'prescriptions',
#             'Treatment': 'treatments',
#             'Branch': 'clinics',
#             'Role': 'accounts',
#             # Add more mappings as needed
#         }
#         return model_to_app.get(model_name, 'unknown')
    
#     # Custom actions
#     actions = ['verify_selected_chains', 'export_selected']
    
#     def verify_selected_chains(self, request, queryset):
#         """Verify hash chain for selected logs"""
#         from .services import verify_chain_for_log
        
#         verified = 0
#         invalid = 0
        
#         for log in queryset:
#             if verify_chain_for_log(log):
#                 verified += 1
#             else:
#                 invalid += 1
        
#         self.message_user(
#             request,
#             f'Verified {verified} logs, {invalid} invalid'
#         )
    
#     verify_selected_chains.short_description = "Verify selected hash chains"
    
#     def export_selected(self, request, queryset):
#         """Export selected logs"""
#         import csv
#         from django.http import HttpResponse
        
#         response = HttpResponse(content_type='text/csv')
#         response['Content-Disposition'] = 'attachment; filename="audit_logs_export.csv"'
        
#         writer = csv.writer(response)
#         writer.writerow([
#             'ID', 'Timestamp', 'Action', 'Model', 'Object ID',
#             'User', 'Branch', 'Device ID', 'IP Address',
#             'Duration (s)', 'Previous Hash', 'Record Hash'
#         ])
        
#         for log in queryset:
#             writer.writerow([
#                 log.id,
#                 log.timestamp,
#                 log.action,
#                 log.model_name,
#                 log.object_id,
#                 log.user.email if log.user else '',
#                 log.branch.name if log.branch else '',
#                 log.device_id or '',
#                 log.ip_address or '',
#                 log.duration.total_seconds() if log.duration else '',
#                 log.previous_hash,
#                 log.record_hash
#             ])
        
#         return response
    
#     export_selected.short_description = "Export selected logs to CSV"
    
#     # Change list customization
#     def changelist_view(self, request, extra_context=None):
#         """Add statistics to change list"""
#         extra_context = extra_context or {}
        
#         # Add statistics
#         today = timezone.now().date()
#         week_ago = today - timedelta(days=7)
        
#         extra_context['stats'] = {
#             'total': AuditLog.objects.count(),
#             'today': AuditLog.objects.filter(timestamp__date=today).count(),
#             'this_week': AuditLog.objects.filter(timestamp__date__gte=week_ago).count(),
#             'top_models': AuditLog.objects.values('model_name').annotate(
#                 count=models.Count('id')
#             ).order_by('-count')[:5],
#             'top_actions': AuditLog.objects.values('action').annotate(
#                 count=models.Count('id')
#             ).order_by('-count')[:5],
#         }
        
#         return super().changelist_view(request, extra_context=extra_context)
    
#     # Custom templates
#     change_list_template = 'admin/audit/auditlog/change_list.html'
#     change_form_template = 'admin/audit/auditlog/change_form.html'


# # Custom admin site actions
# def verify_all_chains(modeladmin, request, queryset):
#     """Verify all audit log chains"""
#     from .services import verify_chain
    
#     broken_links = verify_chain()
    
#     if broken_links:
#         modeladmin.message_user(
#             request,
#             f'Found {len(broken_links)} broken links in chain',
#             level='ERROR'
#         )
#     else:
#         modeladmin.message_user(
#             request,
#             'All hash chains verified successfully',
#             level='SUCCESS'
#         )


# verify_all_chains.short_description = "Verify all hash chains"


# def cleanup_old_logs(modeladmin, request, queryset):
#     """Archive logs older than retention period"""
#     from django.conf import settings
#     from datetime import timedelta
    
#     retention_days = getattr(settings, 'AUDIT_RETENTION_DAYS', 365)
#     cutoff_date = timezone.now() - timedelta(days=retention_days)
    
#     old_logs = AuditLog.objects.filter(timestamp__lt=cutoff_date)
#     count = old_logs.count()
    
#     # In production, you would archive instead of delete
#     # For now, just show count
#     modeladmin.message_user(
#         request,
#         f'Found {count} logs older than {retention_days} days',
#         level='INFO'
#     )


# cleanup_old_logs.short_description = "Find logs for archiving"


# # Register admin actions
# admin.site.add_action(verify_all_chains, 'verify_all_chains')
# admin.site.add_action(cleanup_old_logs, 'cleanup_old_logs')