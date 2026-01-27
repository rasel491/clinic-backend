from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from apps.clinics.models import Counter
# from apps.clinics.serializers import (
#     CounterSerializer,
#     CounterListSerializer,
#     CounterCreateSerializer,
#     CounterAssignmentSerializer,
#     CounterStatsSerializer,
# )

from apps.clinics.models import Counter
from apps.clinics.serializers import CounterSerializer

from apps.accounts.permissions import IsManager
from apps.audit.services import log_action
from apps.audit.utils import build_audit_context

import logging
logger = logging.getLogger(__name__)


# class CounterViewSet(viewsets.ModelViewSet):
#     queryset = Counter.objects.all()
#     permission_classes = [IsAuthenticated, IsManager]

#     def get_serializer_class(self):
#         if self.action == "list":
#             return CounterListSerializer
#         if self.action == "create":
#             return CounterCreateSerializer
#         return CounterSerializer

    # 🔹 keep ALL your existing methods:
    # - get_queryset
    # - perform_create
    # - perform_update
    # - perform_destroy
    # - assign_device
    # - unassign_device
    # - stats
    # - my_counter


class CounterViewSet(viewsets.ModelViewSet):
    queryset = Counter.objects.filter(deleted_at__isnull=True)
    serializer_class = CounterSerializer


    @action(detail=True, methods=["post"])
    def assign_device(self, request, pk=None):
        counter = self.get_object()
        counter.device_id = request.data.get("device_id")
        counter.save(update_fields=["device_id"])
        return Response({"status": "Device assigned"})
    

    @action(detail=True, methods=["post"])
    def unassign_device(self, request, pk=None):
        counter = self.get_object()
        counter.device_id = None
        counter.save(update_fields=["device_id"])
        return Response({"status": "Device unassigned"})


    @action(detail=False, methods=["get"])
    def my_counter(self, request):
        counter = Counter.objects.filter(device_id=request.user.device_id).first()
        if not counter:
            return Response({}, status=status.HTTP_204_NO_CONTENT)
        return Response(CounterSerializer(counter).data)


