from django.apps import AppConfig


class SettingsCoreConfig(AppConfig):
    name = 'apps.settings_core'
    verbose_name = 'System Settings'
    
    def ready(self):
        import apps.settings_core.signals