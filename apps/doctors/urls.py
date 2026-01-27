# apps/doctors/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DoctorViewSet, DoctorScheduleViewSet, DoctorLeaveViewSet

router = DefaultRouter()
router.register(r'doctors', DoctorViewSet, basename='doctor')
router.register(r'schedules', DoctorScheduleViewSet, basename='doctor-schedule')
router.register(r'leaves', DoctorLeaveViewSet, basename='doctor-leave')

urlpatterns = [
    path('', include(router.urls)),
]

# Additional URL patterns
urlpatterns += [
    path('doctors/<int:pk>/statistics/', DoctorViewSet.as_view({'get': 'statistics'}), name='doctor-statistics'),
    path('doctors/available/', DoctorViewSet.as_view({'get': 'available'}), name='doctors-available'),
    path('doctors/dashboard-stats/', DoctorViewSet.as_view({'get': 'dashboard_stats'}), name='doctors-dashboard-stats'),
    path('doctors/specializations/', DoctorViewSet.as_view({'get': 'specializations'}), name='doctor-specializations'),
    path('schedules/bulk-create/', DoctorScheduleViewSet.as_view({'post': 'bulk_create'}), name='schedule-bulk-create'),
    path('leaves/calendar/', DoctorLeaveViewSet.as_view({'get': 'calendar'}), name='leaves-calendar'),
    path('leaves/upcoming/', DoctorLeaveViewSet.as_view({'get': 'upcoming'}), name='leaves-upcoming'),
    path('leaves/summary/', DoctorLeaveViewSet.as_view({'get': 'summary'}), name='leaves-summary'),
]