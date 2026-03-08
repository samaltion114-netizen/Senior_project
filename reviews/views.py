"""Trainer review endpoints."""
from __future__ import annotations

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsTrainer
from proofs.models import ProgrammingQuestion
from reviews.serializers import AdminReviewSerializer


class AdminReviewCreateView(APIView):
    """Create trainer review and optionally escalate issue severity."""

    permission_classes = [permissions.IsAuthenticated, IsTrainer]

    def post(self, request, *args, **kwargs) -> Response:
        serializer = AdminReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = serializer.save(reviewer=request.user)
        if review.is_bug_confirmed:
            ProgrammingQuestion.objects.filter(proof=review.proof).update(severity="high")
        return Response(AdminReviewSerializer(review).data, status=status.HTTP_201_CREATED)
