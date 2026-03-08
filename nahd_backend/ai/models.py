"""AI-related persistence models."""
from __future__ import annotations

from django.conf import settings
from django.db import models


class InterviewConversation(models.Model):
    """Tracks a student's interview session with the AI expert system."""

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interviews")
    status = models.CharField(max_length=20, default="active")
    facts = models.JSONField(default=dict, blank=True)
    suggested_objective = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class InterviewMessage(models.Model):
    """Stores interview message exchange for auditing and context."""

    conversation = models.ForeignKey(InterviewConversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20)  # user, assistant
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)


class AIEventLog(models.Model):
    """Stores AI prompts, responses, and metadata hashes for auditing."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    event_type = models.CharField(max_length=64)
    prompt = models.TextField(blank=True)
    response = models.TextField(blank=True)
    prompt_hash = models.CharField(max_length=128, blank=True)
    response_hash = models.CharField(max_length=128, blank=True)
    embeddings_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class AIModelWeight(models.Model):
    """Model weight registry with per-capability activation."""

    CAPABILITY_ALL = "all"
    CAPABILITY_INTERVIEW = "interview"
    CAPABILITY_TAGGING = "tagging"
    CAPABILITY_TIME = "time_estimation"
    CAPABILITY_SCHEDULING = "scheduling"
    CAPABILITY_PROOF = "proof_analysis"
    CAPABILITY_CHALLENGE = "challenge_generation"
    CAPABILITY_CHOICES = [
        (CAPABILITY_ALL, "All"),
        (CAPABILITY_INTERVIEW, "Interview"),
        (CAPABILITY_TAGGING, "Tagging"),
        (CAPABILITY_TIME, "Time Estimation"),
        (CAPABILITY_SCHEDULING, "Scheduling"),
        (CAPABILITY_PROOF, "Proof Analysis"),
        (CAPABILITY_CHALLENGE, "Challenge Generation"),
    ]

    PROVIDER_LOCAL = "local"
    PROVIDER_OPENAI = "openai"
    PROVIDER_MOCK = "mock"
    PROVIDER_CHOICES = [
        (PROVIDER_LOCAL, "Local"),
        (PROVIDER_OPENAI, "OpenAI"),
        (PROVIDER_MOCK, "Mock"),
    ]

    name = models.CharField(max_length=120)
    capability = models.CharField(max_length=32, choices=CAPABILITY_CHOICES, default=CAPABILITY_ALL)
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default=PROVIDER_LOCAL)
    weight_path = models.CharField(max_length=500)
    is_active = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("name", "capability")
        ordering = ("capability", "name")

    def __str__(self) -> str:
        return f"{self.capability}:{self.name}"
