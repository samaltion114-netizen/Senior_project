"""Non-auth account-related API routes."""
from django.urls import path

from accounts.views import (
    AssignmentRequestView,
    AssignmentListView,
    ChatMessageListCreateView,
    ChatThreadListView,
    ExpertListView,
    LeaderboardView,
    NotificationListView,
    PaymentIntentView,
    PaymentRecordListView,
    StripeWebhookView,
    TrainerAssignmentAcceptView,
    TrainerAssignmentRejectView,
    UserBadgesView,
)

urlpatterns = [
    path("experts/", ExpertListView.as_view(), name="experts"),
    path("leaderboard/", LeaderboardView.as_view(), name="leaderboard"),
    path("users/<int:id>/badges/", UserBadgesView.as_view(), name="user-badges"),
    path("notifications/", NotificationListView.as_view(), name="notifications"),
    path("assignments/", AssignmentListView.as_view(), name="assignments"),
    path("assignments/request/", AssignmentRequestView.as_view(), name="assignment-request"),
    path("trainer/assignments/<int:id>/accept/", TrainerAssignmentAcceptView.as_view(), name="trainer-assignment-accept"),
    path("trainer/assignments/<int:id>/reject/", TrainerAssignmentRejectView.as_view(), name="trainer-assignment-reject"),
    path("chat/threads/", ChatThreadListView.as_view(), name="chat-threads"),
    path("chat/threads/<int:id>/messages/", ChatMessageListCreateView.as_view(), name="chat-thread-messages"),
    path("payments/intent/", PaymentIntentView.as_view(), name="payment-intent"),
    path("payments/", PaymentRecordListView.as_view(), name="payments"),
    path("payments/webhook/", StripeWebhookView.as_view(), name="payments-webhook"),
]
