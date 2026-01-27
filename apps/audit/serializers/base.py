from rest_framework import serializers
from apps.audit.models import AuditLog
from apps.accounts.serializers import UserSerializer
from apps.clinics.serializers import BranchSerializer
from apps.audit.utils import redact_sensitive_fields
from apps.audit.services import validate_record_hash


class AuditLogSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source="user", read_only=True)
    branch_details = BranchSerializer(source="branch", read_only=True)

    duration_seconds = serializers.SerializerMethodField()
    hash_valid = serializers.SerializerMethodField()

    before_safe = serializers.SerializerMethodField()
    after_safe = serializers.SerializerMethodField()

    record_hash_short = serializers.SerializerMethodField()
    previous_hash_short = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "timestamp",
            "action",
            "model_name",
            "object_id",
            "user",
            "branch",
            "device_id",
            "ip_address",
            "before",
            "after",
            "previous_hash",
            "record_hash",
            "duration",
        ]
        read_only_fields = fields

    def get_duration_seconds(self, obj):
        return obj.duration.total_seconds() if obj.duration else None

    def get_hash_valid(self, obj):
        return validate_record_hash(obj)

    def get_before_safe(self, obj):
        return redact_sensitive_fields(obj.before)

    def get_after_safe(self, obj):
        return redact_sensitive_fields(obj.after)

    def get_record_hash_short(self, obj):
        return obj.record_hash[:8] + "…" if obj.record_hash else None

    def get_previous_hash_short(self, obj):
        return obj.previous_hash[:8] + "…" if obj.previous_hash else "GENESIS"
