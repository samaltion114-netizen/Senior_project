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
    is_trainer = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)

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
