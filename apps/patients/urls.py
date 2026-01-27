# clinic/Backend/apps/patients/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'patients', views.PatientViewSet, basename='patient')

urlpatterns = [
    # Router URLs for CRUD operations
    path('', include(router.urls)),
    
    # Patient custom actions
    path('patients/me/', views.PatientViewSet.as_view({'get': 'me'}), name='patient-me'),
    path('patients/search/', views.PatientViewSet.as_view({'get': 'search'}), name='patient-search'),
    path('patients/stats/', views.PatientViewSet.as_view({'get': 'stats'}), name='patient-stats'),
    path('patients/import/', views.PatientViewSet.as_view({'post': 'import_patients'}), name='import-patients'),
    path('patients/export/', views.PatientViewSet.as_view({'post': 'export_patients'}), name='export-patients'),
    path('patients/<uuid:pk>/medical-history/', views.PatientViewSet.as_view({'get': 'medical_history', 'put': 'medical_history'}), name='patient-medical-history'),
    path('patients/<uuid:pk>/emergency-contact/', views.PatientViewSet.as_view({'get': 'emergency_contact', 'put': 'emergency_contact'}), name='patient-emergency-contact'),
    
    # Public endpoints
    path('public/register/', views.PatientRegistrationView.as_view(), name='patient-registration'),
    
    # Dashboard
    path('dashboard/', views.PatientDashboardView.as_view(), name='patient-dashboard'),
    
    # Health check
    path('health/', views.PatientsHealthCheckView.as_view(), name='patients-health'),
]

app_name = 'patients'