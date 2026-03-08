"""Admin for trainer reviews."""
from django.contrib import admin

from reviews.models import AdminReview


@admin.register(AdminReview)
class AdminReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "proof", "reviewer", "is_bug_confirmed", "created_at")
