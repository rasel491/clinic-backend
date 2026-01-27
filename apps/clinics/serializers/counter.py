from rest_framework import serializers
from apps.clinics.models import Counter



    # =========================
    #✅ Counter
    # =========================

class CounterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Counter
        fields = [
            "id",
            "branch",
            "counter_number",
            "name",
            "device_id",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

class CounterCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Counter
        fields = [
            "branch",
            "counter_number",
            "name",
            "device_id",
            "is_active",
        ]

class CounterListSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Counter
        fields = [
            "id",
            "counter_number",
            "name",
            "device_id",
            "is_active",
            "branch_name",
        ]

class CounterAssignmentSerializer(serializers.Serializer):
    device_id = serializers.CharField()
    force = serializers.BooleanField(default=False)

class CounterStatsSerializer(serializers.Serializer):
    counter_id = serializers.UUIDField()
    counter_name = serializers.CharField()
    branch_name = serializers.CharField()

    todays_transactions = serializers.IntegerField()
    weeks_transactions = serializers.IntegerField()
    total_transactions = serializers.IntegerField()

    current_user = serializers.CharField(allow_null=True)
    last_user = serializers.CharField(allow_null=True)
    last_used_at = serializers.DateTimeField(allow_null=True)
