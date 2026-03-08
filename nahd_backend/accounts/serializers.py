"""Serializers for accounts app."""
from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from accounts.models import EmailVerificationToken, ExpertProfile, PasswordResetToken, StudentProfile

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    """Register a new user as student, expert, or trainer."""

    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=["student", "expert", "trainer"])
    major = serializers.CharField(required=False, allow_blank=True)
    current_status = serializers.CharField(required=False, allow_blank=True)
    goal_text = serializers.CharField(required=False, allow_blank=True)
    timezone = serializers.CharField(required=False, allow_blank=True, default="UTC")
    expertise_tags = serializers.ListField(child=serializers.CharField(), required=False)
    bio = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password",
            "role",
            "major",
            "current_status",
            "goal_text",
            "timezone",
            "expertise_tags",
            "bio",
        )

    def create(self, validated_data: dict[str, Any]) -> User:
        role = validated_data.pop("role")
        major = validated_data.pop("major", "")
        current_status = validated_data.pop("current_status", "")
        goal_text = validated_data.pop("goal_text", "")
        timezone = validated_data.pop("timezone", "UTC")
        expertise_tags = validated_data.pop("expertise_tags", [])
        bio = validated_data.pop("bio", "")
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)
        user.is_student = role == "student"
        user.is_expert = role == "expert"
        user.is_trainer = role == "trainer"
        user.save()

        if user.is_student:
            StudentProfile.objects.create(
                user=user,
                major=major,
                current_status=current_status,
                goal_text=goal_text,
                timezone=timezone,
            )
        elif user.is_expert:
            ExpertProfile.objects.create(user=user, expertise_tags=expertise_tags, bio=bio)
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "is_student", "is_expert", "is_trainer", "is_email_verified")


class EmailVerificationRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EmailVerificationConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=128)

    def validate_token(self, value: str) -> str:
        token = EmailVerificationToken.objects.filter(token=value, used=False).first()
        if token is None:
            raise serializers.ValidationError("Invalid token.")
        if token.expires_at <= timezone.now():
            raise serializers.ValidationError("Token expired.")
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=128)
    new_password = serializers.CharField(min_length=8, max_length=128)

    def validate_token(self, value: str) -> str:
        token = PasswordResetToken.objects.filter(token=value, used=False).first()
        if token is None:
            raise serializers.ValidationError("Invalid token.")
        if token.expires_at <= timezone.now():
            raise serializers.ValidationError("Token expired.")
        return value
