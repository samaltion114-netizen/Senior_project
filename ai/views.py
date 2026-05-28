"""Views implementing AI feature APIs."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction
from django.http import FileResponse
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.models import AIEventLog, AIModelWeight, InterviewConversation, InterviewMessage
from ai.serializers import (
    DailyChallengeRequestSerializer,
    InterviewMessageSerializer,
    MindmapGenerateRequestSerializer,
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


class ExpertSystemProxyView(APIView):
    """Proxy requests to the external expert-system service."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs) -> Response:
        payload = request.data if isinstance(request.data, dict) else dict(request.data)
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-User-ID": str(request.user.id),
            "X-User-Name": request.user.username,
            "X-User-Email": request.user.email,
        }
        proxy_request = Request(settings.AI_EXPERT_SYSTEM_URL, data=body, headers=headers, method="POST")
        try:
            with urlopen(proxy_request, timeout=settings.AI_LOCAL_INFERENCE_TIMEOUT) as response:
                response_body = response.read().decode("utf-8")
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    return Response(json.loads(response_body), status=response.status)
                return Response({"response": response_body}, status=response.status)
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8") if exc.fp else ""
            try:
                error_json = json.loads(error_body) if error_body else {"detail": str(exc)}
            except json.JSONDecodeError:
                error_json = {"detail": error_body or str(exc)}
            return Response(error_json, status=exc.code)
        except URLError as exc:
            return Response({"detail": f"Expert system unavailable: {exc.reason}"}, status=status.HTTP_502_BAD_GATEWAY)


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


class MindmapSvgView(APIView):
    """Serve the integrated AI mindmap SVG."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs) -> Response:
        svg_path = Path(settings.AI_MINDMAP_SVG_PATH)
        if not svg_path.exists():
            return Response({"detail": "Mindmap SVG not found. Run import_najem_assets."}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(svg_path.open("rb"), content_type="image/svg+xml")


class MindmapGenerateView(APIView):
    """Generate mindmap JSON from topic/context using selected AI model."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(request=MindmapGenerateRequestSerializer, responses={200: dict})
    def post(self, request, *args, **kwargs) -> Response:
        serializer = MindmapGenerateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        service = get_ai_service(capability=AIModelWeight.CAPABILITY_ALL)
        result = service.generate_mindmap(
            topic=payload["topic"],
            context=payload.get("context", ""),
            max_branches=payload["max_branches"],
        )
        AIEventLog.objects.create(
            user=request.user,
            event_type="mindmap_generate",
            prompt=f"{payload['topic']}\n{payload.get('context', '')}",
            response=str(result),
            prompt_hash=hash_text(f"{payload['topic']}\n{payload.get('context', '')}"),
            response_hash=hash_text(str(result)),
            embeddings_metadata={"max_branches": payload["max_branches"]},
        )
        return Response(result)
