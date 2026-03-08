"""Serializers for objective/task APIs."""
from __future__ import annotations

from rest_framework import serializers

from core.models import (
    Objective,
    ObjectiveMilestone,
    PerformanceMetric,
    PortfolioAsset,
    PortfolioProject,
    ProgressSnapshot,
    Task,
)


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = (
            "id",
            "objective",
            "title",
            "description",
            "estimated_minutes",
            "estimation_confidence",
            "order",
            "metadata",
            "expected_output_text",
        )
        read_only_fields = ("objective", "estimated_minutes", "estimation_confidence")


class ObjectiveSerializer(serializers.ModelSerializer):
    tasks = TaskSerializer(many=True, read_only=True)

    class Meta:
        model = Objective
        fields = ("id", "student", "title", "description", "suggested_by", "status", "created_at", "tasks")
        read_only_fields = ("student", "created_at")


class CreateTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ("title", "description", "order", "metadata", "expected_output_text")


class ObjectiveMilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ObjectiveMilestone
        fields = ("id", "objective", "title", "description", "priority", "order", "status", "created_at")
        read_only_fields = ("objective", "created_at")


class ProgressSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProgressSnapshot
        fields = (
            "id",
            "snapshot_date",
            "overall_progress_percent",
            "skill_score",
            "active_tasks",
            "completed_tasks",
            "recommendations_count",
            "notifications_count",
            "metadata",
        )


class PerformanceMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceMetric
        fields = (
            "id",
            "period_start",
            "period_end",
            "avg_task_minutes",
            "success_rate",
            "failure_rate",
            "speed_score",
            "repeated_issues_count",
        )


class PortfolioAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioAsset
        fields = ("id", "project", "file", "caption", "created_at")
        read_only_fields = ("project", "created_at")


class PortfolioAssetUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    caption = serializers.CharField(max_length=255, required=False, allow_blank=True)


class PortfolioProjectSerializer(serializers.ModelSerializer):
    assets = PortfolioAssetSerializer(many=True, read_only=True)

    class Meta:
        model = PortfolioProject
        fields = ("id", "student", "title", "description", "tech_stack", "project_url", "visibility", "assets")
        read_only_fields = ("student",)
