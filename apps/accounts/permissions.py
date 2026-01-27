# apps/accounts/permissions.py

from rest_framework.permissions import BasePermission, SAFE_METHODS
from apps.accounts.models import RoleCode


# =========================
# Basic / Authenticated Permissions
# =========================

class IsAuthenticatedAndActive(BasePermission):
    """Access only for authenticated and active users."""
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)


class IsSuperAdmin(BasePermission):
    """Access only for superuser / system admin."""
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser)


# =========================
# Role-Based Permissions
# =========================

class HasRole(BasePermission):
    """
    Generic role-based permission.
    Required roles can be passed to the class on initialization.
    """
    required_roles = []

    def has_permission(self, request, view):
        user = request.user
        branch = getattr(request, "branch", None)
        if not user.is_authenticated or not branch:
            return False

        return any(user.has_role(role, branch) for role in self.required_roles)


class IsAdmin(HasRole):
    required_roles = [RoleCode.ADMIN]


class IsManager(HasRole):
    required_roles = [RoleCode.MANAGER, RoleCode.ADMIN]


class IsDoctor(HasRole):
    required_roles = [RoleCode.DOCTOR]


class IsFrontDesk(HasRole):
    required_roles = [RoleCode.FRONT_DESK]


class IsCashier(HasRole):
    required_roles = [RoleCode.CASHIER]


class IsPatient(HasRole):
    required_roles = [RoleCode.PATIENT]


# =========================
# Branch Permissions
# =========================

class HasBranchAccess(BasePermission):
    """
    Ensure user has access to branch resolved by middleware.
    Middleware must set: request.branch
    """
    def has_permission(self, request, view):
        user = request.user
        branch = getattr(request, "branch", None)
        if not user.is_authenticated or not branch:
            return False
        return user.branch_roles.filter(branch=branch, is_active=True).exists() or user.is_superuser


class HasObjectBranchAccess(BasePermission):
    """
    Object-level branch enforcement.
    Object must have `branch` field.
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_superuser:
            return True
        if not hasattr(obj, "branch"):
            return False
        return obj.branch_id in [br.branch_id for br in user.branch_roles.filter(is_active=True)]


# =========================
# Read / Write Permissions
# =========================

class ReadOnly(BasePermission):
    """Allows read-only access."""
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


class ReadOnlyForNonAdmin(BasePermission):
    """Non-admin users cannot write."""
    def has_permission(self, request, view):
        user = request.user
        if request.method in SAFE_METHODS:
            return True
        return user.is_authenticated and user.is_staff


# =========================
# EOD / Financial Protection
# =========================

class EODUnlockedRequired(BasePermission):
    """
    Blocks financial operations if EOD is locked.
    Requires request.branch.is_eod_locked flag.
    """
    message = "End-of-day is locked. Financial operations are disabled."

    def has_permission(self, request, view):
        branch = getattr(request, "branch", None)
        if not branch:
            return False
        if request.method in SAFE_METHODS:
            return True
        return not getattr(branch, "is_eod_locked", False)


# =========================
# Audit Protection
# =========================

class ImmutableAuditProtected(BasePermission):
    """
    Prevents update/delete on audit-logged models.
    """
    message = "Audit records are immutable."

    def has_permission(self, request, view):
        return request.method not in ("PUT", "PATCH", "DELETE")
