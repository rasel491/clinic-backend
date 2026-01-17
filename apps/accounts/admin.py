from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Role, UserRole, UserBranch, UserDevice


# === USER ADMIN ===
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User admin with role-based display"""
    
    list_display = ('email', 'full_name', 'phone', 'is_active', 'is_staff', 'current_branch', 'created_at')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'current_branch')
    search_fields = ('email', 'full_name', 'phone')
    ordering = ('-created_at',)
    
    # Fields for viewing
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal Info'), {'fields': ('full_name', 'phone')}),
        (_('Branch & Session'), {'fields': ('current_branch',)}),
        (_('Verification'), {'fields': ('is_email_verified', 'is_phone_verified')}),
        (_('Security'), {
            'fields': ('last_login_ip', 'failed_login_attempts', 'locked_until'),
            'classes': ('collapse',)
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {
            'fields': ('last_login', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    # Fields for creating
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'phone', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ('last_login', 'created_at', 'updated_at', 'last_login_ip')
    
    # Inline for related models
    inlines = []


# === ROLE ADMIN ===
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Role admin - simple management"""
    
    list_display = ('code', 'name', 'permissions_count')
    list_filter = ('code',)
    search_fields = ('code', 'name')
    readonly_fields = ('code',)
    
    def permissions_count(self, obj):
        return len(obj.permissions) if obj.permissions else 0
    permissions_count.short_description = 'Permissions Count'


# === USER ROLE ADMIN ===
class UserRoleInline(admin.TabularInline):
    """Inline for assigning roles to users"""
    model = UserRole
    fk_name = 'user'  # ✅ SPECIFY: Use the 'user' ForeignKey (not 'assigned_by')
    extra = 1
    raw_id_fields = ('role', 'assigned_by')
    readonly_fields = ('assigned_at',)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Auto-set assigned_by to current user
        if db_field.name == 'assigned_by':
            kwargs['initial'] = request.user.id
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# === USER BRANCH ADMIN ===
class UserBranchInline(admin.TabularInline):
    """Inline for assigning branches to users"""
    model = UserBranch
    fk_name = 'user'  # ✅ SPECIFY: Use the 'user' ForeignKey (not 'assigned_by')
    extra = 1
    raw_id_fields = ('branch', 'assigned_by')
    readonly_fields = ('assigned_at',)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Auto-set assigned_by to current user
        if db_field.name == 'assigned_by':
            kwargs['initial'] = request.user.id
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# === USER DEVICE ADMIN ===
@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    """Device tracking admin - read-only for security"""
    
    list_display = ('user', 'device_type', 'device_name', 'ip_address', 'is_active', 'last_seen_at')
    list_filter = ('device_type', 'is_active', 'last_seen_at')
    search_fields = ('user__email', 'device_id', 'ip_address')
    readonly_fields = ('user', 'device_id', 'device_type', 'device_name', 'user_agent', 
                      'ip_address', 'refresh_token_hash', 'created_at', 'last_seen_at')
    
    # Make it read-only
    def has_add_permission(self, request):
        return False  # Devices are created automatically by system
    
    def has_change_permission(self, request, obj=None):
        return False  # Cannot modify device records
    
    def has_delete_permission(self, request, obj=None):
        return True  # Can delete (for cleaning up old devices)


# === CUSTOM ADMIN FOR USER WITH INLINES ===
# Override the UserAdmin to add inlines
class CustomUserAdmin(UserAdmin):
    """User admin with role and branch inlines"""
    inlines = [UserRoleInline, UserBranchInline]


# Re-register User with custom admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


# === USER ROLE STANDALONE ADMIN ===
@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    """Standalone UserRole admin for bulk management"""
    
    list_display = ('user', 'role', 'is_active', 'assigned_at', 'assigned_by')
    list_filter = ('is_active', 'role', 'assigned_at')
    search_fields = ('user__email', 'role__code')
    raw_id_fields = ('user', 'role', 'assigned_by')
    readonly_fields = ('assigned_at',)
    
    list_select_related = ('user', 'role', 'assigned_by')


# === USER BRANCH STANDALONE ADMIN ===
@admin.register(UserBranch)
class UserBranchAdmin(admin.ModelAdmin):
    """Standalone UserBranch admin for bulk management"""
    
    list_display = ('user', 'branch', 'is_active', 'is_primary', 'assigned_at', 'assigned_by')
    list_filter = ('is_active', 'is_primary', 'branch')
    search_fields = ('user__email', 'branch__name')
    raw_id_fields = ('user', 'branch', 'assigned_by')
    readonly_fields = ('assigned_at',)
    
    list_select_related = ('user', 'branch', 'assigned_by')


# === ADMIN ACTIONS ===
def activate_users(modeladmin, request, queryset):
    """Admin action to activate users"""
    queryset.update(is_active=True)
activate_users.short_description = "Activate selected users"

def deactivate_users(modeladmin, request, queryset):
    """Admin action to deactivate users"""
    queryset.update(is_active=False)
deactivate_users.short_description = "Deactivate selected users"

def assign_staff_role(modeladmin, request, queryset):
    """Admin action to assign staff role"""
    from .models import Role, UserRole
    
    staff_roles = ['FRONT_DESK', 'DOCTOR', 'CASHIER', 'MANAGER']
    roles = Role.objects.filter(code__in=staff_roles)
    
    for user in queryset:
        for role in roles:
            UserRole.objects.get_or_create(
                user=user,
                role=role,
                defaults={'assigned_by': request.user}
            )
assign_staff_role.short_description = "Assign staff roles (Front Desk, Doctor, Cashier, Manager)"

# Add actions to UserAdmin
UserAdmin.actions = [activate_users, deactivate_users, assign_staff_role]







# from django.contrib import admin
# from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
# from django.utils.translation import gettext_lazy as _
# from .models import User, Role, UserRole, UserBranch, UserDevice


# # === USER ROLE INLINE (FIXED) ===
# class UserRoleInline(admin.TabularInline):
#     """Inline for assigning roles to users"""
#     model = UserRole
#     fk_name = 'user'  # ✅ SPECIFY: Use the 'user' ForeignKey (not 'assigned_by')
#     extra = 1
#     raw_id_fields = ('role', 'assigned_by')
#     readonly_fields = ('assigned_at',)
    
#     def formfield_for_foreignkey(self, db_field, request, **kwargs):
#         # Auto-set assigned_by to current user
#         if db_field.name == 'assigned_by':
#             kwargs['initial'] = request.user.id
#         return super().formfield_for_foreignkey(db_field, request, **kwargs)


# # === USER BRANCH INLINE (FIXED) ===
# class UserBranchInline(admin.TabularInline):
#     """Inline for assigning branches to users"""
#     model = UserBranch
#     fk_name = 'user'  # ✅ SPECIFY: Use the 'user' ForeignKey (not 'assigned_by')
#     extra = 1
#     raw_id_fields = ('branch', 'assigned_by')
#     readonly_fields = ('assigned_at',)
    
#     def formfield_for_foreignkey(self, db_field, request, **kwargs):
#         # Auto-set assigned_by to current user
#         if db_field.name == 'assigned_by':
#             kwargs['initial'] = request.user.id
#         return super().formfield_for_foreignkey(db_field, request, **kwargs)


# # === USER ADMIN ===
# class CustomUserAdmin(BaseUserAdmin):
#     """Custom User admin with role and branch inlines"""
    
#     list_display = ('email', 'full_name', 'phone', 'is_active', 'is_staff', 'current_branch', 'created_at')
#     list_filter = ('is_active', 'is_staff', 'is_superuser', 'current_branch')
#     search_fields = ('email', 'full_name', 'phone')
#     ordering = ('-created_at',)
    
#     # Fields for viewing
#     fieldsets = (
#         (None, {'fields': ('email', 'password')}),
#         (_('Personal Info'), {'fields': ('full_name', 'phone')}),
#         (_('Branch & Session'), {'fields': ('current_branch',)}),
#         (_('Verification'), {'fields': ('is_email_verified', 'is_phone_verified')}),
#         (_('Security'), {
#             'fields': ('last_login_ip', 'failed_login_attempts', 'locked_until'),
#             'classes': ('collapse',)
#         }),
#         (_('Permissions'), {
#             'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
#         }),
#         (_('Important dates'), {
#             'fields': ('last_login', 'created_at', 'updated_at'),
#             'classes': ('collapse',)
#         }),
#     )
    
#     # Fields for creating
#     add_fieldsets = (
#         (None, {
#             'classes': ('wide',),
#             'fields': ('email', 'full_name', 'phone', 'password1', 'password2'),
#         }),
#     )
    
#     readonly_fields = ('last_login', 'created_at', 'updated_at', 'last_login_ip')
    
#     # ✅ FIXED: Add inlines with proper fk_name
#     inlines = [UserRoleInline, UserBranchInline]
    
#     # Custom admin actions
#     actions = ['activate_users', 'deactivate_users', 'assign_staff_role']
    
#     @admin.action(description="Activate selected users")
#     def activate_users(self, request, queryset):
#         queryset.update(is_active=True)
    
#     @admin.action(description="Deactivate selected users")
#     def deactivate_users(self, request, queryset):
#         queryset.update(is_active=False)
    
#     @admin.action(description="Assign staff roles")
#     def assign_staff_role(self, request, queryset):
#         from .models import Role, UserRole
#         staff_roles = ['FRONT_DESK', 'DOCTOR', 'CASHIER', 'MANAGER']
#         roles = Role.objects.filter(code__in=staff_roles)
        
#         for user in queryset:
#             for role in roles:
#                 UserRole.objects.get_or_create(
#                     user=user,
#                     role=role,
#                     defaults={'assigned_by': request.user}
#                 )


# # === ROLE ADMIN ===
# @admin.register(Role)
# class RoleAdmin(admin.ModelAdmin):
#     """Role admin - simple management"""
    
#     list_display = ('code', 'name', 'permissions_count')
#     list_filter = ('code',)
#     search_fields = ('code', 'name')
#     readonly_fields = ('code',)
    
#     def permissions_count(self, obj):
#         return len(obj.permissions) if obj.permissions else 0
#     permissions_count.short_description = 'Permissions Count'


# # === USER DEVICE ADMIN ===
# @admin.register(UserDevice)
# class UserDeviceAdmin(admin.ModelAdmin):
#     """Device tracking admin - read-only for security"""
    
#     list_display = ('user', 'device_type', 'device_name', 'ip_address', 'is_active', 'last_seen_at')
#     list_filter = ('device_type', 'is_active', 'last_seen_at')
#     search_fields = ('user__email', 'device_id', 'ip_address')
#     readonly_fields = ('user', 'device_id', 'device_type', 'device_name', 'user_agent', 
#                       'ip_address', 'refresh_token_hash', 'created_at', 'last_seen_at')
    
#     # Make it read-only
#     def has_add_permission(self, request):
#         return False  # Devices are created automatically by system
    
#     def has_change_permission(self, request, obj=None):
#         return False  # Cannot modify device records
    
#     def has_delete_permission(self, request, obj=None):
#         return True  # Can delete (for cleaning up old devices)


# # === USER ROLE STANDALONE ADMIN ===
# @admin.register(UserRole)
# class UserRoleAdmin(admin.ModelAdmin):
#     """Standalone UserRole admin for bulk management"""
    
#     list_display = ('user', 'role', 'is_active', 'assigned_at', 'assigned_by')
#     list_filter = ('is_active', 'role', 'assigned_at')
#     search_fields = ('user__email', 'role__code')
#     raw_id_fields = ('user', 'role', 'assigned_by')
#     readonly_fields = ('assigned_at',)
    
#     list_select_related = ('user', 'role', 'assigned_by')


# # === USER BRANCH STANDALONE ADMIN ===
# @admin.register(UserBranch)
# class UserBranchAdmin(admin.ModelAdmin):
#     """Standalone UserBranch admin for bulk management"""
    
#     list_display = ('user', 'branch', 'is_active', 'is_primary', 'assigned_at', 'assigned_by')
#     list_filter = ('is_active', 'is_primary', 'branch')
#     search_fields = ('user__email', 'branch__name')
#     raw_id_fields = ('user', 'branch', 'assigned_by')
#     readonly_fields = ('assigned_at',)
    
#     list_select_related = ('user', 'branch', 'assigned_by')


# # === REGISTER ALL MODELS ===
# admin.site.register(User, CustomUserAdmin)
# # Role, UserDevice, UserRole, UserBranch already registered with @admin.register