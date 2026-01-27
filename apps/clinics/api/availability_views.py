from datetime import datetime
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from apps.clinics.models import Branch
from apps.clinics.services.availability_service import (
    get_doctor_daily_availability,
)


class BranchAvailabilityView(APIView):
    """
    Public API:
    - Branch availability
    - Doctor-wise slots
    """

    permission_classes = [AllowAny]

    def get(self, request, branch_id):
        date_str = request.query_params.get("date")
        doctor_id = request.query_params.get("doctor_id")

        try:
            date = (
                datetime.strptime(date_str, "%Y-%m-%d").date()
                if date_str
                else timezone.now().date()
            )
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Use YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        branch = get_object_or_404(
            Branch,
            id=branch_id,
            is_active=True,
            deleted_at__isnull=True,
        )

        doctors_data = get_doctor_daily_availability(
            branch=branch,
            date=date,
            doctor_id=doctor_id,
        )

        return Response({
            "branch": {
                "id": branch.id,
                "name": branch.name,
                "code": branch.code,
            },
            "date": date,
            "doctors": doctors_data,
            "is_fully_booked": all(
                d["available_slots"] == 0 for d in doctors_data
            ) if doctors_data else True,
        })
