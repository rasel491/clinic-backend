# apps/otp/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    OTPConfigViewSet, OTPRequestViewSet, OTPBlacklistViewSet,
    OTPRateLimitViewSet, OTPTemplateViewSet, PublicOTPView
)

router = DefaultRouter()
router.register(r'configs', OTPConfigViewSet, basename='otp-config')
router.register(r'requests', OTPRequestViewSet, basename='otp-request')
router.register(r'blacklists', OTPBlacklistViewSet, basename='otp-blacklist')
router.register(r'rate-limits', OTPRateLimitViewSet, basename='otp-rate-limit')
router.register(r'templates', OTPTemplateViewSet, basename='otp-template')

urlpatterns = [
    path('', include(router.urls)),
    path('public/<str:action>/', PublicOTPView.as_view(), name='public-otp'),
]