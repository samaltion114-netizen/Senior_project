"""Admin for proof lifecycle models."""
from django.contrib import admin

from proofs.models import Challenge, ProgrammingQuestion, Proof, TodoItem


@admin.register(Proof)
class ProofAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "analysis_status", "created_at")


@admin.register(ProgrammingQuestion)
class ProgrammingQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "proof", "title", "severity")


@admin.register(TodoItem)
class TodoItemAdmin(admin.ModelAdmin):
    list_display = ("id", "programming_question", "title", "priority", "done")


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "difficulty", "scheduled_date", "completed")
