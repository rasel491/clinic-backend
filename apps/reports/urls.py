# # apps/reports/urls.py
# from django.urls import path
# from . import views

# app_name = 'reports'

# urlpatterns = [
#     # TODO: Add API endpoints when we build the API layer
#     # path('templates/', views.ReportTemplateListView.as_view(), name='template-list'),
#     # path('templates/<uuid:pk>/', views.ReportTemplateDetailView.as_view(), name='template-detail'),
#     # path('generate/', views.GenerateReportView.as_view(), name='generate-report'),
#     # path('generated/<uuid:pk>/', views.GeneratedReportDetailView.as_view(), name='generated-report-detail'),
#     # path('dashboards/', views.DashboardListView.as_view(), name='dashboard-list'),
#     # path('dashboards/<uuid:pk>/', views.DashboardDetailView.as_view(), name='dashboard-detail'),
# ]



# apps/reports/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ReportCategoryViewSet, ReportTemplateViewSet,
    GeneratedReportViewSet, DashboardViewSet,
    DashboardWidgetViewSet, ReportScheduleViewSet,
    ReportExportViewSet, ReportFavoriteViewSet,
    ReportsAPIView, ReportStatisticsAPIView,
    BranchPerformanceAPIView, FinancialSummaryAPIView,
    QuickReportsAPIView
)

router = DefaultRouter()
router.register(r'categories', ReportCategoryViewSet, basename='report-category')
router.register(r'templates', ReportTemplateViewSet, basename='report-template')
router.register(r'generated', GeneratedReportViewSet, basename='generated-report')
router.register(r'dashboards', DashboardViewSet, basename='dashboard')
router.register(r'widgets', DashboardWidgetViewSet, basename='dashboard-widget')
router.register(r'schedules', ReportScheduleViewSet, basename='report-schedule')
router.register(r'exports', ReportExportViewSet, basename='report-export')
router.register(r'favorites', ReportFavoriteViewSet, basename='report-favorite')

urlpatterns = [
    path('', include(router.urls)),
    
    # API endpoints
    path('list/', ReportsAPIView.as_view(), name='report-list'),
    path('statistics/', ReportStatisticsAPIView.as_view(), name='report-statistics'),
    path('branch-performance/', BranchPerformanceAPIView.as_view(), name='branch-performance'),
    path('financial-summary/', FinancialSummaryAPIView.as_view(), name='financial-summary'),
    path('quick/<str:report_type>/', QuickReportsAPIView.as_view(), name='quick-reports'),
    
    # Widget data endpoint
    path('widget-data/', DashboardWidgetViewSet.as_view({'post': 'data'}), name='widget-data'),
]