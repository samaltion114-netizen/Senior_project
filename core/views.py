"""Views for objectives and tasks."""
from __future__ import annotations

from datetime import timedelta

from django.db import connection
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStudent
from ai.models import AIModelWeight
from ai.services import get_ai_service, text_to_embedding
from core.models import Objective, ObjectiveMilestone, PerformanceMetric, PortfolioProject, ProgressSnapshot, Task
from core.serializers import (
    CreateTaskSerializer,
    ObjectiveMilestoneSerializer,
    ObjectiveSerializer,
    PerformanceMetricSerializer,
    PortfolioAssetSerializer,
    PortfolioAssetUploadSerializer,
    PortfolioProjectSerializer,
    ProgressSnapshotSerializer,
    TaskSerializer,
)
from proofs.models import Challenge, ProgrammingQuestion
from scheduling.models import Session


class ObjectiveListCreateView(generics.ListCreateAPIView):
    """List and create objectives for current student."""

    serializer_class = ObjectiveSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_queryset(self):
        return Objective.objects.filter(student=self.request.user).order_by("-created_at")

    def perform_create(self, serializer) -> None:
        serializer.save(student=self.request.user)


class ObjectiveTaskCreateView(APIView):
    """Create task under objective and call AI time estimation."""

    permission_classes = [permissions.IsAuthenticated, IsStudent]

    @extend_schema(request=CreateTaskSerializer, responses={201: TaskSerializer})
    def post(self, request, id: int, *args, **kwargs) -> Response:
        objective = Objective.objects.get(id=id, student=request.user)
        serializer = CreateTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = get_ai_service(capability=AIModelWeight.CAPABILITY_TIME)
        estimate = service.estimate_time(serializer.validated_data)
        task = serializer.save(
            objective=objective,
            estimated_minutes=estimate["estimated_minutes"],
            estimation_confidence=estimate["confidence"],
            expected_output_embedding=text_to_embedding(serializer.validated_data.get("expected_output_text", "")),
        )
        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)


class HealthLiveView(APIView):
    """Liveness probe endpoint."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs) -> Response:
        return Response({"status": "alive"})


class HealthReadyView(APIView):
    """Readiness probe endpoint with DB check."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs) -> Response:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return Response({"status": "ready", "database": "ok"})
        except Exception as exc:
            return Response({"status": "not_ready", "database": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class DashboardProgressView(APIView):
    """Return progress dashboard summary for current student."""

    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get(self, request, *args, **kwargs) -> Response:
        student = request.user
        total_tasks = Task.objects.filter(objective__student=student).count()
        completed_tasks = (
            Session.objects.filter(student=student, status=Session.STATUS_COMPLETED).values("task_id").distinct().count()
        )
        active_tasks = max(total_tasks - completed_tasks, 0)
        progress = round((completed_tasks / total_tasks * 100.0), 2) if total_tasks else 0.0
        latest_metric = PerformanceMetric.objects.filter(student=student).first()
        skill_score = round((latest_metric.speed_score if latest_metric else progress) or 0.0, 2)
        recommendations_count = Challenge.objects.filter(student=student, completed=False).count()
        notifications_count = ProgrammingQuestion.objects.filter(proof__session__student=student).count()

        snapshot, _ = ProgressSnapshot.objects.update_or_create(
            student=student,
            snapshot_date=timezone.localdate(),
            defaults={
                "overall_progress_percent": progress,
                "skill_score": skill_score,
                "active_tasks": active_tasks,
                "completed_tasks": completed_tasks,
                "recommendations_count": recommendations_count,
                "notifications_count": notifications_count,
                "metadata": {"total_tasks": total_tasks},
            },
        )
        return Response(ProgressSnapshotSerializer(snapshot).data)


class PerformanceSummaryView(APIView):
    """Return performance analytics summary for current student."""

    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get(self, request, *args, **kwargs) -> Response:
        student = request.user
        period_end = timezone.localdate()
        period_start = period_end - timedelta(days=30)
        sessions = Session.objects.filter(student=student, created_at__date__gte=period_start, created_at__date__lte=period_end)
        avg_minutes = float(sessions.aggregate(v=Avg("duration_minutes"))["v"] or 0.0)
        total = sessions.count()
        completed = sessions.filter(status=Session.STATUS_COMPLETED).count()
        success_rate = round((completed / total) * 100.0, 2) if total else 0.0
        failure_rate = round(max(100.0 - success_rate, 0.0), 2)
        repeated = (
            ProgrammingQuestion.objects.filter(proof__session__student=student)
            .values("title")
            .annotate(c=Count("id"))
            .filter(c__gt=1)
            .count()
        )
        speed_score = round(min(100.0, (success_rate * 0.7) + (max(0.0, 100.0 - avg_minutes) * 0.3)), 2)
        metric = PerformanceMetric.objects.create(
            student=student,
            period_start=period_start,
            period_end=period_end,
            avg_task_minutes=round(avg_minutes, 2),
            success_rate=success_rate,
            failure_rate=failure_rate,
            speed_score=speed_score,
            repeated_issues_count=repeated,
        )
        return Response(PerformanceMetricSerializer(metric).data)


class ObjectiveDecomposeView(APIView):
    """Decompose one objective into ordered milestones."""

    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def post(self, request, id: int, *args, **kwargs) -> Response:
        objective = get_object_or_404(Objective, id=id, student=request.user)
        ObjectiveMilestone.objects.filter(objective=objective).delete()
        created = []
        source_tasks = list(objective.tasks.all().order_by("order", "id"))
        if source_tasks:
            for i, task in enumerate(source_tasks, start=1):
                created.append(
                    ObjectiveMilestone.objects.create(
                        objective=objective,
                        title=task.title,
                        description=f"Complete task: {task.description}" if task.description else "",
                        priority=i,
                        order=i,
                    )
                )
        else:
            steps = [
                "Understand objective requirements",
                "Implement first deliverable",
                "Validate and test results",
                "Document and finalize portfolio output",
            ]
            for i, title in enumerate(steps, start=1):
                created.append(ObjectiveMilestone.objects.create(objective=objective, title=title, priority=i, order=i))
        return Response({"milestones": ObjectiveMilestoneSerializer(created, many=True).data}, status=status.HTTP_201_CREATED)


class PortfolioProjectListCreateView(generics.ListCreateAPIView):
    """List/create student portfolio projects."""

    serializer_class = PortfolioProjectSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_queryset(self):
        return PortfolioProject.objects.filter(student=self.request.user).order_by("-updated_at")

    def perform_create(self, serializer) -> None:
        serializer.save(student=self.request.user)


class PortfolioProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve/update/delete one student portfolio project."""

    serializer_class = PortfolioProjectSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_queryset(self):
        return PortfolioProject.objects.filter(student=self.request.user)


class PortfolioAssetCreateView(APIView):
    """Upload asset to one portfolio project."""

    permission_classes = [permissions.IsAuthenticated, IsStudent]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request=PortfolioAssetUploadSerializer, responses={201: PortfolioAssetSerializer})
    def post(self, request, id: int, *args, **kwargs) -> Response:
        project = get_object_or_404(PortfolioProject, id=id, student=request.user)
        serializer = PortfolioAssetUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        asset = project.assets.create(
            file=serializer.validated_data["file"],
            caption=serializer.validated_data.get("caption", ""),
        )
        return Response(PortfolioAssetSerializer(asset).data, status=status.HTTP_201_CREATED)
