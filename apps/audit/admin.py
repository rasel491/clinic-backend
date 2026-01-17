# apps/audit/admin.py
from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'model_name', 'object_id', 'branch')
    list_filter = ('action', 'model_name', 'branch', 'timestamp')
    search_fields = ('user__email', 'user__full_name', 'object_id', 'ip_address')
    readonly_fields = ('timestamp', 'duration', 'before', 'after', 'ip_address', 'device_id')
    date_hierarchy = 'timestamp'
    
    # Make audit logs read-only in admin (immutable!)
    def has_add_permission(self, request):
        return False  # Can't create audit logs manually
    
    def has_change_permission(self, request, obj=None):
        return False  # Can't modify audit logs
    
    def has_delete_permission(self, request, obj=None):
        return False  # Can't delete audit logs
    
    # Optional: Pretty display for JSON fields
    def formatted_before(self, obj):
        import json
        return json.dumps(obj.before, indent=2) if obj.before else '-'
    
    def formatted_after(self, obj):
        import json
        return json.dumps(obj.after, indent=2) if obj.after else '-'
    
    formatted_before.short_description = 'Before State'
    formatted_after.short_description = 'After State'
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('timestamp', 'user', 'branch', 'action', 'model_name', 'object_id')
        }),
        ('Technical Details', {
            'fields': ('device_id', 'ip_address', 'duration')
        }),
        ('State Changes', {
            'fields': ('formatted_before', 'formatted_after'),
            'classes': ('collapse',)  # Collapsible section
        }),
    )