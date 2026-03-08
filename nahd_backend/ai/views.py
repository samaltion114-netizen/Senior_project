"""Views implementing AI feature APIs."""
from __future__ import annotations

from datetime import date

from django.conf import settings
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.models import AIEventLog, AIModelWeight, InterviewConversation, InterviewMessage
from ai.serializers import (
    DailyChallengeRequestSerializer,
    InterviewMessageSerializer,
    ModelWeightSelectSerializer,
    TaggingChecklistSerializer,
    TimeEstimateRequestSerializer,
)
from ai.services import get_ai_service, hash_text, list_weight_files, sanitize_text
from ai.throttles import InterviewThrottle
from proofs.models import Challenge


class InterviewStartView(APIView):
    """Start interview conversation."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [InterviewThrottle]

    @extend_schema(request=None, responses={201: dict})
    def post(self, request, *args, **kwargs) -> Response:
        convo = InterviewConversation.objects.create(student=request.user)
        return Response({"conversation_id": convo.id, "status": convo.status}, status=status.HTTP_201_CREATED)


class InterviewMessageView(APIView):
    """Send interview message and get AI expert-system response."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [InterviewThrottle]

    @transaction.atomic
    @extend_schema(request=InterviewMessageSerializer, responses={200: dict})
    def post(self, request, *args, **kwargs) -> Response:
        serializer = InterviewMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = InterviewConversation.objects.select_for_update().get(
            id=serializer.validated_data["conversation_id"], student=request.user
        )
        message = sanitize_text(serializer.validated_data["message"])
        InterviewMessage.objects.create(conversation=conversation, role="user", content=message)
        history = [{"role": m.role, "content": m.content} for m in conversation.messages.all()]
        service = get_ai_service(capability=AIModelWeight.CAPABILITY_INTERVIEW)
        result = service.process_message(history=history, message=message)
        InterviewMessage.objects.create(conversation=conversation, role="assistant", content=result["reply"])
        conversation.facts = {**conversation.facts, **result.get("facts", {})}
        if result.get("suggested_objective"):
            conversation.suggested_objective = result["suggested_objective"]
            conversation.status = "completed"
        conversation.save(update_fields=["facts", "suggested_objective", "status", "updated_at"])

        AIEventLog.objects.create(
            user=request.user,
            event_type="interview_message",
            prompt=message,
            response=result["reply"],
            prompt_hash=hash_text(message),
            response_hash=hash_text(result["reply"]),
            embeddings_metadata={"conversation_id": conversation.id},
        )
        return Response(
            {
                "reply": result["reply"],
                "completed": result["completed"],
                "recommended_objective": result.get("suggested_objective"),
            }
        )


class TaggingChecklistView(APIView):
    """Generate tags + checklist (informatics/legal)."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=TaggingChecklistSerializer, responses={200: dict})
    def post(self, request, *args, **kwargs) -> Response:
        serializer = TaggingChecklistSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        text = serializer.validated_data["text"]
        domain = kwargs.get("domain") or serializer.validated_data.get("domain", "informatics")
        service = get_ai_service(capability=AIModelWeight.CAPABILITY_TAGGING)
        result = service.generate_tagged_checklist(text=text, domain=domain)
        legal_disclaimer = (
            "Educational use only; this is not legal advice." if domain == "law" else "Educational guidance only."
        )
        return Response({**result, "disclaimer": legal_disclaimer})


class DailyChallengeGenerateView(APIView):
    """Generate and persist daily micro challenges."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=DailyChallengeRequestSerializer, responses={200: dict})
    def post(self, request, *args, **kwargs) -> Response:
        serializer = DailyChallengeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        service = get_ai_service(capability=AIModelWeight.CAPABILITY_CHALLENGE)
        generated = service.generate_daily_challenges(
            domain=data["domain"], level=data["level"], minutes=data["minutes"]
        )
        saved = []
        scheduled = request.query_params.get("date")
        try:
            scheduled_date = date.fromisoformat(scheduled) if scheduled else None
        except ValueError:
            scheduled_date = None
        for row in generated[:3]:
            challenge = Challenge.objects.create(
                student=request.user,
                text=f"{row['title']}: {row['requirements']}",
                difficulty=data["level"],
                scheduled_date=scheduled_date,
            )
            saved.append({"id": challenge.id, "text": challenge.text, "difficulty": challenge.difficulty})
        return Response({"challenges": saved})


class TimeEstimateView(APIView):
    """Standalone time estimation endpoint."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=TimeEstimateRequestSerializer, responses={200: dict})
    def post(self, request, *args, **kwargs) -> Response:
        serializer = TimeEstimateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = get_ai_service(capability=AIModelWeight.CAPABILITY_TIME)
        result = service.estimate_time(serializer.validated_data)
        return Response(result)


class ModelWeightListView(APIView):
    """List discovered model files and current active model selections."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        files = list_weight_files()
        active = [
            {
                "capability": row.capability,
                "provider": row.provider,
                "model_name": row.name,
                "weight_path": row.weight_path,
                "updated_at": row.updated_at,
            }
            for row in AIModelWeight.objects.filter(is_active=True).order_by("capability")
        ]
        return Response({"weights_folder": str(settings.AI_WEIGHTS_DIR), "files": files, "active": active})


class ModelWeightSelectView(APIView):
    """Activate one model for a specific capability."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=ModelWeightSelectSerializer, responses={200: dict})
    def post(self, request, *args, **kwargs) -> Response:
        serializer = ModelWeightSelectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        capability = data["capability"]

        AIModelWeight.objects.filter(capability=capability).update(is_active=False)
        obj, _ = AIModelWeight.objects.update_or_create(
            name=data["model_name"],
            capability=capability,
            defaults={
                "provider": data["provider"],
                "weight_path": data["weight_path"],
                "is_active": True,
                "metadata": data.get("metadata", {}),
            },
        )
        return Response(
            {
                "message": "Model selected",
                "id": obj.id,
                "capability": obj.capability,
                "provider": obj.provider,
                "model_name": obj.name,
                "weight_path": obj.weight_path,
                "is_active": obj.is_active,
            },
            status=status.HTTP_200_OK,
        )
