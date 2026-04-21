"""Non-auth account-related API routes."""
from django.urls import path

from accounts.views import (
    AssignmentRequestView,
    ExpertListView,
    LeaderboardView,
    NotificationListView,
    PaymentIntentView,
    TrainerAssignmentAcceptView,
    TrainerAssignmentRejectView,
    UserBadgesView,
)

urlpatterns = [
    path("experts/", ExpertListView.as_view(), name="experts"),
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    path("users/<int:id>/badges/", UserBadgesView.as_view(), name="user-badges"),
    path("notifications/", NotificationListView.as_view(), name="notifications"),
    path("assignments/request/", AssignmentRequestView.as_view(), name="assignment-request"),
    path("trainer/assignments/<int:id>/accept/", TrainerAssignmentAcceptView.as_view(), name="trainer-assignment-accept"),
    path("trainer/assignments/<int:id>/reject/", TrainerAssignmentRejectView.as_view(), name="trainer-assignment-reject"),
    path("payments/intent/", PaymentIntentView.as_view(), name="payment-intent"),
]
