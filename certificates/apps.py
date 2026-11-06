# dems-backend/certificates/apps.py
from django.apps import AppConfig


class CertificatesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'certificates'

    def ready(self):
        # Registers the post_save signal that auto-generates certificates
        from . import signals  # noqa: F401