# apps/audit/views/admin.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction

from apps.audit.models import AuditLog
from apps.audit.serializers import (
    AuditLogSerializer,
    BulkAuditResponseSerializer,
)
from core.permissions import IsAdminUser


class ManualAuditLogView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        log = AuditLog.objects.create(
            user=request.user,
            action=request.data["action"],
            model_name=request.data["model_name"],
            object_id=str(request.data["object_id"]),
            before=request.data.get("before"),
            after=request.data.get("after"),
        )

        return Response(AuditLogSerializer(log).data, status=201)
