"""Proof and adaptive learning models."""
from __future__ import annotations

from django.conf import settings
from django.db import models


def proof_image_path(instance: "Proof", filename: str) -> str:
    task_id = getattr(instance, "task_id", None)
    student_id = instance.task.objective.student_id if task_id else "unknown"
    return f"proofs/{student_id}/task_{task_id or 'unknown'}/{filename}"


class Proof(models.Model):
    """Evidence submitted by student after task progress/completion."""

    STATUS_PENDING = "pending"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [(STATUS_PENDING, "Pending"), (STATUS_DONE, "Done"), (STATUS_FAILED, "Failed")]

    task = models.ForeignKey("core.Task", on_delete=models.CASCADE, related_name="proofs")
    image = models.ImageField(upload_to=proof_image_path)
    explanation_text = models.TextField()
    ai_analysis = models.JSONField(default=dict, blank=True)
    analysis_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Proof<{self.task_id}>"


class ProgrammingQuestion(models.Model):
    """Generated question when mismatch/issue is detected."""

    SEVERITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High")]
    proof = models.ForeignKey(Proof, on_delete=models.CASCADE, related_name="programming_questions")
    title = models.CharField(max_length=255)
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="medium")
    suggested_fixes = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TodoItem(models.Model):
    """Checklist item generated from suggested fixes."""

    PRIORITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High")]
    programming_question = models.ForeignKey(
        ProgrammingQuestion, on_delete=models.CASCADE, related_name="todo_items"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium")
    done = models.BooleanField(default=False)


class Challenge(models.Model):
    """Daily adaptive challenge micro-task."""

    DIFFICULTY_CHOICES = [("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard"), ("beginner", "Beginner"), ("intermediate", "Intermediate"), ("advanced", "Advanced")]
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="challenges")
    text = models.TextField()
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default="easy")
    scheduled_date = models.DateField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
