# apps/reports/urls.py
from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # TODO: Add API endpoints when we build the API layer
    # path('templates/', views.ReportTemplateListView.as_view(), name='template-list'),
    # path('templates/<uuid:pk>/', views.ReportTemplateDetailView.as_view(), name='template-detail'),
    # path('generate/', views.GenerateReportView.as_view(), name='generate-report'),
    # path('generated/<uuid:pk>/', views.GeneratedReportDetailView.as_view(), name='generated-report-detail'),
    # path('dashboards/', views.DashboardListView.as_view(), name='dashboard-list'),
    # path('dashboards/<uuid:pk>/', views.DashboardDetailView.as_view(), name='dashboard-detail'),
]