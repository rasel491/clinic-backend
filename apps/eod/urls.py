# apps/eod/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'eod-locks', views.EodLockViewSet, basename='eod-lock')
router.register(r'daily-summaries', views.DailySummaryViewSet, basename='daily-summary')
router.register(r'cash-reconciliations', views.CashReconciliationViewSet, basename='cash-reconciliation')
router.register(r'eod-exceptions', views.EodExceptionViewSet, basename='eod-exception')

urlpatterns = [
    path('', include(router.urls)),
    
    # API endpoints
    path('check-date-lock/', views.CheckDateLockStatusAPIView.as_view(), name='check-date-lock'),
    path('cash-position/', views.GetCashPositionAPIView.as_view(), name='cash-position'),
    path('generate-report/', views.GenerateEodReportAPIView.as_view(), name='generate-report'),
    path('validate-transaction-date/', views.ValidateTransactionDateAPIView.as_view(), name='validate-transaction-date'),
]