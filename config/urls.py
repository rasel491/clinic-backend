from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

        # API endpoints
    path('api/accounts/', include('apps.accounts.urls')),
    path('api/audit/', include('apps.audit.urls')),
    
    path('api/clinics/', include('apps.clinics.urls')),

     path('api/patients/', include('apps.patients.urls')),
    path('api/doctors/', include('apps.doctors.urls')),
    path('api/prescriptions/', include('apps.prescriptions.urls')),
    path('api/treatments/', include('apps.treatments.urls')),
    path('api/visits/', include('apps.visits.urls')),

    path('api/billing/', include('apps.billing.urls')),
    path('api/payments/', include('apps.payments.urls')),
    path('api/eod/', include('apps.eod.urls')),
    
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/otp/', include('apps.otp.urls')),
    path('api/reports/', include('apps.reports.urls')),
    path('api/settings/', include('apps.settings_core.urls')),
    # path('api/integrations/', include('apps.integrations.urls')),
    # path('api/inventory/', include('apps.inventory.urls')), #later
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)