from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from apps.clinics.models import Branch, Counter
from apps.clinics.serializers import (
    BranchListSerializer,
    CounterListSerializer,
)





# class BranchPublicView(ListAPIView):
#     permission_classes = [AllowAny]
#     serializer_class = BranchListSerializer

#     def get_queryset(self):
#         return Branch.objects.filter(
#             is_active=True,
#             deleted_at__isnull=True
#         ).order_by("name")


# class CounterPublicView(ListAPIView):
#     permission_classes = [AllowAny]
#     serializer_class = CounterListSerializer

#     def get_queryset(self):
#         return Counter.objects.filter(is_active=True)


class BranchPublicView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        branches = Branch.objects.filter(is_active=True)
        return Response(BranchListSerializer(branches, many=True).data)


class CounterPublicView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        counters = Counter.objects.filter(is_active=True)
        return Response(CounterListSerializer(counters, many=True).data)


class BranchAvailabilityView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, branch_id):
        return Response({"branch_id": branch_id, "available": True})
    

class NearestBranchView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"nearest_branch": None})
