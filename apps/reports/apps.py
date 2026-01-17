from django.apps import AppConfig


class ReportsConfig(AppConfig):
    name = 'apps.reports'
    verbose_name = 'Reports & Analytics'
    
    def ready(self):
        import apps.reports.signals 