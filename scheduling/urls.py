"""URLs for scheduling app."""
from django.urls import path

from scheduling.views import ScheduleOptimizeView, ScheduleSessionsView

urlpatterns = [
    path("schedule/optimize/", ScheduleOptimizeView.as_view(), name="schedule-optimize"),
    path("schedule/sessions/", ScheduleSessionsView.as_view(), name="schedule-sessions"),
]
