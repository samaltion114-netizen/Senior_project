"""URLs for AI app."""
from django.urls import path

from ai.views import (
    DailyChallengeGenerateView,
    InterviewMessageView,
    InterviewStartView,
    ModelWeightListView,
    ModelWeightSelectView,
    TaggingChecklistView,
    TimeEstimateView,
)

urlpatterns = [
    path("interview/start/", InterviewStartView.as_view(), name="interview-start"),
    path("interview/message/", InterviewMessageView.as_view(), name="interview-message"),
    path("ai/tagging/informatics/", TaggingChecklistView.as_view(), {"domain": "informatics"}, name="tagging-it"),
    path("ai/tagging/legal/", TaggingChecklistView.as_view(), {"domain": "law"}, name="tagging-law"),
    path("ai/challenges/generate/", DailyChallengeGenerateView.as_view(), name="daily-challenges-generate"),
    path("ai/time-estimate/", TimeEstimateView.as_view(), name="time-estimate"),
    path("ai/models/weights/", ModelWeightListView.as_view(), name="model-weights"),
    path("ai/models/select/", ModelWeightSelectView.as_view(), name="model-select"),
]
