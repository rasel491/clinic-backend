# apps/audit/views/health.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta

from apps.audit.models import AuditLog
from apps.audit.services import verify_chain
from core.permissions import IsAuditor

class AuditHealthView(APIView):
    permission_classes = [IsAuthenticated, IsAuditor]

    def get(self, request):
        return Response({
            "status": "healthy",
            "total_logs": AuditLog.objects.count(),
            "chain_healthy": not verify_chain(),
            "recent_logs": AuditLog.objects.filter(
                timestamp__gte=timezone.now() - timedelta(hours=1)
            ).count(),
            "timestamp": timezone.now(),
        })
