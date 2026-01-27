# apps/integrations/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    IntegrationTypeViewSet, IntegrationProviderViewSet,
    BranchIntegrationViewSet, PharmacyIntegrationViewSet,
    PaymentGatewayIntegrationViewSet, IntegrationLogViewSet,
    WebhookEventViewSet, PharmacyOrderViewSet,
    PaymentTransactionViewSet, WebhookReceiverView
)

router = DefaultRouter()
router.register(r'types', IntegrationTypeViewSet, basename='integration-type')
router.register(r'providers', IntegrationProviderViewSet, basename='integration-provider')
router.register(r'branch-integrations', BranchIntegrationViewSet, basename='branch-integration')
router.register(r'pharmacy-integrations', PharmacyIntegrationViewSet, basename='pharmacy-integration')
router.register(r'payment-integrations', PaymentGatewayIntegrationViewSet, basename='payment-integration')
router.register(r'logs', IntegrationLogViewSet, basename='integration-log')
router.register(r'webhooks', WebhookEventViewSet, basename='webhook-event')
router.register(r'pharmacy-orders', PharmacyOrderViewSet, basename='pharmacy-order')
router.register(r'payment-transactions', PaymentTransactionViewSet, basename='payment-transaction')

urlpatterns = [
    path('', include(router.urls)),
    path('webhook/receive/<str:provider>/<int:integration_id>/', 
         WebhookReceiverView.as_view(), name='webhook-receive'),
]