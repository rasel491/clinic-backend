from datetime import datetime, timedelta
from django.utils import timezone

from apps.clinics.models.availability import DoctorAvailability
from apps.visits.models import Appointment


def generate_time_slots(start_time, end_time, duration_minutes):
    """Generate time slots between start and end"""
    slots = []

    start = datetime.combine(timezone.now().date(), start_time)
    end = datetime.combine(timezone.now().date(), end_time)

    while start + timedelta(minutes=duration_minutes) <= end:
        slots.append(start.time())
        start += timedelta(minutes=duration_minutes)

    return slots


def get_doctor_daily_availability(branch, date, doctor_id=None):
    """
    Returns available slots per doctor for a branch on a date
    """

    weekday = date.strftime("%a").lower()[:3]  # mon, tue, wed

    availabilities = DoctorAvailability.objects.filter(
        branch=branch,
        day_of_week=weekday,
        is_active=True,
        deleted_at__isnull=True,
    ).select_related("doctor")

    if doctor_id:
        availabilities = availabilities.filter(doctor_id=doctor_id)

    results = []

    for availability in availabilities:
        slots = generate_time_slots(
            availability.start_time,
            availability.end_time,
            availability.slot_duration_minutes,
        )

        booked_slots = Appointment.objects.filter(
            branch=branch,
            doctor=availability.doctor,
            appointment_date=date,
            status__in=["SCHEDULED", "CONFIRMED"],
        ).values_list("start_time", flat=True)

        free_slots = [s for s in slots if s not in booked_slots]

        results.append({
            "doctor_id": availability.doctor.id,
            "doctor_name": availability.doctor.full_name,
            "total_slots": len(slots),
            "available_slots": len(free_slots),
            "slots": free_slots,
        })

    return results
