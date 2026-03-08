"""URLs for scheduling app."""
from django.urls import path

from scheduling.views import ScheduleOptimizeView

urlpatterns = [
    path("schedule/optimize/", ScheduleOptimizeView.as_view(), name="schedule-optimize"),
]
