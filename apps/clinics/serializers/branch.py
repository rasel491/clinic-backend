from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
import logging

from apps.clinics.models import Branch
from apps.accounts.serializers import UserSerializer

logger = logging.getLogger(__name__)


    # =========================
    #✅ BranchSerializer (main)
    # =========================

class BranchSerializer(serializers.ModelSerializer):
    is_eod_locked_display = serializers.SerializerMethodField()
    eod_locked_by_details = UserSerializer(source="eod_locked_by", read_only=True)

    active_counters = serializers.SerializerMethodField()
    total_staff = serializers.SerializerMethodField()
    todays_appointments = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = [
            "id",
            "name",
            "code",
            "address",
            "phone",
            "email",
            "opening_time",
            "closing_time",
            "is_active",
            "is_eod_locked",
            "is_eod_locked_display",
            "eod_locked_at",
            "eod_locked_by",
            "eod_locked_by_details",
            "active_counters",
            "total_staff",
            "todays_appointments",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "is_eod_locked",
            "eod_locked_at",
            "eod_locked_by",
        ]

    def get_is_eod_locked_display(self, obj):
        if obj.is_eod_locked and obj.eod_locked_at:
            return f"Locked at {obj.eod_locked_at:%Y-%m-%d %H:%M}"
        return "Open"

    def get_active_counters(self, obj):
        return obj.counters.filter(is_active=True).count()

    def get_total_staff(self, obj):
        return getattr(obj, "user_branches", []).filter(is_active=True).count()

    def get_todays_appointments(self, obj):
        from apps.visits.models import Appointment
        today = timezone.now().date()
        return Appointment.objects.filter(
            branch=obj,
            appointment_date=today,
            status__in=["scheduled", "confirmed"],
        ).count()

    def validate(self, data):
        if (
            data.get("opening_time")
            and data.get("closing_time")
            and data["opening_time"] >= data["closing_time"]
        ):
            raise serializers.ValidationError(
                "Opening time must be before closing time"
            )
        return data


    # =========================
    #✅ BranchCreate / Update / List
    # =========================

class BranchCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = [
            "name",
            "code",
            "address",
            "phone",
            "email",
            "opening_time",
            "closing_time",
            "is_active",
        ]

    def validate_code(self, value):
        if Branch.objects.filter(code=value, deleted_at__isnull=True).exists():
            raise serializers.ValidationError("Branch code already exists")
        return value.upper()

class BranchUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = [
            "name",
            "address",
            "phone",
            "email",
            "opening_time",
            "closing_time",
            "is_active",
        ]

    def validate(self, data):
        if self.instance.is_eod_locked:
            for field in ["opening_time", "closing_time", "is_active"]:
                if field in data:
                    raise serializers.ValidationError(
                        f"Cannot modify {field} after EOD lock"
                    )
        return data


class BranchListSerializer(serializers.ModelSerializer):
    active_counters = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = [
            "id",
            "name",
            "code",
            "phone",
            "is_active",
            "is_eod_locked",
            "active_counters",
        ]

    def get_active_counters(self, obj):
        return obj.counters.filter(is_active=True).count()


    # =========================
    # 📊 Utility / Operational serializers
    # =========================

class BranchEODSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["lock", "unlock"])
    reason = serializers.CharField(required=False, allow_blank=True)

class BranchStatsSerializer(serializers.Serializer):
    branch_id = serializers.UUIDField()
    branch_name = serializers.CharField()
    branch_code = serializers.CharField()

    total_patients = serializers.IntegerField()
    total_appointments_today = serializers.IntegerField()
    total_appointments_week = serializers.IntegerField()
    active_staff = serializers.IntegerField()
    active_counters = serializers.IntegerField()

    todays_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    weeks_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    pending_payments = serializers.DecimalField(max_digits=12, decimal_places=2)

    eod_locked = serializers.BooleanField()
    eod_locked_at = serializers.DateTimeField(allow_null=True)
