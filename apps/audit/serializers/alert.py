from rest_framework import serializers


class AuditAlertSerializer(serializers.Serializer):
    alert_type = serializers.CharField()
    severity = serializers.ChoiceField(
        choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    )
    message = serializers.CharField()
    details = serializers.JSONField()
    timestamp = serializers.DateTimeField()
    resolved = serializers.BooleanField(default=False)
