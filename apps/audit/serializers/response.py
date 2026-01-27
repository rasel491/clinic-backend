from rest_framework import serializers


class AuditLogResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    log_id = serializers.IntegerField(required=False)
    data = serializers.JSONField(required=False)
    timestamp = serializers.DateTimeField()


class BulkAuditResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    message = serializers.CharField()
    total_processed = serializers.IntegerField()
    successful = serializers.IntegerField()
    failed = serializers.IntegerField()
    failed_details = serializers.ListField(required=False)
    timestamp = serializers.DateTimeField()
