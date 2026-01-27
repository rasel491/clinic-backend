# apps/audit/views/trail.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditTrailSerializer
from core.permissions import IsAuditor

class ObjectAuditTrailView(APIView):
    permission_classes = [IsAuthenticated, IsAuditor]

    def get(self, request, model_name, object_id):
        qs = AuditLog.objects.filter(
            model_name=model_name,
            object_id=str(object_id),
        ).order_by("-timestamp")

        if not qs.exists():
            return Response({"detail": "No audit trail found"}, status=404)

        data = {
            "object_id": object_id,
            "model_name": model_name,
            "total_logs": qs.count(),
            "first_log": qs.last().timestamp,
            "last_log": qs.first().timestamp,
            "logs": qs,
        }

        return Response(AuditTrailSerializer(data).data)
