# apps/treatments/urls.py

# apps/treatments/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TreatmentCategoryViewSet, TreatmentViewSet, ToothChartViewSet,
    TreatmentPlanViewSet, TreatmentPlanItemViewSet, TreatmentNoteViewSet,
    TreatmentTemplateViewSet, TreatmentDashboardView
)

router = DefaultRouter()

# Register viewsets
router.register(r'categories', TreatmentCategoryViewSet, basename='treatment-category')
router.register(r'treatments', TreatmentViewSet, basename='treatment')
router.register(r'tooth-chart', ToothChartViewSet, basename='tooth-chart')
router.register(r'plans', TreatmentPlanViewSet, basename='treatment-plan')
router.register(r'plan-items', TreatmentPlanItemViewSet, basename='treatment-plan-item')
router.register(r'notes', TreatmentNoteViewSet, basename='treatment-note')
router.register(r'templates', TreatmentTemplateViewSet, basename='treatment-template')

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    
    # Dashboard
    path('api/dashboard/', TreatmentDashboardView.as_view(), name='treatments-dashboard'),
    
    # Quick actions
    path('api/plans/<int:pk>/update-status/', 
         TreatmentPlanViewSet.as_view({'post': 'update_status'}), 
         name='treatment-plan-update-status'),
    path('api/plans/<int:pk>/create-revision/', 
         TreatmentPlanViewSet.as_view({'post': 'create_revision'}), 
         name='treatment-plan-create-revision'),
    path('api/plan-items/<int:pk>/update-status/', 
         TreatmentPlanItemViewSet.as_view({'post': 'update_status'}), 
         name='plan-item-update-status'),
    path('api/plan-items/<int:pk>/schedule-visit/', 
         TreatmentPlanItemViewSet.as_view({'post': 'schedule_visit'}), 
         name='plan-item-schedule-visit'),
    
    # Convenience endpoints
    path('api/treatments/catalog/', 
         TreatmentViewSet.as_view({'get': 'catalog'}), 
         name='treatment-catalog'),
    path('api/treatments/popular/', 
         TreatmentViewSet.as_view({'get': 'popular'}), 
         name='treatment-popular'),
    path('api/treatments/suggest/', 
         TreatmentViewSet.as_view({'get': 'suggest'}), 
         name='treatment-suggest'),
    path('api/plans/active/', 
         TreatmentPlanViewSet.as_view({'get': 'active_plans'}), 
         name='active-plans'),
    path('api/plans/todays/', 
         TreatmentPlanViewSet.as_view({'get': 'todays_plans'}), 
         name='todays-plans'),
    path('api/plans/create-with-items/', 
         TreatmentPlanViewSet.as_view({'post': 'create_with_items'}), 
         name='create-plan-with-items'),
    path('api/plan-items/todays/', 
         TreatmentPlanItemViewSet.as_view({'get': 'todays_items'}), 
         name='todays-plan-items'),
    
    # Export
    path('api/plans/export/', 
         TreatmentPlanViewSet.as_view({'get': 'export'}), 
         name='export-plans'),
    
    # Apply template
    path('api/templates/<int:pk>/apply/', 
         TreatmentTemplateViewSet.as_view({'post': 'apply_to_patient'}), 
         name='apply-template'),
]

