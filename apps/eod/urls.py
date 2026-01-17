# apps/eod/urls.py
from django.urls import path
from . import views

app_name = 'eod'

urlpatterns = [
    # TODO: Add API endpoints when we build the API layer
    # path('eod/', views.EodListView.as_view(), name='eod-list'),
    # path('eod/<uuid:pk>/', views.EodDetailView.as_view(), name='eod-detail'),
    # path('eod/<uuid:pk>/lock/', views.LockEodView.as_view(), name='eod-lock'),
    # path('eod/<uuid:pk>/reverse/', views.ReverseEodView.as_view(), name='eod-reverse'),
]