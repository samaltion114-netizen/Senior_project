"""Core domain models for objectives and tasks."""
from __future__ import annotations

from django.conf import settings
from django.db import models


class Objective(models.Model):
    """A SMART-style objective assigned to a student."""

    STATUS_DRAFT = "draft"
    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_COMPLETED, "Completed"),
    ]

    SUGGESTED_BY_AI = "ai"
    SUGGESTED_BY_EXPERT = "expert"
    SUGGESTED_BY_STUDENT = "student"
    SUGGESTED_BY_CHOICES = [
        (SUGGESTED_BY_AI, "AI"),
        (SUGGESTED_BY_EXPERT, "Expert"),
        (SUGGESTED_BY_STUDENT, "Student"),
    ]

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="objectives")
    title = models.CharField(max_length=255)
    description = models.TextField()
    suggested_by = models.CharField(max_length=20, choices=SUGGESTED_BY_CHOICES, default=SUGGESTED_BY_AI)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.student.username}: {self.title}"


class Task(models.Model):
    """Task under a given objective."""

    objective = models.ForeignKey(Objective, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    estimated_minutes = models.PositiveIntegerField(default=30)
    estimation_confidence = models.FloatField(default=0.5)
    order = models.PositiveIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)
    expected_output_text = models.TextField(blank=True)
    expected_output_embedding = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("order", "id")

    def __str__(self) -> str:
        return self.title


class ObjectiveMilestone(models.Model):
    """Decomposed step under an objective."""

    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_DONE = "done"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_DONE, "Done"),
    ]

    objective = models.ForeignKey(Objective, on_delete=models.CASCADE, related_name="milestones")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("order", "id")


class LearningPath(models.Model):
    """Adaptive learning path state for student."""

    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = [(STATUS_ACTIVE, "Active"), (STATUS_PAUSED, "Paused"), (STATUS_COMPLETED, "Completed")]

    student = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="learning_path")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    current_level = models.PositiveSmallIntegerField(default=1)
    adaptation_notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class PathAdjustment(models.Model):
    """History of adaptive path changes."""

    SOURCE_PROOF = "proof"
    SOURCE_REVIEW = "review"
    SOURCE_SYSTEM = "system"
    SOURCE_CHOICES = [(SOURCE_PROOF, "Proof"), (SOURCE_REVIEW, "Review"), (SOURCE_SYSTEM, "System")]

    learning_path = models.ForeignKey(LearningPath, on_delete=models.CASCADE, related_name="adjustments")
    before_level = models.PositiveSmallIntegerField()
    after_level = models.PositiveSmallIntegerField()
    reason = models.TextField()
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_SYSTEM)
    related_proof = models.ForeignKey("proofs.Proof", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class ProgressSnapshot(models.Model):
    """Precomputed progress summary for dashboard rendering."""

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="progress_snapshots")
    snapshot_date = models.DateField()
    overall_progress_percent = models.FloatField(default=0.0)
    skill_score = models.FloatField(default=0.0)
    active_tasks = models.PositiveIntegerField(default=0)
    completed_tasks = models.PositiveIntegerField(default=0)
    recommendations_count = models.PositiveIntegerField(default=0)
    notifications_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-snapshot_date", "-id")
        unique_together = ("student", "snapshot_date")


class PerformanceMetric(models.Model):
    """Performance model outputs over a time window."""

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="performance_metrics")
    period_start = models.DateField()
    period_end = models.DateField()
    avg_task_minutes = models.FloatField(default=0.0)
    success_rate = models.FloatField(default=0.0)
    failure_rate = models.FloatField(default=0.0)
    speed_score = models.FloatField(default=0.0)
    repeated_issues_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-period_end", "-id")


class PortfolioProject(models.Model):
    """Portfolio entry for student achievements."""

    VIS_PUBLIC = "public"
    VIS_PRIVATE = "private"
    VISIBILITY_CHOICES = [(VIS_PUBLIC, "Public"), (VIS_PRIVATE, "Private")]

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="portfolio_projects")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    tech_stack = models.JSONField(default=list, blank=True)
    project_url = models.URLField(blank=True)
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default=VIS_PRIVATE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-id")


def portfolio_asset_path(instance: "PortfolioAsset", filename: str) -> str:
    return f"portfolio/{instance.project.student_id}/{instance.project_id}/{filename}"


class PortfolioAsset(models.Model):
    """Asset uploaded under portfolio project."""

    project = models.ForeignKey(PortfolioProject, on_delete=models.CASCADE, related_name="assets")
    file = models.FileField(upload_to=portfolio_asset_path)
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
