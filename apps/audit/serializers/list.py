from rest_framework import serializers
from apps.audit.models import AuditLog


class AuditLogListSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "timestamp",
            "action",
            "model_name",
            "object_id",
            "user_email",
            "branch_name",
            "ip_address",
            "device_id",
        ]
        read_only_fields = fields
