from core.exceptions import EODLockedError
from apps.billing.models import EndOfDay


def is_eod_closed(branch, date):
    return EndOfDay.objects.filter(
        branch=branch,
        date=date
    ).exists()


def enforce_eod(branch, date):
    if is_eod_closed(branch, date):
        raise EODLockedError("Financial day is locked by EOD")
