# core/permissions.py

from rest_framework.permissions import BasePermission
from rest_framework import permissions
from .constants import UserRoles

class IsAuthenticatedAndActive(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
        )




class IsPatient(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRoles.PATIENT

class IsFrontDesk(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRoles.FRONT_DESK

class IsDoctor(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRoles.DOCTOR

class IsCashier(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRoles.CASHIER

class IsManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRoles.MANAGER

class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == UserRoles.ADMIN

class IsStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in [
            UserRoles.FRONT_DESK,
            UserRoles.DOCTOR, 
            UserRoles.CASHIER,
            UserRoles.MANAGER,
            UserRoles.ADMIN
        ]

class CanOverride(permissions.BasePermission):
    """For actions requiring manager override (refunds, waivers)"""
    def has_permission(self, request, view):
        if request.user.role not in [UserRoles.MANAGER, UserRoles.ADMIN]:
            return False
        # Check if override reason is provided
        override_reason = request.data.get('override_reason') or request.query_params.get('override_reason')
        return bool(override_reason)