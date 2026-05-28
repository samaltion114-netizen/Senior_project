"""Admin registrations for accounts app."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import (
    Badge,
    ChatMessage,
    ChatThread,
    EmailVerificationToken,
    ExpertAssignment,
    ExpertProfile,
    ExpertRating,
    Notification,
    PasswordResetToken,
    PaymentRecord,
    StudentProfile,
    User,
    UserActivityLog,
    UserBadge,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "is_email_verified", "is_student", "is_expert", "is_staff")
    fieldsets = UserAdmin.fieldsets + (
        ("Nahd Roles", {"fields": ("is_student", "is_expert", "total_xp", "current_streak", "highest_streak", "fcm_token")}),
    )


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "major", "current_status", "timezone")


@admin.register(ExpertProfile)
class ExpertProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "expertise_level", "average_rating", "is_accepting_new_students")


@admin.register(ExpertRating)
class ExpertRatingAdmin(admin.ModelAdmin):
    list_display = ("student", "expert", "rating", "created_at")
    list_filter = ("rating",)


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "expires_at", "used", "created_at")
    readonly_fields = ("token", "created_at")


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "expires_at", "used", "created_at")
    readonly_fields = ("token", "created_at")


@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ("user", "event_type", "related_id", "created_at")


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "condition")


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ("user", "badge", "awarded_at")


@admin.register(ExpertAssignment)
class ExpertAssignmentAdmin(admin.ModelAdmin):
    list_display = ("student", "expert", "status", "expires_at", "created_at")
    list_filter = ("status",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "title", "is_read", "created_at")
    list_filter = ("type", "is_read")


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ("assignment", "created_at", "updated_at")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("thread", "sender", "created_at")


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "expert", "provider", "amount", "currency", "status", "created_at")
    list_filter = ("provider", "status")
