"""Serializers for schedule optimization."""
from __future__ import annotations

from rest_framework import serializers

from scheduling.models import Session


class WeeklyAvailabilitySerializer(serializers.Serializer):
    weekly_availability = serializers.JSONField()
    objective_id = serializers.IntegerField()
    max_daily_minutes = serializers.IntegerField(required=False, default=120)
    break_minutes = serializers.IntegerField(required=False, default=10)
    start_date = serializers.DateField(required=False)


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = ("id", "student", "task", "scheduled_start", "scheduled_end", "status", "duration_minutes")
        read_only_fields = ("student", "status")
