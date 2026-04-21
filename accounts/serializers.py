"""Serializers for accounts app."""
from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.models import (
    Badge,
    ChatMessage,
    ChatThread,
    EmailVerificationToken,
    ExpertAssignment,
    ExpertProfile,
    Notification,
    PasswordResetToken,
    PaymentRecord,
    StudentProfile,
    UserBadge,
)

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    """Register a new user as student or expert."""

    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=["student", "expert"])
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
    user_name = serializers.CharField(source="username", read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "user_name",
            "email",
            "is_student",
            "is_expert",
            "is_email_verified",
            "total_xp",
            "current_streak",
            "highest_streak",
        )


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """JWT serializer that authenticates primarily by email."""

    email = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True)
    username = serializers.CharField(required=False)

    @classmethod
    def get_token(cls, user: User):
        token = super().get_token(user)
        token["user_name"] = user.username
        token["email"] = user.email
        return token

    def validate(self, attrs):
        email = attrs.get("email")
        username = attrs.get("username")
        password = attrs.get("password")
        if not password:
            raise serializers.ValidationError({"password": "This field is required."})
        if email:
            user = User.objects.filter(email__iexact=email).first()
            if user is None:
                raise serializers.ValidationError({"email": "No user found with this email."})
            username = user.username
        if not username:
            raise serializers.ValidationError({"email": "Email is required."})
        data = super().validate({self.username_field: username, "password": password})
        data["user"] = UserSerializer(self.user).data
        data["user_name"] = self.user.username
        return data


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


class FCMTokenUpdateSerializer(serializers.Serializer):
    fcm_token = serializers.CharField(max_length=4096)


class ExpertListSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    user_name = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = ExpertProfile
        fields = ("id", "user_id", "user_name", "email", "expertise_tags", "bio")


class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ("id", "name", "slug", "image_url", "condition")


class UserBadgeSerializer(serializers.ModelSerializer):
    badge = BadgeSerializer(read_only=True)

    class Meta:
        model = UserBadge
        fields = ("id", "badge", "awarded_at")


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ("id", "type", "title", "message", "related_id", "metadata", "is_read", "created_at")


class AssignmentRequestSerializer(serializers.Serializer):
    expert_id = serializers.IntegerField()
    request_message = serializers.CharField(required=False, allow_blank=True)


class AssignmentActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)


class ExpertAssignmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.username", read_only=True)
    expert_name = serializers.CharField(source="expert.username", read_only=True)

    class Meta:
        model = ExpertAssignment
        fields = (
            "id",
            "student",
            "student_name",
            "expert",
            "expert_name",
            "status",
            "request_message",
            "rejection_reason",
            "expires_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("student", "expert", "status", "rejection_reason", "expires_at", "created_at", "updated_at")


class PaymentIntentRequestSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    currency = serializers.CharField(max_length=10, default="usd")
    expert_id = serializers.IntegerField(required=False)


class ChatMessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=4000)


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.username", read_only=True)

    class Meta:
        model = ChatMessage
        fields = ("id", "thread", "sender", "sender_name", "body", "created_at")
        read_only_fields = ("thread", "sender", "created_at")


class ChatThreadSerializer(serializers.ModelSerializer):
    assignment = ExpertAssignmentSerializer(read_only=True)
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = ChatThread
        fields = ("id", "assignment", "messages", "created_at", "updated_at")


class PaymentRecordSerializer(serializers.ModelSerializer):
    expert_name = serializers.CharField(source="expert.username", read_only=True)

    class Meta:
        model = PaymentRecord
        fields = (
            "id",
            "user",
            "expert",
            "expert_name",
            "provider",
            "amount",
            "currency",
            "payment_intent_id",
            "client_secret",
            "status",
            "metadata",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("user", "provider", "payment_intent_id", "client_secret", "status", "created_at", "updated_at")


class StripeWebhookSerializer(serializers.Serializer):
    payment_intent_id = serializers.CharField(max_length=255)
    status = serializers.ChoiceField(choices=["succeeded", "failed"])
    metadata = serializers.JSONField(required=False, default=dict)
