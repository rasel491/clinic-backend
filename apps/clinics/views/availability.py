from datetime import datetime, timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from apps.clinics.models import Branch
from apps.clinics.models.availability import DoctorAvailability
from apps.visits.models import Appointment


    # =========================
    #✅ BranchAvailabilityView
    # =========================
from apps.clinics.models import Counter

def get_active_chairs(branch):
    """
    Chairs = active counters in branch.
    """
    return Counter.objects.filter(
        branch=branch,
        is_active=True,
        deleted_at__isnull=True,
    ).count()
from django.core.cache import cache

def availability_cache_key(branch_id, date, mode, doctor_id=None):
    return f"availability:{branch_id}:{date}:{mode}:{doctor_id or 'all'}"


def doctor_is_on_leave(doctor, date):
    """
    Safely check doctor leave without breaking if model missing.
    """
    try:
        from apps.accounts.models import DoctorLeave
        return DoctorLeave.objects.filter(
            doctor=doctor,
            start_date__lte=date,
            end_date__gte=date,
            is_active=True,
        ).exists()
    except Exception:
        return False

def calculate_branch_daily_capacity(branch: Branch) -> int:
    """
    Calculate max appointment slots per day for a branch.
    Default slot size: 30 minutes.
    """
    opening = datetime.combine(timezone.now().date(), branch.opening_time)
    closing = datetime.combine(timezone.now().date(), branch.closing_time)

    if closing <= opening:
        return 0

    total_minutes = int((closing - opening).total_seconds() / 60)
    slot_duration = 30  # future: configurable per branch

    return total_minutes // slot_duration


def calculate_doctor_slots(availability, date):
    """
    Calculate all slots for a doctor on a specific date.
    """
    start = datetime.combine(date, availability.start_time)
    end = datetime.combine(date, availability.end_time)

    slots = []
    duration = availability.slot_duration_minutes

    while start + timedelta(minutes=duration) <= end:
        slots.append(start.time())
        start += timedelta(minutes=duration)

    return slots


    # =========================
    #✅ BranchAvailabilityView
    # =========================
class BranchAvailabilityView(APIView):
    """
    Public availability endpoint.
    Supports:
    - Branch capacity
    - Chair (counter) capacity
    - Doctor slots
    - Cache
    - EOD lock
    """
    permission_classes = [AllowAny]

    def get(self, request, branch_id):
        # ----------------------------
        # Params
        # ----------------------------
        date_str = request.query_params.get("date")
        mode = request.query_params.get("mode", "branch")  # branch | doctor
        doctor_id = request.query_params.get("doctor_id")

        try:
            date = (
                datetime.strptime(date_str, "%Y-%m-%d").date()
                if date_str else timezone.now().date()
            )
        except ValueError:
            return Response(
                {"detail": "Invalid date format (YYYY-MM-DD)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ----------------------------
        # Branch
        # ----------------------------
        branch = get_object_or_404(
            Branch,
            id=branch_id,
            is_active=True,
            deleted_at__isnull=True,
        )

        # ----------------------------
        # 🚫 EOD LOCK CHECK
        # ----------------------------
        if branch.is_eod_locked:
            return Response({
                "branch": branch.name,
                "date": date,
                "is_eod_locked": True,
                "available_slots": 0,
                "detail": "Branch is locked for end-of-day.",
            })

        # ----------------------------
        # Cache
        # ----------------------------
        cache_key = availability_cache_key(
            branch.id, date, mode, doctor_id
        )
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        # ============================
        # MODE 1️⃣ Branch / Chair level
        # ============================
        if mode == "branch":
            base_capacity = calculate_branch_daily_capacity(branch)

            chairs = get_active_chairs(branch)
            total_capacity = base_capacity * max(1, chairs)

            booked = Appointment.objects.filter(
                branch=branch,
                appointment_date=date,
                status__in=["scheduled", "confirmed"],
            ).count()

            available = max(0, total_capacity - booked)

            response = {
                "mode": "branch",
                "branch": {
                    "id": branch.id,
                    "name": branch.name,
                    "code": branch.code,
                },
                "date": date,
                "chairs": chairs,
                "capacity": total_capacity,
                "booked": booked,
                "available_slots": available,
                "is_fully_booked": available == 0,
            }

            cache.set(cache_key, response, 300)  # 5 min
            return Response(response)

        # ============================
        # MODE 2️⃣ Doctor availability
        # ============================
        weekday = date.strftime("%a").lower()[:3]

        availabilities = DoctorAvailability.objects.filter(
            branch=branch,
            day_of_week=weekday,
            is_active=True,
            deleted_at__isnull=True,
        )

        if doctor_id:
            availabilities = availabilities.filter(doctor_id=doctor_id)

        doctors = []

        for availability in availabilities:
            doctor = availability.doctor

            # 🚫 Leave check
            if doctor_is_on_leave(doctor, date):
                continue

            slots = calculate_doctor_slots(availability, date)

            booked_slots = Appointment.objects.filter(
                branch=branch,
                doctor=doctor,
                appointment_date=date,
                status__in=["scheduled", "confirmed"],
            ).values_list("appointment_time", flat=True)

            free_slots = [s for s in slots if s not in booked_slots]

            doctors.append({
                "doctor_id": doctor.id,
                "doctor_name": doctor.full_name,
                "total_slots": len(slots),
                "available_slots": len(free_slots),
                "slots": free_slots,
            })

        response = {
            "mode": "doctor",
            "branch": {
                "id": branch.id,
                "name": branch.name,
            },
            "date": date,
            "doctors": doctors,
        }

        cache.set(cache_key, response, 300)
        return Response(response)
