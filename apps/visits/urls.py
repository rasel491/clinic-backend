# apps/visits/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    VisitViewSet, AppointmentViewSet, QueueViewSet,
    VisitVitalSignViewSet, VisitDocumentViewSet,
    DashboardView, DoctorScheduleView, PublicAppointmentView
)

router = DefaultRouter()

# Register viewsets
router.register(r'visits', VisitViewSet, basename='visit')
router.register(r'appointments', AppointmentViewSet, basename='appointment')
router.register(r'queues', QueueViewSet, basename='queue')
router.register(r'vital-signs', VisitVitalSignViewSet, basename='vital-sign')
router.register(r'documents', VisitDocumentViewSet, basename='document')

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    
    # Dashboard and schedule views
    path('api/dashboard/', DashboardView.as_view(), name='visits-dashboard'),
    path('api/doctor-schedule/', DoctorScheduleView.as_view(), name='doctor-schedule'),
    
    # Public endpoints (for patient booking)
    path('api/public/appointments/', PublicAppointmentView.as_view(), name='public-appointments'),
    
    # Quick actions (simplified endpoints for specific actions)
    path('api/quick/checkin/<int:visit_id>/', 
         VisitViewSet.as_view({'post': 'check_in'}), 
         name='quick-checkin'),
    path('api/quick/complete-consultation/<int:visit_id>/', 
         VisitViewSet.as_view({'post': 'complete_consultation'}), 
         name='quick-complete-consultation'),
    path('api/quick/call-patient/<int:queue_id>/', 
         QueueViewSet.as_view({'post': 'call_patient'}), 
         name='quick-call-patient'),
    
    # Today's views
    path('api/today/visits/', 
         VisitViewSet.as_view({'get': 'todays_visits'}), 
         name='todays-visits'),
    path('api/today/appointments/', 
         AppointmentViewSet.as_view({'get': 'todays'}), 
         name='todays-appointments'),
    path('api/today/queue/<int:branch_id>/', 
         QueueViewSet.as_view({'get': 'current_queue'}), 
         name='today-queue'),
    
    # Export endpoints
    path('api/visits/export/', 
         VisitViewSet.as_view({'get': 'export'}), 
         name='export-visits'),
]

