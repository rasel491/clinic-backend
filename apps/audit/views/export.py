# apps/audit/views/export.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse

from apps.audit.serializers import AuditExportSerializer
from apps.audit.services import export_audit_logs
from core.permissions import IsAdminUser


class AuditExportView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        serializer = AuditExportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        content = export_audit_logs(**serializer.validated_data)

        response = HttpResponse(content, content_type="application/octet-stream")
        response["Content-Disposition"] = "attachment; filename=audit_export"
        return response
