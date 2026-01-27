from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.utils.timezone import now

from apps.clinics.models import Branch, Counter





# class ClinicsHealthCheckView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         return Response({
#             "status": "healthy",
#             "branches": Branch.objects.count(),
#             "counters": Counter.objects.count(),
#             "timestamp": timezone.now(),
#         })


class ClinicsHealthCheckView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({
            "service": "clinics",
            "status": "healthy",
            "timestamp": now(),
        })
