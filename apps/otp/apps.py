# apps/otp/apps.py
from django.apps import AppConfig


class OtpConfig(AppConfig):
    name = 'apps.otp'
    
    def ready(self):
        import apps.otp.signals