# apps/prescriptions/permissions.py

from rest_framework import permissions
from core.constants import UserRoles


class PrescriptionPermissions(permissions.BasePermission):
    """Permissions for Prescription operations"""
    
    def has_permission(self, request, view):
        user_role = request.user.role
        
        # Everyone can view prescriptions (with filters)
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Create/Update/Delete operations
        if view.action in ['create', 'update', 'partial_update', 'destroy']:
            return user_role in [
                UserRoles.DOCTOR, 
                UserRoles.CLINIC_MANAGER, 
                UserRoles.SUPER_ADMIN
            ]
        
        # Special actions
        if view.action in ['dispense', 'refill', 'sign', 'print']:
            return user_role in [
                UserRoles.DOCTOR,
                UserRoles.CASHIER,
                UserRoles.CLINIC_MANAGER,
                UserRoles.SUPER_ADMIN
            ]
        
        return True
    
    def has_object_permission(self, request, view, obj):
        user_role = request.user.role
        
        # Super Admin and Clinic Manager have full access
        if user_role in [UserRoles.SUPER_ADMIN, UserRoles.CLINIC_MANAGER]:
            return True
        
        # Doctors can access their own prescriptions
        if user_role == UserRoles.DOCTOR:
            if request.method in permissions.SAFE_METHODS:
                return True
            if request.method in ['PUT', 'PATCH']:
                return obj.doctor.user == request.user
        
        # Cashiers can view and dispense prescriptions
        if user_role == UserRoles.CASHIER:
            if request.method in permissions.SAFE_METHODS:
                return True
            if view.action == 'dispense':
                return True
        
        # Patients can view their own prescriptions
        if hasattr(request.user, 'patient_profile'):
            if request.method in permissions.SAFE_METHODS:
                return obj.patient.user == request.user
        
        return False


class MedicationPermissions(permissions.BasePermission):
    """Permissions for Medication operations"""
    
    def has_permission(self, request, view):
        user_role = request.user.role
        
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Only medical staff and managers can modify medications
        return user_role in [
            UserRoles.DOCTOR,
            UserRoles.LAB_TECHNICIAN,
            UserRoles.INVENTORY_MANAGER,
            UserRoles.CLINIC_MANAGER,
            UserRoles.SUPER_ADMIN
        ]
    
    def has_object_permission(self, request, view, obj):
        user_role = request.user.role
        
        if user_role in [UserRoles.SUPER_ADMIN, UserRoles.CLINIC_MANAGER]:
            return True
        
        # Inventory manager can manage all medications
        if user_role == UserRoles.INVENTORY_MANAGER:
            return True
        
        # Medical staff can view all medications
        if user_role in [UserRoles.DOCTOR, UserRoles.LAB_TECHNICIAN]:
            return request.method in permissions.SAFE_METHODS
        
        return False


class PrescriptionTemplatePermissions(permissions.BasePermission):
    """Permissions for PrescriptionTemplate operations"""
    
    def has_permission(self, request, view):
        user_role = request.user.role
        
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Only doctors and managers can modify templates
        return user_role in [
            UserRoles.DOCTOR,
            UserRoles.CLINIC_MANAGER,
            UserRoles.SUPER_ADMIN
        ]
    
    def has_object_permission(self, request, view, obj):
        user_role = request.user.role
        
        if user_role in [UserRoles.SUPER_ADMIN, UserRoles.CLINIC_MANAGER]:
            return True
        
        # Doctors can modify their own templates
        if user_role == UserRoles.DOCTOR:
            return request.user in obj.created_by
        
        return False


class CanDispensePrescription(permissions.BasePermission):
    """Check if user can dispense prescriptions"""
    
    def has_permission(self, request, view):
        return request.user.role in [
            UserRoles.CASHIER,
            UserRoles.DOCTOR,
            UserRoles.CLINIC_MANAGER,
            UserRoles.SUPER_ADMIN
        ]
    
    def has_object_permission(self, request, view, obj):
        # Check if prescription can be dispensed
        if not obj.can_be_dispensed:
            return False
        
        # Check if user is at the same branch as dispensing pharmacy
        if hasattr(request.user, 'user_branches'):
            user_branches = request.user.user_branches.filter(is_active=True)
            if obj.dispensing_pharmacy:
                return user_branches.filter(branch=obj.dispensing_pharmacy).exists()
        
        return True


class CanUpdateStock(permissions.BasePermission):
    """Check if user can update medication stock"""
    
    def has_permission(self, request, view):
        return request.user.role in [
            UserRoles.INVENTORY_MANAGER,
            UserRoles.CLINIC_MANAGER,
            UserRoles.SUPER_ADMIN
        ]
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)