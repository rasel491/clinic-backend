# apps/audit/views/base.py

from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from apps.audit.models import AuditLog
from apps.audit.serializers import (
    AuditLogListSerializer,
    AuditLogDetailSerializer,
)
from apps.audit.filters import AuditLogFilter
from core.permissions import IsAuditor


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Immutable audit log access.
    """

    queryset = AuditLog.objects.select_related(
        "user", "branch"
    ).all()

    permission_classes = [IsAuthenticated, IsAuditor]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = AuditLogFilter
    search_fields = ["action", "model_name", "object_id", "ip_address"]
    ordering_fields = ["timestamp", "action", "model_name"]
    ordering = ["-timestamp"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.is_superuser or user.is_admin():
            return qs

        if user.is_manager():
            branch_ids = user.user_branches.filter(
                is_active=True
            ).values_list("branch_id", flat=True)
            return qs.filter(branch_id__in=branch_ids)

        return qs.filter(user=user)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AuditLogDetailSerializer
        return AuditLogListSerializer
