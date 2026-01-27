from django.apps import AppConfig


class BillingConfig(AppConfig):
    name = 'apps.billing'
    # verbose_name = 'Billing & Invoicing'
    verbose_name = 'Billing Management'
    
    def ready(self):
        """Import signals when app is ready"""
        try:
            from . import signals
        except ImportError:
            pass