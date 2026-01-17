from core.constants import UserRoles


class ClinicQuerySetMixin:
    """
    Enforces clinic-based queryset filtering.
    """

    clinic_field = "clinic"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.role == UserRoles.SUPER_ADMIN:
            return qs

        return qs.filter(**{self.clinic_field: self.request.clinic})
