# apps/doctors/permissions.py

from rest_framework import permissions
from core.constants import UserRoles


class DoctorPermissions(permissions.BasePermission):
    """
    Custom permissions for Doctor operations
    """
    
    def has_permission(self, request, view):
        """Check if user has permission for the view"""
        user_role = request.user.role
        
        # Everyone can view doctor list (for appointment booking)
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Create/Update/Delete operations
        if view.action in ['create', 'update', 'partial_update', 'destroy']:
            return user_role in [UserRoles.SUPER_ADMIN, UserRoles.CLINIC_MANAGER]
        
        # Special actions
        if view.action in ['set_active', 'set_inactive', 'export']:
            return user_role in [UserRoles.SUPER_ADMIN, UserRoles.CLINIC_MANAGER]
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check if user has permission for specific object"""
        user_role = request.user.role
        
        # Super Admin and Clinic Manager have full access
        if user_role in [UserRoles.SUPER_ADMIN, UserRoles.CLINIC_MANAGER]:
            return True
        
        # Doctors can view and update their own profile
        if user_role == UserRoles.DOCTOR:
            if request.method in permissions.SAFE_METHODS:
                return True
            if request.method in ['PUT', 'PATCH']:
                return obj.user == request.user
        
        # Receptionists can view doctors
        if user_role == UserRoles.RECEPTIONIST and request.method in permissions.SAFE_METHODS:
            return True
        
        return False


class DoctorSchedulePermissions(permissions.BasePermission):
    """Permissions for doctor schedules"""
    
    def has_permission(self, request, view):
        user_role = request.user.role
        
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if user_role in [UserRoles.SUPER_ADMIN, UserRoles.CLINIC_MANAGER]:
            return True
        
        if user_role == UserRoles.DOCTOR:
            # Doctors can create/update their own schedules
            if request.method in ['POST', 'PUT', 'PATCH']:
                return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        user_role = request.user.role
        
        if user_role in [UserRoles.SUPER_ADMIN, UserRoles.CLINIC_MANAGER]:
            return True
        
        if user_role == UserRoles.DOCTOR:
            # Doctors can only modify their own schedules
            return obj.doctor.user == request.user
        
        return False


class DoctorLeavePermissions(permissions.BasePermission):
    """Permissions for doctor leaves"""
    
    def has_permission(self, request, view):
        user_role = request.user.role
        
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if user_role in [UserRoles.SUPER_ADMIN, UserRoles.CLINIC_MANAGER]:
            return True
        
        if user_role == UserRoles.DOCTOR:
            # Doctors can create leaves for themselves
            if request.method == 'POST':
                return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        user_role = request.user.role
        
        if user_role in [UserRoles.SUPER_ADMIN, UserRoles.CLINIC_MANAGER]:
            return True
        
        if user_role == UserRoles.DOCTOR:
            # Doctors can only modify their own leaves
            return obj.doctor.user == request.user
        
        return False