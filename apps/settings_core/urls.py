# # apps/settings_core/urls.py
# from django.urls import path
# from . import views

# app_name = 'settings_core'

# urlpatterns = [
#     # TODO: Add API endpoints when we build the API layer
#     # path('system/', views.SystemSettingsView.as_view(), name='system-settings'),
#     # path('branch/', views.BranchSettingsView.as_view(), name='branch-settings'),
#     # path('clinic-config/', views.ClinicConfigView.as_view(), name='clinic-config'),
#     # path('holidays/', views.HolidayListView.as_view(), name='holiday-list'),
#     # path('taxes/', views.TaxConfigListView.as_view(), name='tax-list'),
# ]


# apps/settings_core/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'system-settings', views.SystemSettingViewSet, basename='system-settings')
router.register(r'branch-settings', views.BranchSettingViewSet, basename='branch-settings')
router.register(r'clinic-configurations', views.ClinicConfigurationViewSet, basename='clinic-configurations')
router.register(r'holidays', views.HolidayViewSet, basename='holidays')
router.register(r'tax-configurations', views.TaxConfigurationViewSet, basename='tax-configurations')
router.register(r'sms-configurations', views.SMSConfigurationViewSet, basename='sms-configurations')
router.register(r'email-configurations', views.EmailConfigurationViewSet, basename='email-configurations')
router.register(r'notification-templates', views.NotificationTemplateViewSet, basename='notification-templates')
router.register(r'settings-utility', views.SettingsUtilityViewSet, basename='settings-utility')

urlpatterns = [
    path('', include(router.urls)),
]