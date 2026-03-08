"""Nahd backend package."""

try:
    from .celery_app import app as celery_app
except Exception:  # pragma: no cover - allows local/test env without Celery package
    celery_app = None

__all__ = ("celery_app",)
