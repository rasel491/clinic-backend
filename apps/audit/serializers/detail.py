from rest_framework import serializers
from apps.audit.models import AuditLog
from .base import AuditLogSerializer
from apps.audit.utils import diff_dicts


class AuditLogDetailSerializer(AuditLogSerializer):
    changes = serializers.SerializerMethodField()
    changed_fields = serializers.SerializerMethodField()

    class Meta(AuditLogSerializer.Meta):
        fields = AuditLogSerializer.Meta.fields + [
            "changes",
            "changed_fields",
        ]

    def get_changes(self, obj):
        if not obj.before or not obj.after:
            return None
        return diff_dicts(obj.before, obj.after)

    def get_changed_fields(self, obj):
        diffs = self.get_changes(obj)
        if not diffs:
            return []
        return list(diffs.keys())
