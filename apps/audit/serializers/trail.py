from rest_framework import serializers
from .base import AuditLogSerializer


class AuditTrailSerializer(serializers.Serializer):
    object_id = serializers.CharField()
    model_name = serializers.CharField()
    total_logs = serializers.IntegerField()
    first_log = serializers.DateTimeField()
    last_log = serializers.DateTimeField()
    logs = AuditLogSerializer(many=True)
