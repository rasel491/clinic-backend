from rest_framework import serializers
from .base import AuditLogSerializer


class AuditLogDiffSerializer(serializers.Serializer):
    log1 = AuditLogSerializer()
    log2 = AuditLogSerializer()
    differences = serializers.DictField()
