from rest_framework import serializers


class AuditExportSerializer(serializers.Serializer):
    start_date = serializers.DateTimeField()
    end_date = serializers.DateTimeField()

    format = serializers.ChoiceField(choices=["json", "csv", "excel"])
    include_sensitive = serializers.BooleanField(default=False)
    compress = serializers.BooleanField(default=False)


class ChainVerificationSerializer(serializers.Serializer):
    verified = serializers.BooleanField()
    total_records = serializers.IntegerField()
    broken_links = serializers.ListField()
    first_record_hash = serializers.CharField(allow_null=True)
    last_record_hash = serializers.CharField(allow_null=True)
    verification_timestamp = serializers.DateTimeField()
