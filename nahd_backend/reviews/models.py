"""Trainer/admin review models."""
from __future__ import annotations

from django.conf import settings
from django.db import models


class AdminReview(models.Model):
    """Trainer review result for a proof analysis."""

    proof = models.ForeignKey("proofs.Proof", on_delete=models.CASCADE, related_name="admin_reviews")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="admin_reviews")
    is_bug_confirmed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
