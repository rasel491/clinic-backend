# # apps/notifications/urls.py
# from django.urls import path, include
# from rest_framework.routers import DefaultRouter
# from .views import (
#     NotificationTemplateViewSet, NotificationLogViewSet,
#     SMSProviderViewSet, EmailProviderViewSet,
#     NotificationSettingViewSet, NotificationQueueViewSet
# )

# router = DefaultRouter()
# router.register(r'templates', NotificationTemplateViewSet, basename='notification-template')
# router.register(r'logs', NotificationLogViewSet, basename='notification-log')
# router.register(r'sms-providers', SMSProviderViewSet, basename='sms-provider')
# router.register(r'email-providers', EmailProviderViewSet, basename='email-provider')
# router.register(r'settings', NotificationSettingViewSet, basename='notification-setting')
# router.register(r'queue', NotificationQueueViewSet, basename='notification-queue')

# urlpatterns = [
#     path('', include(router.urls)),
# ]

# apps/notifications/urls.py (unchanged - this is correct)
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    NotificationTemplateViewSet, NotificationLogViewSet,
    SMSProviderViewSet, EmailProviderViewSet,
    NotificationSettingViewSet, NotificationQueueViewSet
)

router = DefaultRouter()
router.register(r'templates', NotificationTemplateViewSet, basename='notification-template')
router.register(r'logs', NotificationLogViewSet, basename='notification-log')
router.register(r'sms-providers', SMSProviderViewSet, basename='sms-provider')
router.register(r'email-providers', EmailProviderViewSet, basename='email-provider')
router.register(r'settings', NotificationSettingViewSet, basename='notification-setting')
router.register(r'queue', NotificationQueueViewSet, basename='notification-queue')

urlpatterns = [
    path('', include(router.urls)),
]