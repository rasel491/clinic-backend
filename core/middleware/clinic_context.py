from django.utils.deprecation import MiddlewareMixin
from django.core.exceptions import PermissionDenied
from core.constants import UserRoles


class ClinicContextMiddleware(MiddlewareMixin):
    """
    Injects request.clinic and enforces clinic presence.
    """

    def process_request(self, request):
        user = request.user

        request.clinic = None

        if not user.is_authenticated:
            return

        # Super admin can see all clinics
        if user.role == UserRoles.SUPER_ADMIN:
            return

        # Non-super-admin must have a clinic
        if not user.clinic_id:
            raise PermissionDenied("User is not assigned to any clinic.")

        request.clinic = user.clinic
