"""URLs for proofs app."""
from django.urls import path

from proofs.views import ChallengeListView, ProofAnalysisView, SessionCompleteView

urlpatterns = [
    path("sessions/<int:id>/complete/", SessionCompleteView.as_view(), name="session-complete"),
    path("proofs/<int:id>/analysis/", ProofAnalysisView.as_view(), name="proof-analysis"),
    path("challenges/", ChallengeListView.as_view(), name="challenges"),
]
