"""Celery application setup."""
from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

app = Celery("project_root")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
