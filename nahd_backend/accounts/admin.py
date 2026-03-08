"""Admin registrations for accounts app."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import EmailVerificationToken, ExpertProfile, PasswordResetToken, StudentProfile, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "is_email_verified", "is_student", "is_expert", "is_trainer", "is_staff")
    fieldsets = UserAdmin.fieldsets + (
        ("Nahd Roles", {"fields": ("is_student", "is_expert", "is_trainer")}),
    )


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "major", "current_status", "timezone")


@admin.register(ExpertProfile)
class ExpertProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "expertise_tags")


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "expires_at", "used", "created_at")
    readonly_fields = ("token", "created_at")


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "expires_at", "used", "created_at")
    readonly_fields = ("token", "created_at")
