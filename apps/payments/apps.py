from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    name = 'apps.payments'
    verbose_name = 'Payments Management'

    
    def ready(self):
        """Import signals when app is ready"""
        try:
            import apps.payments.signals
        except ImportError:
            pass