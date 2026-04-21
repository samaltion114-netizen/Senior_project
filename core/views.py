"""Views for objectives and tasks."""
from __future__ import annotations

from datetime import timedelta

from django.db import connection
from django.db import transaction
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsStudent
from accounts.models import ExpertAssignment, Notification
from accounts.services import award_badge_if_eligible, create_notification, log_user_activity
from ai.models import AIModelWeight
from ai.services import get_ai_service, text_to_embedding
from core.models import Objective, ObjectiveMilestone, PerformanceMetric, PortfolioProject, ProgressSnapshot, Task
from core.serializers import (
    CreateTaskSerializer,
    GenerateTasksSerializer,
    ObjectiveMilestoneSerializer,
    ObjectiveSerializer,
    PerformanceMetricSerializer,
    PortfolioAssetSerializer,
    PortfolioAssetUploadSerializer,
    PortfolioProjectSerializer,
    ProgressSnapshotSerializer,
    TaskSerializer,
    TaskCommentSerializer,
    TaskUpdateSerializer,
)
from proofs.models import Challenge, ProgrammingQuestion
from scheduling.models import Session


def _user_level_for_request(request) -> str:
    profile = getattr(request.user, "student_profile", None)
    raw = (profile.current_status if profile else "") or ""
    lowered = raw.lower()
    if any(token in lowered for token in ["beginner", "new", "starter"]):
        return "beginner"
    if any(token in lowered for token in ["advanced", "expert", "senior"]):
        return "advanced"
    return "intermediate"


class ObjectiveListCreateView(generics.ListCreateAPIView):
    """List and create objectives for current student."""

    serializer_class = ObjectiveSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_queryset(self):
        return Objective.objects.filter(student=self.request.user).order_by("-created_at")

    def perform_create(self, serializer) -> None:
        serializer.save(student=self.request.user)


class ObjectiveDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete one objective."""

    serializer_class = ObjectiveSerializer
    permission_classes = [permissions.IsAuthenticated, IsStudent]

    def get_queryset(self):
        return Objective.objects.filter(student=self.request.user)


class ObjectiveTaskCreateView(APIView):
    """Create task under objective and call AI time estimation."""

    permission_classes = [permissions.IsAuthenticated, IsStudent]

    @extend_schema(request=CreateTaskSerializer, responses={201: TaskSerializer})
    def post(self, request, id: int, *args, **kwargs) -> Response:
        objective = Objective.objects.get(id=id, student=request.user)
        serializer = CreateTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ai_service = get_ai_service(capability=AIModelWeight.CAPABILITY_TIME)
        task_ai = ai_service.validate_or_generate_tasks(
            objective_title=objective.title,
            task_name=serializer.validated_data["title"],
            user_level=_user_level_for_request(request),
        )
        if not task_ai.get("is_valid", False):
            return Response({"detail": "Task is not relevant to the selected objective."}, status=status.HTTP_400_BAD_REQUEST)
        ai_task = task_ai["tasks"][0]
        estimate_payload = {
            **serializer.validated_data,
            "task_type": ai_task["task_type"],
            "task_size": ai_task["task_size"],
            "difficulty_level": ai_task["difficulty"],
            "metadata": {
                **serializer.validated_data.get("metadata", {}),
                "task_type": ai_task["task_type"],
                "user_level": ai_task["user_level"],
            },
        }
        estimate = ai_service.estimate_time(estimate_payload)
        task = serializer.save(
            objective=objective,
            status=serializer.validated_data.get("status", Task.STATUS_ACTIVE),
            type=ai_task["type"],
            difficulty_level=ai_task["difficulty"],
            task_size=ai_task["task_size"],
            xp_reward=serializer.validated_data.get("xp_reward") or ai_task["xp_reward"],
            estimated_minutes=estimate["estimated_minutes"],
            estimation_confidence=estimate["confidence"],
            youtube_link_ar=serializer.validated_data.get("youtube_link_ar") or ai_task["youtube_link_ar"],
            youtube_link_en=serializer.validated_data.get("youtube_link_en") or ai_task["youtube_link_en"],
            expected_output_embedding=text_to_embedding(serializer.validated_data.get("expected_output_text", "")),
        )
        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)


class ObjectiveGenerateTasksView(APIView):
    """Generate multiple AI-enriched tasks for one objective."""

    permission_classes = [permissions.IsAuthenticated, IsStudent]

    @extend_schema(request=GenerateTasksSerializer, responses={201: dict})
    def post(self, request, id: int, *args, **kwargs) -> Response:
        objective = get_object_or_404(Objective, id=id, student=request.user)
        serializer = GenerateTasksSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ai_service = get_ai_service(capability=AIModelWeight.CAPABILITY_TIME)
        generated = ai_service.validate_or_generate_tasks(
            objective_title=objective.title,
            task_name="",
            user_level=serializer.validated_data["user_level"],
            count=serializer.validated_data["count"],
        )
        created = []
        next_order = objective.tasks.count() + 1
        for offset, row in enumerate(generated["tasks"], start=0):
            estimate = ai_service.estimate_time(
                {
                    "title": row["task_name"],
                    "description": f"AI generated for objective {objective.title}",
                    "task_type": row["task_type"],
                    "task_size": row["task_size"],
                    "difficulty_level": row["difficulty"],
                    "metadata": {"task_type": row["task_type"], "user_level": row["user_level"]},
                }
            )
            created.append(
                Task.objects.create(
                    objective=objective,
                    title=row["task_name"],
                    description=f"AI generated for objective {objective.title}",
                    type=row["type"],
                    difficulty_level=row["difficulty"],
                    task_size=row["task_size"],
                    xp_reward=row["xp_reward"],
                    estimated_minutes=estimate["estimated_minutes"],
                    estimation_confidence=estimate["confidence"],
                    order=next_order + offset,
                    youtube_link_ar=row["youtube_link_ar"],
                    youtube_link_en=row["youtube_link_en"],
                )
            )
        return Response({"tasks": TaskSerializer(created, many=True).data}, status=status.HTTP_201_CREATED)


class TaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete one task."""

    permission_classes = [permissions.IsAuthenticated, IsStudent]
    serializer_class = TaskUpdateSerializer

    def get_queryset(self):
        return Task.objects.filter(objective__student=self.request.user).select_related("objective")

    def retrieve(self, request, *args, **kwargs) -> Response:
        instance = self.get_object()
        return Response(TaskSerializer(instance).data)

    def update(self, request, *args, **kwargs) -> Response:
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        task = serializer.save()
        return Response(TaskSerializer(task).data)


class TaskCompleteView(APIView):
    """Complete task, award XP, and update streak fields."""

    permission_classes = [permissions.IsAuthenticated, IsStudent]

    @transaction.atomic
    def post(self, request, id: int, *args, **kwargs) -> Response:
        task = get_object_or_404(Task.objects.select_for_update(), id=id, objective__student=request.user)
        user = request.user
        badge_won = None
        if task.status != Task.STATUS_COMPLETED:
            task.status = Task.STATUS_COMPLETED
            task.save(update_fields=["status"])
            user.total_xp += task.xp_reward
            today = timezone.localdate()
            last_activity = user.student_profile.weekly_availability.get("_last_task_completion_date") if hasattr(user, "student_profile") else None
            if last_activity == str(today - timedelta(days=1)):
                user.current_streak += 1
            elif last_activity == str(today):
                pass
            else:
                user.current_streak = 1
            user.highest_streak = max(user.highest_streak, user.current_streak)
            user.save(update_fields=["total_xp", "current_streak", "highest_streak"])
            if hasattr(user, "student_profile"):
                profile = user.student_profile
                profile.weekly_availability = {**profile.weekly_availability, "_last_task_completion_date": str(today)}
                profile.save(update_fields=["weekly_availability"])
            log_user_activity(user=user, event_type="task_completed", related_id=task.id, metadata={"xp_reward": task.xp_reward})
            badge_won = award_badge_if_eligible(user)
            create_notification(
                user=user,
                type=Notification.TYPE_GAMIFICATION,
                title="Task completed",
                message=f"You earned {task.xp_reward} XP for completing {task.title}.",
                related_id=task.id,
                metadata={"badge_won": badge_won},
            )
        return Response(
            {
                "task_id": task.id,
                "task_status": task.status,
                "xp_earned": task.xp_reward,
                "new_total_xp": user.total_xp,
                "streak_updated": user.current_streak,
                "badge_won": badge_won,
            }
        )


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
        create_notification(
            user=request.user,
            type=Notification.TYPE_TASK_DECOMPOSED,
            title="Objective decomposed",
            message=f"{objective.title} was decomposed into {len(created)} milestones.",
            related_id=objective.id,
        )
        return Response({"milestones": ObjectiveMilestoneSerializer(created, many=True).data}, status=status.HTTP_201_CREATED)


class TaskCommentCreateView(APIView):
    """Create task comments when there is an active expert assignment."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id: int, *args, **kwargs) -> Response:
        task = get_object_or_404(Task.objects.select_related("objective__student"), id=id)
        serializer = TaskCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment_exists = ExpertAssignment.objects.filter(
            student=task.objective.student,
            status=ExpertAssignment.STATUS_ACTIVE,
        ).filter(expert=request.user).exists() or request.user == task.objective.student
        if not assignment_exists:
            return Response({"detail": "Active assignment required before commenting."}, status=status.HTTP_403_FORBIDDEN)
        comment = serializer.save(task=task, author=request.user)
        return Response(TaskCommentSerializer(comment).data, status=status.HTTP_201_CREATED)


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
