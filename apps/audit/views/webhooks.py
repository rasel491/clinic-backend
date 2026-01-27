# apps/audit/views/webhooks.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditWebhookSerializer


@api_view(["POST"])
@permission_classes([AllowAny])
def audit_webhook(request):
    serializer = AuditWebhookSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    AuditLog.objects.create(
        action=f"WEBHOOK_{serializer.validated_data['event_type']}",
        model_name="ExternalSystem",
        object_id=str(serializer.validated_data["log_id"]),
        after=serializer.validated_data["data"],
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    return Response({"status": "accepted"})
