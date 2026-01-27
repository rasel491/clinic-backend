from rest_framework import serializers
from apps.clinics.models import Clinic




    # =========================
    #✅ Clinic
    # =========================
class ClinicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        fields = [
            "id",
            "name",
            "code",
            "email",
            "phone",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
