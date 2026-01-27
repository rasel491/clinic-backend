# # Backend/apps/audit/permissions.py

# """
# Custom permissions for audit app.
# """
# from rest_framework.permissions import BasePermission, SAFE_METHODS
# from django.core.cache import cache
# from django.utils.timezone import now


# class IsAuditor(BasePermission):
#     """
#     Allows access only to users with auditor role.
#     """
#     def has_permission(self, request, view):
#         user = request.user
#         if not user or not user.is_authenticated:
#             return False

#         return (
#             user.is_superuser or
#             getattr(user, "is_admin", lambda: False)() or
#             getattr(user, "is_manager", lambda: False)() or
#             getattr(user, "has_role", lambda r: False)("AUDITOR") or
#             user.groups.filter(name="Auditors").exists()
#         )



# class CanExportAuditLogs(BasePermission):
#     """
#     Allows export only to authorized users.
#     """
#     def has_permission(self, request, view):
#         user = request.user
#         if not user or not user.is_authenticated:
#             return False

#         return (
#             user.is_superuser or
#             getattr(user, "is_admin", lambda: False)() or
#             user.has_perm("audit.export_auditlog")
#         )



# class CanVerifyAuditChain(BasePermission):
#     """
#     Allows chain verification only to authorized users.
#     """
#     def has_permission(self, request, view):
#         user = request.user
#         if not user or not user.is_authenticated:
#             return False

#         return (
#             user.is_superuser or
#             getattr(user, "is_admin", lambda: False)() or
#             user.has_perm("audit.verify_auditchain")
#         )



# class CanViewSensitiveAuditData(BasePermission):
#     """
#     Allows viewing of sensitive audit data.
#     """
#     def has_permission(self, request, view):
#         include_sensitive = (
#             request.data.get("include_sensitive", False)
#             if hasattr(request, "data")
#             else request.query_params.get("include_sensitive", False)
#         )

#         if not include_sensitive:
#             return True

#         user = request.user
#         return bool(
#             user and user.is_authenticated and
#             (user.is_superuser or getattr(user, "is_admin", lambda: False)())
#         )



# class WebhookPermission(BasePermission):
#     """
#     Permission for webhook endpoints.
#     Uses signature verification instead of authentication.
#     """
#     def has_permission(self, request, view):
#         # Check signature in header
#         signature = request.META.get('HTTP_X_SIGNATURE')
        
#         if not signature:
#             return False
        
#         # Verify signature (implement your verification logic)
#         try:
#             from .services import verify_webhook_signature
#             return verify_webhook_signature(request)
#         except Exception:
#             return False



# class AuditRateLimitPermission(BasePermission):
#     RATE_LIMITS = {
#         "AuditWebhookView": (100, 3600),
#         "AuditExportView": (5, 86400),
#         "AuditVerifyView": (10, 3600),
#     }

#     def has_permission(self, request, view):
#         view_name = view.__class__.__name__
#         if view_name not in self.RATE_LIMITS:
#             return True

#         limit, period = self.RATE_LIMITS[view_name]

#         identifier = (
#             f"user:{request.user.id}"
#             if request.user and request.user.is_authenticated
#             else f"ip:{request.META.get('REMOTE_ADDR')}"
#         )

#         key = f"audit_rl:{view_name}:{identifier}"
#         count = cache.get(key, 0)

#         if count >= limit:
#             return False

#         cache.set(key, count + 1, timeout=period)
#         return True



# Backend/apps/audit/permissions.py

from rest_framework.permissions import BasePermission
from django.core.cache import cache


class IsAuditor(BasePermission):
    """
    Allows access only to audit-capable users.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        return (
            user.is_superuser or
            getattr(user, "is_admin", lambda: False)() or
            getattr(user, "is_manager", lambda: False)() or
            getattr(user, "has_role", lambda r: False)("AUDITOR") or
            user.groups.filter(name="Auditors").exists()
        )


class CanExportAuditLogs(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and (
                user.is_superuser or
                getattr(user, "is_admin", lambda: False)() or
                user.has_perm("audit.export_auditlog")
            )
        )


class CanVerifyAuditChain(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and (
                user.is_superuser or
                getattr(user, "is_admin", lambda: False)() or
                user.has_perm("audit.verify_auditchain")
            )
        )


class CanViewSensitiveAuditData(BasePermission):
    """
    Sensitive audit fields must be explicitly requested.
    """
    def has_permission(self, request, view):
        include_sensitive = (
            request.query_params.get("include_sensitive", "false").lower() == "true"
        )

        if not include_sensitive:
            return True

        user = request.user
        return bool(
            user and user.is_authenticated and
            (user.is_superuser or getattr(user, "is_admin", lambda: False)())
        )


class WebhookPermission(BasePermission):
    def has_permission(self, request, view):
        signature = request.META.get("HTTP_X_SIGNATURE")
        if not signature:
            return False

        try:
            from .services import verify_webhook_signature
            return verify_webhook_signature(request)
        except Exception:
            return False


class AuditRateLimitPermission(BasePermission):
    """
    Generic rate limiter keyed by view + user/ip.
    """
    RATE_LIMITS = {
        "webhook": (100, 3600),
        "export": (5, 86400),
        "verify": (10, 3600),
    }

    def has_permission(self, request, view):
        key_name = getattr(view, "rate_limit_key", None)
        if not key_name or key_name not in self.RATE_LIMITS:
            return True

        limit, period = self.RATE_LIMITS[key_name]

        identifier = (
            f"user:{request.user.id}"
            if request.user and request.user.is_authenticated
            else f"ip:{request.META.get('REMOTE_ADDR')}"
        )

        cache_key = f"audit_rl:{key_name}:{identifier}"
        count = cache.get(cache_key, 0)

        if count >= limit:
            return False

        cache.set(cache_key, count + 1, timeout=period)
        return True
