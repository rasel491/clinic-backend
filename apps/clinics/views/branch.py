from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone

from apps.clinics.models import Branch

from apps.clinics.serializers import (
    BranchSerializer,
    BranchCreateSerializer,
    BranchListSerializer,
    BranchUpdateSerializer,
    BranchStatsSerializer,
    BranchEODSerializer,
)
from core.permissions import IsAdmin


from apps.accounts.permissions import IsAdmin, IsManager
from apps.audit.utils import build_audit_context
from apps.audit.services import log_action

import logging
logger = logging.getLogger(__name__)


  # =========================
    #✅ BranchView
    # =========================

# class BranchViewSet(viewsets.ModelViewSet):
#     queryset = Branch.objects.filter(deleted_at__isnull=True)
#     permission_classes = [IsAuthenticated, IsManager]

#     def get_serializer_class(self):
#         if self.action == "list":
#             return BranchListSerializer
#         return BranchSerializer

#     def perform_create(self, serializer):
#         with transaction.atomic():
#             attach_audit_context(serializer, self.request)
#             branch = serializer.save()

#             log_action(
#                 instance=branch,
#                 action="CREATE",
#                 user=self.request.user,
#                 branch=branch,
#             )

#     def perform_update(self, serializer):
#         branch = self.get_object()
#         if branch.is_eod_locked:
#             raise ValueError("Branch is EOD locked")

#         with transaction.atomic():
#             attach_audit_context(serializer, self.request)
#             branch = serializer.save()

#             log_action(
#                 instance=branch,
#                 action="UPDATE",
#                 user=self.request.user,
#                 branch=branch,
#             )

#     @action(detail=True, methods=["post"])
#     def lock_eod(self, request, pk=None):
#         branch = self.get_object()
#         branch.is_eod_locked = True
#         branch.eod_locked_at = timezone.now()
#         branch.save(update_fields=["is_eod_locked", "eod_locked_at"])

#         log_action(
#             instance=branch,
#             action="EOD_LOCK",
#             user=request.user,
#             branch=branch,
#         )

#         return Response({"status": "EOD locked"})


class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.filter(deleted_at__isnull=True)
    permission_classes = [IsAdmin]

    def get_serializer_class(self):
        if self.action == "create":
            return BranchCreateSerializer
        if self.action in ["update", "partial_update"]:
            return BranchUpdateSerializer
        return BranchSerializer


    @action(detail=True, methods=["post"])
    def eod_lock(self, request, pk=None):
        branch = self.get_object()
        serializer = BranchEODSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            branch.lock_eod(user=request.user)

        return Response({"status": "EOD locked"})


    @action(detail=True, methods=["post"])
    def eod_unlock(self, request, pk=None):
        branch = self.get_object()
        if not request.user.is_superuser:
            return Response(
                {"detail": "Only superuser can unlock EOD"},
                status=status.HTTP_403_FORBIDDEN,
            )

        branch.is_eod_locked = False
        branch.eod_locked_at = None
        branch.eod_locked_by = None
        branch.save()

        return Response({"status": "EOD unlocked"})


    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        branch = self.get_object()

        data = {
            "branch_id": branch.id,
            "branch_name": branch.name,
            "branch_code": branch.code,
            "total_patients": 0,
            "total_appointments_today": 0,
            "total_appointments_week": 0,
            "active_staff": 0,
            "active_counters": branch.counters.filter(is_active=True).count(),
            "todays_revenue": 0,
            "weeks_revenue": 0,
            "pending_payments": 0,
            "eod_locked": branch.is_eod_locked,
            "eod_locked_at": branch.eod_locked_at,
        }

        serializer = BranchStatsSerializer(data)
        return Response(serializer.data)


    @action(detail=True, methods=["get", "put"])
    def operational_hours(self, request, pk=None):
        branch = self.get_object()

        if request.method == "GET":
            return Response({
                "opening_time": branch.opening_time,
                "closing_time": branch.closing_time,
            })

        branch.opening_time = request.data.get("opening_time")
        branch.closing_time = request.data.get("closing_time")
        branch.save(update_fields=["opening_time", "closing_time"])

        return Response({"status": "Operational hours updated"})


    @action(detail=True, methods=["get", "put"])
    def configuration(self, request, pk=None):
        branch = self.get_object()

        if request.method == "GET":
            return Response({"is_active": branch.is_active})

        branch.is_active = request.data.get("is_active", branch.is_active)
        branch.save(update_fields=["is_active"])
        return Response({"status": "Configuration updated"})


