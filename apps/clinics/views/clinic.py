from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.clinics.models import Branch


class ClinicOverviewView(APIView):
    """
    High-level clinic overview for dashboard.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Branch.objects.filter(
            is_active=True,
            deleted_at__isnull=True,
        )

        total_branches = qs.count()
        eod_locked = qs.filter(is_eod_locked=True).count()

        return Response(
            {
                "clinic_name": "Dental Clinic",
                "date": timezone.now().date(),
                "branches": {
                    "total": total_branches,
                    "active": total_branches,
                    "eod_locked": eod_locked,
                },
            }
        )


class ClinicStatsView(APIView):
    """
    Aggregated statistics across all branches.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        branches = Branch.objects.filter(
            is_active=True,
            deleted_at__isnull=True,
        )

        return Response(
            {
                "branches": branches.count(),
                "eod_locked": branches.filter(is_eod_locked=True).count(),
                "last_updated": timezone.now(),
            }
        )
