# # core/permissions.py (old)

# from rest_framework.permissions import BasePermission
# from rest_framework import permissions
# from .constants import UserRoles

# class IsAuthenticatedAndActive(BasePermission):
#     def has_permission(self, request, view):
#         return bool(
#             request.user
#             and request.user.is_authenticated
#             and request.user.is_active
#         )




# class IsPatient(permissions.BasePermission):
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.PATIENT

# class IsFrontDesk(permissions.BasePermission):
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.FRONT_DESK

# class IsDoctor(permissions.BasePermission):
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.DOCTOR

# class IsCashier(permissions.BasePermission):
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.CASHIER

# class IsManager(permissions.BasePermission):
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.MANAGER

# class IsAdmin(permissions.BasePermission):
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.ADMIN

# class IsStaff(permissions.BasePermission):
#     def has_permission(self, request, view):
#         return request.user.role in [
#             UserRoles.FRONT_DESK,
#             UserRoles.DOCTOR, 
#             UserRoles.CASHIER,
#             UserRoles.MANAGER,
#             UserRoles.ADMIN
#         ]

# class CanOverride(permissions.BasePermission):
#     """For actions requiring manager override (refunds, waivers)"""
#     def has_permission(self, request, view):
#         if request.user.role not in [UserRoles.MANAGER, UserRoles.ADMIN]:
#             return False
#         # Check if override reason is provided
#         override_reason = request.data.get('override_reason') or request.query_params.get('override_reason')
#         return bool(override_reason)



# core/permissions.py (new )
# from rest_framework.permissions import BasePermission
# from rest_framework import permissions
# from .constants import UserRoles

# class IsAuthenticatedAndActive(BasePermission):
#     """Ensure user is authenticated and active"""
#     def has_permission(self, request, view):
#         return bool(
#             request.user
#             and request.user.is_authenticated
#             and request.user.is_active
#         )

# # ===========================================
# # CORE PERMISSION CLASSES (using your actual roles)
# # ===========================================
# class IsAdmin(permissions.BasePermission):
#     """Alias for IsSuperAdmin - matches accounts/views.py import"""
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.SUPER_ADMIN
    
# class IsManager(permissions.BasePermission):
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.MANAGER
    
# class IsAuditor(permissions.BasePermission):
#     pass
# class IsSuperAdmin(permissions.BasePermission):
#     """Check if user is super admin (SUPER_ADMIN)"""
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.SUPER_ADMIN

# class IsAdminUser(permissions.BasePermission):
#     """Alias for IsSuperAdmin - matches views.py import"""
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.SUPER_ADMIN

# class IsClinicManager(permissions.BasePermission):
#     """Check if user is clinic manager"""
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.CLINIC_MANAGER

# class IsManager(permissions.BasePermission):
#     """Alias for IsClinicManager - matches views.py import"""
#     def has_permission(self, request, view):
#         return request.user.role in [UserRoles.CLINIC_MANAGER, UserRoles.SUPER_ADMIN]

# class IsDoctor(permissions.BasePermission):
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.DOCTOR

# class IsReceptionist(permissions.BasePermission):
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.RECEPTIONIST

# class IsFrontDesk(permissions.BasePermission):
#     """Alias for IsReceptionist (backward compatibility)"""
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.RECEPTIONIST

# class IsCashier(permissions.BasePermission):
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.CASHIER

# class IsLabTechnician(permissions.BasePermission):
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.LAB_TECHNICIAN

# class IsInventoryManager(permissions.BasePermission):
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.INVENTORY_MANAGER

# # ===========================================
# # COMPOSITE PERMISSION CLASSES
# # ===========================================

# class IsStaff(permissions.BasePermission):
#     """Check if user is any staff member (not patient)"""
#     def has_permission(self, request, view):
#         return request.user.role in [
#             UserRoles.RECEPTIONIST,
#             UserRoles.DOCTOR,
#             UserRoles.CASHIER,
#             UserRoles.CLINIC_MANAGER,
#             UserRoles.LAB_TECHNICIAN,
#             UserRoles.INVENTORY_MANAGER,
#             UserRoles.SUPER_ADMIN
#         ]

# class IsMedicalStaff(permissions.BasePermission):
#     """Check if user is medical staff"""
#     def has_permission(self, request, view):
#         return request.user.role in [UserRoles.DOCTOR, UserRoles.LAB_TECHNICIAN]

# class IsAdministrativeStaff(permissions.BasePermission):
#     """Check if user is administrative staff"""
#     def has_permission(self, request, view):
#         return request.user.role in [
#             UserRoles.RECEPTIONIST,
#             UserRoles.CASHIER,
#             UserRoles.CLINIC_MANAGER,
#             UserRoles.INVENTORY_MANAGER,
#             UserRoles.SUPER_ADMIN
#         ]

# # ===========================================
# # BUSINESS LOGIC PERMISSIONS
# # ===========================================

# class CanOverride(permissions.BasePermission):
#     """For actions requiring manager override (refunds, waivers)"""
#     def has_permission(self, request, view):
#         # Only clinic managers and super admins can override
#         if request.user.role not in [UserRoles.CLINIC_MANAGER, UserRoles.SUPER_ADMIN]:
#             return False
        
#         # Check if override reason is provided
#         override_reason = request.data.get('override_reason') or request.query_params.get('override_reason')
#         return bool(override_reason)

# class HasBranchAccess(permissions.BasePermission):
#     """Check if user has access to the branch in the request"""
#     def has_permission(self, request, view):
#         # Get branch from request (set by BranchMiddleware)
#         branch_id = getattr(request, 'branch_id', None)
        
#         # Super admins can access all branches
#         if request.user.role == UserRoles.SUPER_ADMIN:
#             return True
        
#         # Clinic managers can access all branches
#         if request.user.role == UserRoles.CLINIC_MANAGER:
#             return True
        
#         # Check if user is assigned to this branch
#         if hasattr(request.user, 'user_branches'):
#             if branch_id:
#                 return request.user.user_branches.filter(
#                     branch_id=branch_id, is_active=True
#                 ).exists()
#             else:
#                 # If no branch specified, allow if user has any branch access
#                 return request.user.user_branches.filter(is_active=True).exists()
        
#         return False

# class IsOwnerOrStaff(permissions.BasePermission):
#     """Check if user owns the record or is staff"""
#     def has_object_permission(self, request, view, obj):
#         # Staff can access
#         if request.user.role != UserRoles.PATIENT:
#             return True
        
#         # Check if user owns the object
#         if hasattr(obj, 'patient') and obj.patient.user == request.user:
#             return True
        
#         if hasattr(obj, 'user') and obj.user == request.user:
#             return True
        
#         return False

# class IsReadOnly(permissions.BasePermission):
#     """Allow only read operations"""
#     def has_permission(self, request, view):
#         return request.method in permissions.SAFE_METHODS

# # ===========================================
# # QUICK PERMISSION MIXINS (for views)
# # ===========================================

# class PermissionMixin:
#     """Quick permission mixins for common patterns"""
    
#     @classmethod
#     def super_admin_only(cls):
#         return [IsSuperAdmin]
    
#     @classmethod
#     def manager_and_above(cls):
#         return [IsManager]
    
#     @classmethod  
#     def doctor_and_above(cls):
#         return [IsDoctor | IsManager]
    
#     @classmethod
#     def receptionist_and_above(cls):
#         return [IsReceptionist | IsDoctor | IsManager]
    
#     @classmethod
#     def cashier_and_above(cls):
#         return [IsCashier | IsManager]
    
#     @classmethod
#     def staff_only(cls):
#         return [IsStaff]
    
#     @classmethod
#     def with_branch_access(cls):
#         return [IsAuthenticatedAndActive & HasBranchAccess]
    



# class CanPerformEOD(permissions.BasePermission):
#     """Check if user can perform EOD operations"""
#     def has_permission(self, request, view):
#         return request.user.role in [
#             UserRoles.CLINIC_MANAGER, 
#             UserRoles.SUPER_ADMIN,
#             UserRoles.CASHIER  # Cashiers can prepare, but managers approve
#         ]

# class CanApproveEOD(permissions.BasePermission):
#     """Check if user can approve/lock EOD"""
#     def has_permission(self, request, view):
#         return request.user.role in [
#             UserRoles.CLINIC_MANAGER, 
#             UserRoles.SUPER_ADMIN
#         ]

# class CanReverseEOD(permissions.BasePermission):
#     """Check if user can reverse locked EOD (strict control)"""
#     def has_permission(self, request, view):
#         return request.user.role == UserRoles.SUPER_ADMIN  # Only super admin




#COMPLETE UPDATED core/permissions.py
# # core/permissions.py
from rest_framework.permissions import BasePermission
from rest_framework import permissions
from .constants import UserRoles

class IsAuthenticatedAndActive(BasePermission):
    """Ensure user is authenticated and active"""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
        )


class HasPermission(permissions.BasePermission):
    """
    Check if user has specific permission for a view/action.
    This class is used as a base for views that require custom permission checks.
    """
    def has_permission(self, request, view):
        # By default, just check if user is authenticated and active
        return bool(request.user and request.user.is_authenticated and request.user.is_active)
    
    def has_object_permission(self, request, view, obj):
        # By default, allow if user has view permission
        return self.has_permission(request, view)

# ===========================================
# CORE PERMISSION CLASSES (using your actual roles)
# ===========================================
class IsAdmin(permissions.BasePermission):
    """Alias for IsSuperAdmin - matches accounts/views.py import"""
    def has_permission(self, request, view):
        return request.user.role == UserRoles.SUPER_ADMIN
    
class IsManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRoles.MANAGER
    
class IsAuditor(permissions.BasePermission):
    pass

class IsSuperAdmin(permissions.BasePermission):
    """Check if user is super admin (SUPER_ADMIN)"""
    def has_permission(self, request, view):
        return request.user.role == UserRoles.SUPER_ADMIN

class IsAdminUser(permissions.BasePermission):
    """Alias for IsSuperAdmin - matches views.py import"""
    def has_permission(self, request, view):
        return request.user.role == UserRoles.SUPER_ADMIN

class IsClinicManager(permissions.BasePermission):
    """Check if user is clinic manager"""
    def has_permission(self, request, view):
        return request.user.role == UserRoles.CLINIC_MANAGER

class IsBranchManager(permissions.BasePermission):
    """Check if user is clinic manager (for branch settings)"""
    def has_permission(self, request, view):
        return request.user.role in [UserRoles.CLINIC_MANAGER, UserRoles.SUPER_ADMIN]

class IsDoctor(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRoles.DOCTOR

class IsReceptionist(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRoles.RECEPTIONIST

class IsFrontDesk(permissions.BasePermission):
    """Alias for IsReceptionist (backward compatibility)"""
    def has_permission(self, request, view):
        return request.user.role == UserRoles.RECEPTIONIST

class IsCashier(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRoles.CASHIER

class IsLabTechnician(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRoles.LAB_TECHNICIAN

class IsInventoryManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRoles.INVENTORY_MANAGER

# ===========================================
# COMPOSITE PERMISSION CLASSES
# ===========================================

class IsStaff(permissions.BasePermission):
    """Check if user is any staff member (not patient)"""
    def has_permission(self, request, view):
        return request.user.role in [
            UserRoles.RECEPTIONIST,
            UserRoles.DOCTOR,
            UserRoles.CASHIER,
            UserRoles.CLINIC_MANAGER,
            UserRoles.LAB_TECHNICIAN,
            UserRoles.INVENTORY_MANAGER,
            UserRoles.SUPER_ADMIN
        ]

class IsMedicalStaff(permissions.BasePermission):
    """Check if user is medical staff"""
    def has_permission(self, request, view):
        return request.user.role in [UserRoles.DOCTOR, UserRoles.LAB_TECHNICIAN]

class IsAdministrativeStaff(permissions.BasePermission):
    """Check if user is administrative staff"""
    def has_permission(self, request, view):
        return request.user.role in [
            UserRoles.RECEPTIONIST,
            UserRoles.CASHIER,
            UserRoles.CLINIC_MANAGER,
            UserRoles.INVENTORY_MANAGER,
            UserRoles.SUPER_ADMIN
        ]

# ===========================================
# BUSINESS LOGIC PERMISSIONS
# ===========================================

class CanOverride(permissions.BasePermission):
    """For actions requiring manager override (refunds, waivers)"""
    def has_permission(self, request, view):
        # Only clinic managers and super admins can override
        if request.user.role not in [UserRoles.CLINIC_MANAGER, UserRoles.SUPER_ADMIN]:
            return False
        
        # Check if override reason is provided
        override_reason = request.data.get('override_reason') or request.query_params.get('override_reason')
        return bool(override_reason)

class HasBranchAccess(permissions.BasePermission):
    """Check if user has access to the branch in the request"""
    def has_permission(self, request, view):
        # Get branch from request (set by BranchMiddleware)
        branch_id = getattr(request, 'branch_id', None)
        
        # Super admins can access all branches
        if request.user.role == UserRoles.SUPER_ADMIN:
            return True
        
        # Clinic managers can access all branches
        if request.user.role == UserRoles.CLINIC_MANAGER:
            return True
        
        # Check if user is assigned to this branch
        if hasattr(request.user, 'user_branches'):
            if branch_id:
                return request.user.user_branches.filter(
                    branch_id=branch_id, is_active=True
                ).exists()
            else:
                # If no branch specified, allow if user has any branch access
                return request.user.user_branches.filter(is_active=True).exists()
        
        return False

class IsOwnerOrStaff(permissions.BasePermission):
    """Check if user owns the record or is staff"""
    def has_object_permission(self, request, view, obj):
        # Staff can access
        if request.user.role != UserRoles.PATIENT:
            return True
        
        # Check if user owns the object
        if hasattr(obj, 'patient') and obj.patient.user == request.user:
            return True
        
        if hasattr(obj, 'user') and obj.user == request.user:
            return True
        
        return False

class IsReadOnly(permissions.BasePermission):
    """Allow only read operations"""
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS

# ===========================================
# EOD PERMISSIONS
# ===========================================

class CanPerformEOD(permissions.BasePermission):
    """Check if user can perform EOD operations"""
    def has_permission(self, request, view):
        return request.user.role in [
            UserRoles.CLINIC_MANAGER, 
            UserRoles.SUPER_ADMIN,
            UserRoles.CASHIER  # Cashiers can prepare, but managers approve
        ]

class CanApproveEOD(permissions.BasePermission):
    """Check if user can approve/lock EOD"""
    def has_permission(self, request, view):
        return request.user.role in [
            UserRoles.CLINIC_MANAGER, 
            UserRoles.SUPER_ADMIN
        ]

class CanReverseEOD(permissions.BasePermission):
    """Check if user can reverse locked EOD (strict control)"""
    def has_permission(self, request, view):
        return request.user.role == UserRoles.SUPER_ADMIN  # Only super admin

# ===========================================
# QUICK PERMISSION MIXINS (for views)
# ===========================================

class PermissionMixin:
    """Quick permission mixins for common patterns"""
    
    @classmethod
    def super_admin_only(cls):
        return [IsSuperAdmin]
    
    @classmethod
    def manager_and_above(cls):
        return [IsClinicManager]
    
    @classmethod  
    def doctor_and_above(cls):
        return [IsDoctor | IsClinicManager]
    
    @classmethod
    def receptionist_and_above(cls):
        return [IsReceptionist | IsDoctor | IsClinicManager]
    
    @classmethod
    def cashier_and_above(cls):
        return [IsCashier | IsClinicManager]
    
    @classmethod
    def staff_only(cls):
        return [IsStaff]
    
    @classmethod
    def with_branch_access(cls):
        return [IsAuthenticatedAndActive & HasBranchAccess]