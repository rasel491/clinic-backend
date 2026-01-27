from rest_framework import serializers


class AuditWebhookSerializer(serializers.Serializer):
    event_type = serializers.CharField()
    log_id = serializers.CharField()
    timestamp = serializers.DateTimeField()
    data = serializers.JSONField()
    signature = serializers.CharField(required=False)
