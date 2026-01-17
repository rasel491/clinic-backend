# apps/accounts/permissions.py

from rest_framework.permissions import BasePermission
from rest_framework.permissions import AND, OR
from core.permissions import IsAuthenticatedAndActive
from apps.accounts.permissions import IsCashier, IsManager


class HasRole(BasePermission):
    required_roles = []

    def has_permission(self, request, view):
        role = getattr(request, "role", None)
        return role in self.required_roles

class IsAdmin(HasRole):
    required_roles = ["ADMIN"]


class IsManager(HasRole):
    required_roles = ["MANAGER", "ADMIN"]


class IsDoctor(HasRole):
    required_roles = ["DOCTOR"]


class IsFrontDesk(HasRole):
    required_roles = ["FRONT_DESK"]


class IsCashier(HasRole):
    required_roles = ["CASHIER"]


class IsPatient(HasRole):
    required_roles = ["PATIENT"]



permission_classes = [
    AND(
        IsAuthenticatedAndActive,
        OR(IsCashier, IsManager)
    )
]

