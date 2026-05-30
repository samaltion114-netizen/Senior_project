"""Serializers for accounts app."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
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
    expertise_level = serializers.ChoiceField(choices=["junior", "certified", "senior"], required=False, default="junior")
    subscription_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=Decimal("0.01"))
    max_students = serializers.IntegerField(required=False, min_value=1, default=1)
    availability_schedule = serializers.JSONField(required=False, default=dict)

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
            "expertise_level",
            "subscription_price",
            "max_students",
            "availability_schedule",
        )

    def create(self, validated_data: dict[str, Any]) -> User:
        role = validated_data.pop("role")
        major = validated_data.pop("major", "")
        current_status = validated_data.pop("current_status", "")
        goal_text = validated_data.pop("goal_text", "")
        timezone = validated_data.pop("timezone", "UTC")
        expertise_tags = validated_data.pop("expertise_tags", [])
        bio = validated_data.pop("bio", "")
        expertise_level = validated_data.pop("expertise_level", "junior")
        subscription_price = validated_data.pop("subscription_price", None)
        max_students = validated_data.pop("max_students", 1)
        availability_schedule = validated_data.pop("availability_schedule", {})
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
            ExpertProfile.objects.create(
                user=user,
                expertise_tags=expertise_tags,
                bio=bio,
                expertise_level=expertise_level,
                subscription_price=subscription_price or 1,
                max_students=max_students,
                availability_schedule=availability_schedule,
            )
        return user


class UserSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="username", read_only=True)
    user_profile = serializers.SerializerMethodField()

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
            "user_profile",
        )

    def get_user_profile(self, obj: User) -> dict[str, Any]:
        profile: dict[str, Any] = {
            "id": obj.id,
            "email": obj.email,
            "first_name": obj.first_name,
            "last_name": obj.last_name,
            "user_name": obj.username,
            "role": "expert" if obj.is_expert else "student" if obj.is_student else "user",
        }
        if obj.is_student and hasattr(obj, "student_profile"):
            profile.update(
                {
                    "major": obj.student_profile.major,
                    "current_status": obj.student_profile.current_status,
                    "goal_text": obj.student_profile.goal_text,
                    "total_xp": obj.total_xp,
                    "streaks": obj.current_streak,
                }
            )
        if obj.is_expert and hasattr(obj, "expert_profile"):
            profile.update(
                {
                    "expertise_level": obj.expert_profile.expertise_level,
                    "subscription_price": obj.expert_profile.subscription_price,
                    "max_students": obj.expert_profile.max_students,
                    "bio": obj.expert_profile.bio,
                    "expertise_tags": obj.expert_profile.expertise_tags,
                    "availability_schedule": obj.expert_profile.availability_schedule,
                    "is_accepting_new_students": obj.expert_profile.is_accepting_new_students,
                    "wallet_balance": obj.expert_profile.wallet_balance,
                    "average_rating": obj.expert_profile.average_rating,
                }
            )
        return profile


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
    average_rating = serializers.SerializerMethodField()
    current_active_slots = serializers.SerializerMethodField()
    is_accepting_new_students = serializers.SerializerMethodField()

    class Meta:
        model = ExpertProfile
        fields = (
            "id",
            "user_id",
            "user_name",
            "email",
            "expertise_level",
            "subscription_price",
            "max_students",
            "expertise_tags",
            "availability_schedule",
            "is_accepting_new_students",
            "bio",
            "wallet_balance",
            "average_rating",
            "current_active_slots",
        )

    def get_average_rating(self, obj: ExpertProfile) -> float:
        return round(float(obj.average_rating or 0), 2)

    def get_current_active_slots(self, obj: ExpertProfile) -> int:
        # Calculate current active slots from assignments
        return ExpertAssignment.objects.filter(
            expert=obj.user,
            status__in=["active", "awaiting_payment"]
        ).count()

    def get_is_accepting_new_students(self, obj: ExpertProfile) -> bool:
        # Check if expert is accepting new students based on current slots
        active_slots = self.get_current_active_slots(obj)
        return obj.max_students > active_slots


class ExpertMeSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    average_rating = serializers.SerializerMethodField()

    class Meta:
        model = ExpertProfile
        fields = (
            "id",
            "user_name",
            "email",
            "expertise_level",
            "subscription_price",
            "max_students",
            "expertise_tags",
            "availability_schedule",
            "bio",
            "is_accepting_new_students",
            "wallet_balance",
            "average_rating",
            "hourly_rate",
        )
        read_only_fields = ("wallet_balance", "average_rating")

    def get_average_rating(self, obj: ExpertProfile) -> float:
        return round(float(obj.average_rating or 0), 2)


class ExpertRatingSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    feedback = serializers.CharField(required=False, allow_blank=True, default="")


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
    amount = serializers.IntegerField(min_value=1, required=False)
    currency = serializers.CharField(max_length=10, default="usd")
    expert_id = serializers.IntegerField(required=False)
    assignment_id = serializers.IntegerField(required=False)


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
    student_name = serializers.CharField(source="user.username", read_only=True)
    amount = serializers.SerializerMethodField()
    payment_date = serializers.DateTimeField(source="created_at", read_only=True)
    subscription_ends_at = serializers.SerializerMethodField()
    chat_thread_id = serializers.SerializerMethodField()

    class Meta:
        model = PaymentRecord
        fields = (
            "id",
            "user",
            "student_name",
            "expert",
            "expert_name",
            "provider",
            "amount",
            "currency",
            "payment_intent_id",
            "client_secret",
            "status",
            "metadata",
            "payment_date",
            "subscription_ends_at",
            "chat_thread_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("user", "provider", "payment_intent_id", "client_secret", "status", "created_at", "updated_at")

    def get_amount(self, obj: PaymentRecord) -> float:
        return round(float(obj.amount) / 100.0, 2)

    def get_subscription_ends_at(self, obj: PaymentRecord):
        return obj.created_at + timedelta(days=30)

    def get_chat_thread_id(self, obj: PaymentRecord) -> int | None:
        assignment_id = obj.metadata.get("assignment_id") if isinstance(obj.metadata, dict) else None
        if not assignment_id:
            return None
        thread = ChatThread.objects.filter(assignment_id=assignment_id).only("id").first()
        return thread.id if thread else None


class StripeWebhookSerializer(serializers.Serializer):
    payment_intent_id = serializers.CharField(max_length=255)
    status = serializers.ChoiceField(choices=["succeeded", "failed"])
    metadata = serializers.JSONField(required=False, default=dict)
