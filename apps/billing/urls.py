from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'invoices', views.InvoiceViewSet, basename='invoice')
router.register(r'invoice-items', views.InvoiceItemViewSet, basename='invoice-item')
router.register(r'discount-policies', views.DiscountPolicyViewSet, basename='discount-policy')
router.register(r'applied-discounts', views.AppliedDiscountViewSet, basename='applied-discount')

urlpatterns = [
    path('', include(router.urls)),
    
    # Additional endpoints
    path('invoices/<int:pk>/print/', views.InvoiceViewSet.as_view({'get': 'retrieve'}), 
         name='invoice-print', kwargs={'print': True}),
]