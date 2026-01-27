from rest_framework import serializers
from apps.clinics.models import DoctorAvailability


    # =========================
    #✅ Availability
    # =========================

class AvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorAvailability
        fields = [
            "id",
            "branch",
            "day_of_week",
            "is_open",
            "opening_time",
            "closing_time",
            "break_start",
            "break_end",
        ]

