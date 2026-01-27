from django.apps import AppConfig


class VisitsConfig(AppConfig):
    name = 'apps.visits'
    verbose_name = 'Visits & Appointments'

    # verbose_name = 'Visits Management'
    
    def ready(self):
        """Import and connect signals when app is ready"""
        import apps.visits.signals