# apps/prescriptions/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PrescriptionViewSet, MedicationViewSet,
    PrescriptionItemViewSet, PrescriptionTemplateViewSet
)

router = DefaultRouter()
router.register(r'prescriptions', PrescriptionViewSet, basename='prescription')
router.register(r'medications', MedicationViewSet, basename='medication')
router.register(r'prescription-items', PrescriptionItemViewSet, basename='prescription-item')
router.register(r'templates', PrescriptionTemplateViewSet, basename='prescription-template')

urlpatterns = [
    path('', include(router.urls)),
]

# Additional URL patterns
urlpatterns += [
    # Prescription actions
    path('prescriptions/<int:pk>/sign/', PrescriptionViewSet.as_view({'post': 'sign'}), name='prescription-sign'),
    path('prescriptions/<int:pk>/dispense/', PrescriptionViewSet.as_view({'post': 'dispense'}), name='prescription-dispense'),
    path('prescriptions/<int:pk>/refill/', PrescriptionViewSet.as_view({'post': 'refill'}), name='prescription-refill'),
    path('prescriptions/<int:pk>/cancel/', PrescriptionViewSet.as_view({'post': 'cancel'}), name='prescription-cancel'),
    path('prescriptions/<int:pk>/print/', PrescriptionViewSet.as_view({'get': 'print'}), name='prescription-print'),
    
    # Prescription bulk operations
    path('prescriptions/search/', PrescriptionViewSet.as_view({'get': 'search'}), name='prescription-search'),
    path('prescriptions/stats/', PrescriptionViewSet.as_view({'get': 'stats'}), name='prescription-stats'),
    path('prescriptions/export/', PrescriptionViewSet.as_view({'get': 'export'}), name='prescription-export'),
    
    # Medication actions
    path('medications/<int:pk>/update-stock/', MedicationViewSet.as_view({'post': 'update_stock'}), name='medication-update-stock'),
    path('medications/low-stock/', MedicationViewSet.as_view({'get': 'low_stock'}), name='medication-low-stock'),
    path('medications/expired/', MedicationViewSet.as_view({'get': 'expired'}), name='medication-expired'),
    path('medications/categories/', MedicationViewSet.as_view({'get': 'categories'}), name='medication-categories'),
    path('medications/search-autocomplete/', MedicationViewSet.as_view({'get': 'search_autocomplete'}), name='medication-search-autocomplete'),
    
    # Prescription item actions
    path('prescription-items/<int:pk>/dispense-item/', PrescriptionItemViewSet.as_view({'post': 'dispense_item'}), name='prescription-item-dispense'),
    
    # Template actions
    path('templates/<int:pk>/apply/', PrescriptionTemplateViewSet.as_view({'post': 'apply'}), name='template-apply'),
]