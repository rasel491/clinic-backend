# apps/audit/views/stats.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Count, Avg, Max, Min
from datetime import timedelta

from apps.audit.models import AuditLog
from apps.audit.serializers import (
    AuditStatsSerializer,
    AuditSummarySerializer,
    AuditLogListSerializer,
)
from apps.audit.services import verify_chain
from core.permissions import IsAuditor


class AuditStatsView(APIView):
    permission_classes = [IsAuthenticated, IsAuditor]

    def get(self, request):
        days = int(request.query_params.get("days", 30))
        end = timezone.now()
        start = end - timedelta(days=days)

        qs = AuditLog.objects.filter(timestamp__range=(start, end))

        stats = {
            "period_start": start,
            "period_end": end,
            "total_logs": qs.count(),
            "logs_today": qs.filter(timestamp__date=end.date()).count(),
            "logs_this_week": qs.filter(timestamp__gte=end - timedelta(days=7)).count(),
            "logs_this_month": qs.filter(timestamp__gte=end - timedelta(days=30)).count(),
            "by_action": dict(qs.values_list("action").annotate(Count("id"))),
            "by_model": dict(qs.values_list("model_name").annotate(Count("id"))),
            "by_user": list(
                qs.values("user__email")
                .annotate(count=Count("id"))
                .order_by("-count")[:10]
            ),
            "by_hour": {
                str(h): qs.filter(timestamp__hour=h).count()
                for h in range(24)
            },
            "chain_verified": not verify_chain(),
            "broken_links_count": len(verify_chain()),
        }

        durations = qs.aggregate(
            avg=Avg("duration"), max=Max("duration"), min=Min("duration")
        )

        stats.update({
            "avg_duration_seconds": durations["avg"].total_seconds() if durations["avg"] else 0,
            "max_duration_seconds": durations["max"].total_seconds() if durations["max"] else 0,
            "min_duration_seconds": durations["min"].total_seconds() if durations["min"] else 0,
        })

        return Response(AuditStatsSerializer(stats).data)
