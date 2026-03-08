"""Serializers for trainer reviews."""
from __future__ import annotations

from rest_framework import serializers

from reviews.models import AdminReview


class AdminReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminReview
        fields = ("id", "proof", "reviewer", "is_bug_confirmed", "notes", "created_at")
        read_only_fields = ("reviewer", "created_at")
