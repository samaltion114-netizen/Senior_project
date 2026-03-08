"""Celery application setup."""
from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "nahd_backend.settings")

app = Celery("nahd_backend")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
