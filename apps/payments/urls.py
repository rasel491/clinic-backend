from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'payment-methods', views.PaymentMethodViewSet, basename='payment-method')
router.register(r'payments', views.PaymentViewSet, basename='payment')
router.register(r'refunds', views.RefundViewSet, basename='refund')
router.register(r'receipts', views.PaymentReceiptViewSet, basename='receipt')

urlpatterns = [
    path('', include(router.urls)),
    
    # Additional endpoints
    path('payments/daily-summary/', views.PaymentViewSet.as_view({'get': 'daily_summary'}), 
         name='payment-daily-summary'),
    path('receipts/verify/', views.PaymentReceiptViewSet.as_view({'get': 'verify'}), 
         name='receipt-verify'),
    
    # Print endpoints
    path('payments/<int:pk>/print-receipt/', views.PaymentViewSet.as_view({'get': 'retrieve'}), 
         name='payment-print-receipt', kwargs={'print': True}),
    path('receipts/<int:pk>/print/', views.PaymentReceiptViewSet.as_view({'get': 'retrieve'}), 
         name='receipt-print', kwargs={'print': True}),
]