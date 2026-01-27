from django.core.exceptions import ValidationError

class EODImmutableMixin:
    """
    Enforces EOD & financial immutability at model level
    """

    def _assert_not_locked(self):
        branch = getattr(self, "branch", None)

        if branch and branch.is_eod_locked:
            raise ValidationError("EOD locked: no financial modification allowed")

        if getattr(self, "is_locked", False):
            raise ValidationError("Record is locked")

        if getattr(self, "is_final", False):
            raise ValidationError("Finalized record cannot be modified")

        status = getattr(self, "status", None)
        if status in {"PAID", "VOID", "CANCELLED"}:
            raise ValidationError(f"Cannot modify invoice in {status} state")
