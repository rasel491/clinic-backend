from rest_framework import serializers


class AuditStatsSerializer(serializers.Serializer):
    period_start = serializers.DateTimeField()
    period_end = serializers.DateTimeField()

    total_logs = serializers.IntegerField()
    logs_today = serializers.IntegerField()
    logs_this_week = serializers.IntegerField()
    logs_this_month = serializers.IntegerField()

    by_action = serializers.DictField()
    by_model = serializers.DictField()
    by_user = serializers.ListField()
    by_hour = serializers.DictField()

    chain_verified = serializers.BooleanField()
    broken_links_count = serializers.IntegerField()

    avg_duration_seconds = serializers.FloatField()
    max_duration_seconds = serializers.FloatField()
    min_duration_seconds = serializers.FloatField()


class AuditSummarySerializer(serializers.Serializer):
    today_total = serializers.IntegerField()
    today_by_action = serializers.DictField()
    today_top_models = serializers.ListField()
    today_top_users = serializers.ListField()

    week_activity = serializers.ListField()

    chain_healthy = serializers.BooleanField()
    storage_used_mb = serializers.FloatField()
    avg_logs_per_day = serializers.FloatField()

    suspicious_activity_count = serializers.IntegerField()
    failed_logins_today = serializers.IntegerField()

    recent_critical = serializers.ListField()
