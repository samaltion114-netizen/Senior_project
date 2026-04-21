"""Accounts and profile models."""
from __future__ import annotations

import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


def default_verification_expiry():
    return timezone.now() + timedelta(hours=24)


def default_password_reset_expiry():
    return timezone.now() + timedelta(hours=2)


class User(AbstractUser):
    """Custom user with explicit Nahd role flags."""

    is_student = models.BooleanField(default=False)
    is_expert = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    total_xp = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    highest_streak = models.PositiveIntegerField(default=0)
    fcm_token = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.username


class StudentProfile(models.Model):
    """Extended student profile for planning and adaptation."""

    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="student_profile")
    major = models.CharField(max_length=120, blank=True)
    current_status = models.CharField(max_length=120, blank=True)
    goal_text = models.TextField(blank=True)
    weekly_availability = models.JSONField(default=dict, blank=True)
    timezone = models.CharField(max_length=64, default="UTC")

    def __str__(self) -> str:
        return f"StudentProfile<{self.user.username}>"


class ExpertProfile(models.Model):
    """Extended expert profile used for interviews and recommendations."""

    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="expert_profile")
    expertise_tags = models.JSONField(default=list, blank=True)
    bio = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"ExpertProfile<{self.user.username}>"


class UserActivityLog(models.Model):
    """Tracks user actions relevant to streaks, XP, and analytics."""

    EVENT_TASK_COMPLETED = "task_completed"
    EVENT_ASSIGNMENT_REQUESTED = "assignment_requested"
    EVENT_ASSIGNMENT_ACCEPTED = "assignment_accepted"
    EVENT_CHOICES = [
        (EVENT_TASK_COMPLETED, "Task Completed"),
        (EVENT_ASSIGNMENT_REQUESTED, "Assignment Requested"),
        (EVENT_ASSIGNMENT_ACCEPTED, "Assignment Accepted"),
    ]

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="activity_logs")
    event_type = models.CharField(max_length=40, choices=EVENT_CHOICES)
    related_id = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class Badge(models.Model):
    """Badge definition used by the gamification system."""

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    image_url = models.URLField(blank=True)
    condition = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class UserBadge(models.Model):
    """Badge awarded to a user."""

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="user_badges")
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="awards")
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "badge")
        ordering = ("-awarded_at",)


class ExpertAssignment(models.Model):
    """Request-based relationship between a student and an expert."""

    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_REJECTED = "rejected"
    STATUS_EXPIRED = "expired"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_EXPIRED, "Expired"),
    ]

    student = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="sent_assignments")
    expert = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="received_assignments")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    request_message = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)


class Notification(models.Model):
    """Student/expert notification with deep-link metadata."""

    TYPE_ASSIGNMENT_REQUEST = "assignment_request"
    TYPE_ASSIGNMENT_ACCEPTED = "assignment_accepted"
    TYPE_ASSIGNMENT_REJECTED = "assignment_rejected"
    TYPE_AI_ANALYSIS = "ai_analysis"
    TYPE_TASK_DECOMPOSED = "task_decomposed"
    TYPE_STREAK = "streak"
    TYPE_GAMIFICATION = "gamification"
    TYPE_INACTIVITY = "inactivity"
    TYPE_SESSION_REMINDER = "session_reminder"
    TYPE_ASSIGNMENT_EXPIRY = "assignment_expiry"
    TYPE_CHAT_MESSAGE = "chat_message"
    TYPE_CHOICES = [
        (TYPE_ASSIGNMENT_REQUEST, "Assignment Request"),
        (TYPE_ASSIGNMENT_ACCEPTED, "Assignment Accepted"),
        (TYPE_ASSIGNMENT_REJECTED, "Assignment Rejected"),
        (TYPE_AI_ANALYSIS, "AI Analysis"),
        (TYPE_TASK_DECOMPOSED, "Task Decomposed"),
        (TYPE_STREAK, "Streak"),
        (TYPE_GAMIFICATION, "Gamification"),
        (TYPE_INACTIVITY, "Inactivity"),
        (TYPE_SESSION_REMINDER, "Session Reminder"),
        (TYPE_ASSIGNMENT_EXPIRY, "Assignment Expiry"),
        (TYPE_CHAT_MESSAGE, "Chat Message"),
    ]

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=40, choices=TYPE_CHOICES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    related_id = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class ChatThread(models.Model):
    """One direct chat thread bound to an active expert assignment."""

    assignment = models.OneToOneField("accounts.ExpertAssignment", on_delete=models.CASCADE, related_name="chat_thread")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)


class ChatMessage(models.Model):
    """Message exchanged inside a mentorship thread."""

    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="sent_chat_messages")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "id")


class PaymentRecord(models.Model):
    """Tracks payment intents and webhook-confirmed outcomes."""

    STATUS_PENDING = "pending"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
    ]

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="payments")
    expert = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="expert_payments")
    provider = models.CharField(max_length=30, default="mock")
    amount = models.PositiveIntegerField()
    currency = models.CharField(max_length=10, default="usd")
    payment_intent_id = models.CharField(max_length=255, unique=True)
    client_secret = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)


class EmailVerificationToken(models.Model):
    """Email verification token with expiration and one-time usage."""

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="email_verification_tokens")
    token = models.CharField(max_length=128, unique=True, default=secrets.token_urlsafe)
    expires_at = models.DateTimeField(default=default_verification_expiry)
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class PasswordResetToken(models.Model):
    """Password reset token with expiration and one-time usage."""

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="password_reset_tokens")
    token = models.CharField(max_length=128, unique=True, default=secrets.token_urlsafe)
    expires_at = models.DateTimeField(default=default_password_reset_expiry)
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
