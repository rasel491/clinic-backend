# apps/audit/views/verify.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services import verify_chain
from apps.audit.serializers import ChainVerificationSerializer
from core.permissions import IsAuditor

class AuditChainVerifyView(APIView):
    permission_classes = [IsAuthenticated, IsAuditor]

    def get(self, request):
        broken = verify_chain()

        first = AuditLog.objects.order_by("id").first()
        last = AuditLog.objects.order_by("-id").first()

        data = {
            "verified": not broken,
            "total_records": AuditLog.objects.count(),
            "broken_links": broken,
            "first_record_hash": first.record_hash if first else None,
            "last_record_hash": last.record_hash if last else None,
            "verification_timestamp": timezone.now(),
        }

        return Response(ChainVerificationSerializer(data).data)
