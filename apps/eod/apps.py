from django.apps import AppConfig


class EodConfig(AppConfig):
    name = 'apps.eod'
    verbose_name = 'End of Day Management'

    def ready(self):
        import apps.eod.signals 