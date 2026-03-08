"""Admin registration for AI models."""
from django.contrib import admin

from ai.models import AIEventLog, AIModelWeight, InterviewConversation, InterviewMessage


@admin.register(InterviewConversation)
class InterviewConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "status", "updated_at")


@admin.register(InterviewMessage)
class InterviewMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "role", "created_at")


@admin.register(AIEventLog)
class AIEventLogAdmin(admin.ModelAdmin):
    list_display = ("id", "event_type", "user", "created_at")


@admin.register(AIModelWeight)
class AIModelWeightAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "capability", "provider", "is_active", "weight_path")
    list_filter = ("capability", "provider", "is_active")
    search_fields = ("name", "weight_path")
