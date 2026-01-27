# clinic/Backend/apps/clinics/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from apps.clinics import views
from apps.clinics.views.clinic import (
    ClinicOverviewView,
    ClinicStatsView,
)

router = DefaultRouter()
router.register(r'branches', views.BranchViewSet, basename='branch')
router.register(r'counters', views.CounterViewSet, basename='counter')

urlpatterns = [
    # Router URLs for CRUD operations
    path('', include(router.urls)),
    
    # Branch custom actions
    path('branches/<uuid:pk>/lock-eod/', views.BranchViewSet.as_view({'post': 'eod_lock'}), name='branch-lock-eod'),
    path('branches/<uuid:pk>/unlock-eod/', views.BranchViewSet.as_view({'post': 'eod_unlock'}), name='branch-unlock-eod'),
    path('branches/<uuid:pk>/statistics/', views.BranchViewSet.as_view({'get': 'stats'}), name='branch-statistics'),
    path('branches/<uuid:pk>/operational-hours/', views.BranchViewSet.as_view({'get': 'operational_hours', 'put': 'operational_hours'}), name='branch-operational-hours'),
    path('branches/<uuid:pk>/configuration/', views.BranchViewSet.as_view({'get': 'configuration', 'put': 'configuration'}), name='branch-configuration'),
    
    # clinic custom actions
    path("clinic/overview/", ClinicOverviewView.as_view(), name="clinic-overview"),
    path("clinic/stats/", ClinicStatsView.as_view(), name="clinic-stats"),

    # Counter custom actions
    path('counters/<uuid:pk>/assign-device/', views.CounterViewSet.as_view({'post': 'assign_device'}), name='counter-assign-device'),
    path('counters/<uuid:pk>/unassign-device/', views.CounterViewSet.as_view({'post': 'unassign_device'}), name='counter-unassign-device'),
    path('counters/<uuid:pk>/statistics/', views.CounterViewSet.as_view({'get': 'stats'}), name='counter-statistics'),
    
    # Public endpoints
    path('public/branches/', views.BranchPublicView.as_view(), name='public-branches'),
    path('public/counters/', views.CounterPublicView.as_view(), name='public-counters'),
    path('public/branches/<uuid:branch_id>/availability/', views.BranchAvailabilityView.as_view(), name='public-branch-availability'),
    path('public/branches/nearest/', views.NearestBranchView.as_view(), name='nearest-branch'),
    
    # User-specific endpoints
    path('my-counter/', views.CounterViewSet.as_view({'get': 'my_counter'}), name='my-counter'),
    
    # Bulk operations
    path('branches-bulk/import/', views.BranchViewSet.as_view({'post': 'import_branches'}), name='import-branches'),
    path('branches-bulk/export/', views.BranchViewSet.as_view({'post': 'export_branches'}), name='export-branches'),
    path('branches/search/', views.BranchViewSet.as_view({'get': 'search'}), name='search-branches'),
    path('branches/geo-data/', views.BranchViewSet.as_view({'get': 'geo_data'}), name='branches-geo-data'),
    path('branches/sync/', views.BranchViewSet.as_view({'post': 'sync'}), name='branches-sync'),
    path('branches/all-statistics/', views.BranchViewSet.as_view({'get': 'all_stats'}), name='all-branches-stats'),
    
    # Health check
    path('health/', views.ClinicsHealthCheckView.as_view(), name='clinics-health'),
]

app_name = 'clinics'