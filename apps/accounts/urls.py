# # apps/accounts/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    PasswordResetViewSet
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='users')
router.register(r'password', PasswordResetViewSet, basename='password-reset')

urlpatterns = [
    # JWT token endpoints
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),

    # REST API routes
    path('', include(router.urls)),
]
