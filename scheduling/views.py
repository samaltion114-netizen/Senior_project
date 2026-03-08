"""Scheduling views."""
from __future__ import annotations

from datetime import date

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStudent
from ai.models import AIModelWeight
from ai.services import get_ai_service
from core.models import Objective
from scheduling.models import Session
from scheduling.serializers import SessionSerializer, WeeklyAvailabilitySerializer


class ScheduleOptimizeView(APIView):
    """Generate optimized sessions from availability and tasks."""

    permission_classes = [permissions.IsAuthenticated, IsStudent]

    @extend_schema(request=WeeklyAvailabilitySerializer, responses={201: dict})
    def post(self, request, *args, **kwargs) -> Response:
        serializer = WeeklyAvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        objective = get_object_or_404(Objective, id=payload["objective_id"], student=request.user)
        profile = getattr(request.user, "student_profile", None)
        if profile is not None:
            profile.weekly_availability = payload["weekly_availability"]
            profile.save(update_fields=["weekly_availability"])

        task_blocks = []
        for task in objective.tasks.all():
            minutes = task.estimated_minutes
            block_size = 30
            full_blocks = minutes // block_size
            rem = minutes % block_size
            for _ in range(full_blocks):
                task_blocks.append({"task_id": task.id, "duration_minutes": block_size})
            if rem:
                task_blocks.append({"task_id": task.id, "duration_minutes": rem})
            if not full_blocks and not rem:
                task_blocks.append({"task_id": task.id, "duration_minutes": 20})

        existing_sessions = [
            {"scheduled_start": s.scheduled_start.isoformat(), "scheduled_end": s.scheduled_end.isoformat()}
            for s in Session.objects.filter(student=request.user)
        ]
        service = get_ai_service(capability=AIModelWeight.CAPABILITY_SCHEDULING)
        planned = service.optimize_schedule(
            {
                "weekly_availability": payload["weekly_availability"],
                "task_blocks": task_blocks,
                "max_daily_minutes": payload["max_daily_minutes"],
                "break_minutes": payload["break_minutes"],
                "start_date": str(payload.get("start_date") or date.today()),
                "existing_sessions": existing_sessions,
            }
        )

        created = []
        for row in planned:
            session = Session.objects.create(
                student=request.user,
                task_id=row["task_id"],
                scheduled_start=row["scheduled_start"],
                scheduled_end=row["scheduled_end"],
                status=row["status"],
                duration_minutes=row["duration_minutes"],
            )
            created.append(session)
        return Response({"sessions": SessionSerializer(created, many=True).data}, status=status.HTTP_201_CREATED)
