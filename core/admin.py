"""Admin for core app."""
from django.contrib import admin

from core.models import (
    LearningPath,
    Objective,
    ObjectiveMilestone,
    PathAdjustment,
    PerformanceMetric,
    PortfolioAsset,
    PortfolioProject,
    ProgressSnapshot,
    Task,
)


@admin.register(Objective)
class ObjectiveAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "title", "status", "suggested_by")
    list_filter = ("status", "suggested_by")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "objective", "title", "estimated_minutes", "order")


@admin.register(ObjectiveMilestone)
class ObjectiveMilestoneAdmin(admin.ModelAdmin):
    list_display = ("id", "objective", "title", "priority", "order", "status")


@admin.register(LearningPath)
class LearningPathAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "current_level", "status", "updated_at")


@admin.register(PathAdjustment)
class PathAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("id", "learning_path", "before_level", "after_level", "source", "created_at")


@admin.register(ProgressSnapshot)
class ProgressSnapshotAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "snapshot_date", "overall_progress_percent", "skill_score")


@admin.register(PerformanceMetric)
class PerformanceMetricAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "period_start", "period_end", "success_rate", "speed_score")


@admin.register(PortfolioProject)
class PortfolioProjectAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "title", "visibility", "updated_at")


@admin.register(PortfolioAsset)
class PortfolioAssetAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "caption", "created_at")
