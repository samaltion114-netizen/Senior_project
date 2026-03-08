"""Admin for scheduling app."""
from django.contrib import admin

from scheduling.models import Session


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "task", "scheduled_start", "scheduled_end", "status")
    list_filter = ("status",)
