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
    TaskComment,
)


class TaskSerializer(serializers.ModelSerializer):
    session_id = serializers.SerializerMethodField()
    scheduled_day = serializers.SerializerMethodField()
    estimated_duration = serializers.IntegerField(source="estimated_minutes", read_only=True)
    is_scheduled = serializers.SerializerMethodField()

    def get_session_id(self, obj: Task):
        session = obj.sessions.order_by("scheduled_start").first()
        return session.id if session else None

    def get_scheduled_day(self, obj: Task):
        session = obj.sessions.order_by("scheduled_start").first()
        return session.scheduled_start.strftime("%A") if session else None

    def get_is_scheduled(self, obj: Task) -> bool:
        return obj.sessions.exists()

    class Meta:
        model = Task
        fields = (
            "id",
            "objective",
            "title",
            "description",
            "status",
            "type",
            "difficulty_level",
            "task_size",
            "xp_reward",
            "estimated_minutes",
            "estimated_duration",
            "estimation_confidence",
            "order",
            "metadata",
            "expected_output_text",
            "youtube_link_ar",
            "youtube_link_en",
            "session_id",
            "scheduled_day",
            "is_scheduled",
        )
        read_only_fields = ("objective", "estimated_minutes", "estimation_confidence")


class CompletedTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ("id", "title", "description", "status", "order", "xp_reward")


class ObjectiveSerializer(serializers.ModelSerializer):
    tasks = TaskSerializer(many=True, read_only=True)
    has_unscheduled_tasks = serializers.SerializerMethodField()

    def get_has_unscheduled_tasks(self, obj: Objective) -> bool:
        return obj.tasks.filter(sessions__isnull=True).exists()

    class Meta:
        model = Objective
        fields = (
            "id",
            "student",
            "title",
            "description",
            "suggested_by",
            "status",
            "linkedin_generated_text",
            "created_at",
            "has_unscheduled_tasks",
            "tasks",
        )
        read_only_fields = ("student", "created_at", "linkedin_generated_text")


class PortfolioGoalSerializer(serializers.ModelSerializer):
    goal_title = serializers.CharField(source="title", read_only=True)
    completed_tasks = serializers.SerializerMethodField()
    all_tasks_completed = serializers.SerializerMethodField()

    def get_completed_tasks(self, obj: Objective):
        tasks = obj.tasks.filter(status=Task.STATUS_COMPLETED).order_by("order", "id")
        return CompletedTaskSerializer(tasks, many=True).data

    def get_all_tasks_completed(self, obj: Objective) -> bool:
        total_tasks = obj.tasks.count()
        if not total_tasks:
            return False
        return not obj.tasks.exclude(status=Task.STATUS_COMPLETED).exists()

    class Meta:
        model = Objective
        fields = ("id", "goal_title", "linkedin_generated_text", "completed_tasks", "all_tasks_completed")
        read_only_fields = fields


class CreateTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = (
            "title",
            "description",
            "status",
            "type",
            "difficulty_level",
            "task_size",
            "xp_reward",
            "order",
            "metadata",
            "expected_output_text",
            "youtube_link_ar",
            "youtube_link_en",
        )


class TaskUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = (
            "title",
            "description",
            "status",
            "type",
            "difficulty_level",
            "task_size",
            "xp_reward",
            "order",
            "metadata",
            "expected_output_text",
            "youtube_link_ar",
            "youtube_link_en",
        )


class GenerateTasksSerializer(serializers.Serializer):
    user_level = serializers.ChoiceField(choices=["beginner", "intermediate", "advanced"], required=False, default="intermediate")
    count = serializers.IntegerField(min_value=1, max_value=10, default=5)


class TaskCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.username", read_only=True)

    class Meta:
        model = TaskComment
        fields = ("id", "task", "author", "author_name", "body", "created_at")
        read_only_fields = ("task", "author", "created_at")


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
