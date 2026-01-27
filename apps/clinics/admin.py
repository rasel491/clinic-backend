# # clinic/Backend/apps/clinics/admin.py
# from django.contrib import admin
# from django.utils.html import format_html
# from django.urls import reverse
# from .models import Branch, Counter

# @admin.register(Branch)
# class BranchAdmin(admin.ModelAdmin):
#     list_display = [
#         'code', 'name', 'phone', 'is_active', 
#         'is_eod_locked', 'eod_locked_at_display', 'created_at_display'
#     ]
#     list_filter = ['is_active', 'is_eod_locked', 'created_at']
#     search_fields = ['code', 'name', 'address', 'phone', 'email']
#     readonly_fields = [
#         'is_eod_locked', 'eod_locked_at', 'eod_locked_by',
#         'created_at', 'updated_at', 'deleted_at', 'deleted_by',
#         'created_by', 'updated_by'
#     ]
#     fieldsets = (
#         ('Basic Information', {
#             'fields': ('name', 'code', 'is_active')
#         }),
#         ('Contact Information', {
#             'fields': ('address', 'phone', 'email')
#         }),
#         ('Operational Hours', {
#             'fields': ('opening_time', 'closing_time')
#         }),
#         ('EOD Status', {
#             'fields': ('is_eod_locked', 'eod_locked_at', 'eod_locked_by'),
#             'classes': ('collapse',)
#         }),
#         ('Audit Information', {
#             'fields': (
#                 'created_by', 'created_at',
#                 'updated_by', 'updated_at',
#                 'deleted_by', 'deleted_at'
#             ),
#             'classes': ('collapse',)
#         }),
#     )
    
#     def created_at_display(self, obj):
#         """Format created_at for display"""
#         if obj.created_at:
#             return obj.created_at.strftime('%Y-%m-%d %H:%M')
#         return "-"
#     created_at_display.short_description = 'Created At'
#     created_at_display.admin_order_field = 'created_at'
    
#     def eod_locked_at_display(self, obj):
#         """Format eod_locked_at for display"""
#         if obj.eod_locked_at:
#             return obj.eod_locked_at.strftime('%Y-%m-%d %H:%M')
#         return "-"
#     eod_locked_at_display.short_description = 'EOD Locked At'
#     eod_locked_at_display.admin_order_field = 'eod_locked_at'
    
#     def has_delete_permission(self, request, obj=None):
#         """Prevent hard delete from admin"""
#         return False
    
#     def save_model(self, request, obj, form, change):
#         if not change:
#             obj.created_by = request.user
#         obj.updated_by = request.user
#         super().save_model(request, obj, form, change)

# @admin.register(Counter)
# class CounterAdmin(admin.ModelAdmin):
#     list_display = [
#         'branch_code', 'counter_number', 'name', 
#         'device_id_display', 'is_active', 'created_at_display'
#     ]
#     list_filter = ['is_active', 'branch', 'created_at']
#     search_fields = ['name', 'device_id', 'branch__code', 'branch__name']
#     readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
#     list_select_related = ['branch']
    
#     fieldsets = (
#         ('Basic Information', {
#             'fields': ('branch', 'counter_number', 'name', 'is_active')
#         }),
#         ('Device Information', {
#             'fields': ('device_id',),
#             'classes': ('collapse',)
#         }),
#         ('Audit Information', {
#             'fields': ('created_by', 'created_at', 'updated_by', 'updated_at'),
#             'classes': ('collapse',)
#         }),
#     )
    
#     def branch_code(self, obj):
#         return obj.branch.code
#     branch_code.short_description = 'Branch'
#     branch_code.admin_order_field = 'branch__code'
    
#     def device_id_display(self, obj):
#         """Display device ID with truncation if too long"""
#         if obj.device_id:
#             if len(obj.device_id) > 20:
#                 return f"{obj.device_id[:20]}..."
#             return obj.device_id
#         return "-"
#     device_id_display.short_description = 'Device ID'
    
#     def created_at_display(self, obj):
#         """Format created_at for display"""
#         if obj.created_at:
#             return obj.created_at.strftime('%Y-%m-%d %H:%M')
#         return "-"
#     created_at_display.short_description = 'Created'
#     created_at_display.admin_order_field = 'created_at'
    
#     def view_branch_link(self, obj):
#         url = reverse('admin:clinics_branch_change', args=[obj.branch.id])
#         return format_html('<a href="{}">{}</a>', url, obj.branch.name)
#     view_branch_link.short_description = 'Branch Details'


# # clinic/Backend/apps/clinics/admin.py