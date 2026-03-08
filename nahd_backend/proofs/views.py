"""Proof endpoints and challenge listing."""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStudent
from ai.tasks import analyze_proof_task
from proofs.models import Challenge, Proof
from proofs.serializers import ChallengeSerializer, CompleteSessionSerializer, ProofSerializer
from proofs.services import run_proof_analysis
from scheduling.models import Session


class SessionCompleteView(APIView):
    """Mark session complete, upload proof, and trigger analysis."""

    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request, id: int, *args, **kwargs) -> Response:
        session = get_object_or_404(Session, id=id, student=request.user)
        serializer = CompleteSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session.status = Session.STATUS_COMPLETED
        session.save(update_fields=["status"])
        proof = Proof.objects.create(
            session=session,
            image=serializer.validated_data["image"],
            explanation_text=serializer.validated_data["explanation"],
        )
        # Keep analysis deterministic for local/demo usage, while exposing a Celery task for production.
        run_proof_analysis(proof)
        delay_fn = getattr(analyze_proof_task, "delay", None)
        if callable(delay_fn):
            try:
                delay_fn(proof.id)
            except Exception:
                pass
        return Response(ProofSerializer(proof).data, status=status.HTTP_201_CREATED)


class ProofAnalysisView(APIView):
    """Get proof analysis and generated questions/todo items."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id: int, *args, **kwargs) -> Response:
        proof = get_object_or_404(Proof, id=id, session__student=request.user)
        return Response(ProofSerializer(proof).data)


class ChallengeListView(APIView):
    """List upcoming adaptive challenges."""

    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get(self, request, *args, **kwargs) -> Response:
        challenges = Challenge.objects.filter(student=request.user).order_by("scheduled_date", "-id")
        return Response(ChallengeSerializer(challenges, many=True).data)
