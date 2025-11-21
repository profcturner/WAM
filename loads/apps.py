# apps.py
from django.apps import AppConfig

# This override of the default configuration is required to enable signals
class LoadsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'loads'
    def ready(self):
        import loads.signals
