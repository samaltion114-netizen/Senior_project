"""Scheduling models."""
from __future__ import annotations

from django.conf import settings
from django.db import models


class Session(models.Model):
    """Scheduled execution block for one task."""

    STATUS_PLANNED = "planned"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [(STATUS_PLANNED, "Planned"), (STATUS_COMPLETED, "Completed")]

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sessions")
    task = models.ForeignKey("core.Task", on_delete=models.CASCADE, related_name="sessions")
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNED)
    duration_minutes = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("scheduled_start",)

    def __str__(self) -> str:
        return f"Session<{self.student.username}:{self.task.title}>"
