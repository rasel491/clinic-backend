# clinic/Backend/core/middleware/audit_middleware.py

from django.utils import timezone


class AuditContextMiddleware:
    """
    Injects audit context into request and model instances.
    DOES NOT write to database.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Attach request-level audit context
        request._audit_user = getattr(request, "user", None)
        request._audit_device = request.META.get("HTTP_X_DEVICE_ID")
        request._audit_ip = self._get_client_ip(request)
        request._audit_start_time = timezone.now()

        response = self.get_response(request)

        # Attach duration (optional)
        request._audit_duration = timezone.now() - request._audit_start_time

        return response

    @staticmethod
    def _get_client_ip(request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
