"""Celery tasks for AI workflows."""
from __future__ import annotations

try:
    from celery import shared_task
except Exception:  # pragma: no cover
    def shared_task(func=None, **_kwargs):
        if func is None:
            return lambda f: f
        return func
from datetime import timedelta
from django.utils import timezone

from accounts.models import ExpertAssignment, Notification, User, UserActivityLog
from accounts.services import create_notification
from ai.models import AIModelWeight
from ai.services import get_ai_service
from proofs.models import Challenge, ProgrammingQuestion, Proof
from proofs.services import run_proof_analysis
from scheduling.models import Session


@shared_task
def analyze_proof_task(proof_id: int) -> dict:
    """Asynchronously analyze proof and create remediation artifacts."""
    proof = Proof.objects.get(id=proof_id)
    run_proof_analysis(proof)
    return {"proof_id": proof_id, "status": "analyzed"}


@shared_task
def generate_daily_challenges_task() -> dict:
    """Generate challenges for students from open issues."""
    service = get_ai_service(capability=AIModelWeight.CAPABILITY_CHALLENGE)
    created = 0
    today = timezone.localdate()
    for student_id in (
        Proof.objects.filter(task__objective__student__is_student=True).values_list("task__objective__student_id", flat=True).distinct()
    ):
        open_issues = list(
            ProgrammingQuestion.objects.filter(proof__task__objective__student_id=student_id).values_list("title", flat=True)[:3]
        )
        generated = service.generate({"open_issues": open_issues})
        for row in generated[:3]:
            Challenge.objects.create(
                student_id=student_id,
                text=row["text"],
                difficulty=row.get("difficulty", "easy"),
                scheduled_date=today,
            )
            created += 1
            print(f"[challenge] student={student_id} text={row['text']}")
    return {"created": created}


@shared_task
def send_reminder_notifications_task() -> dict:
    """Send inactivity, streak-risk, session, and assignment-expiry notifications."""
    now = timezone.now()
    today = timezone.localdate()
    sent = 0

    for session in Session.objects.filter(status=Session.STATUS_PLANNED, scheduled_start__gte=now, scheduled_start__lte=now + timedelta(minutes=15)):
        create_notification(
            user=session.student,
            type=Notification.TYPE_SESSION_REMINDER,
            title="Session reminder",
            message=f"Your session for {session.task.title} starts soon.",
            related_id=session.id,
        )
        sent += 1

    recent_cutoff = now - timedelta(hours=24)
    inactive_students = User.objects.filter(is_student=True).exclude(activity_logs__created_at__gte=recent_cutoff).distinct()
    for student in inactive_students:
        create_notification(
            user=student,
            type=Notification.TYPE_INACTIVITY,
            title="Inactivity reminder",
            message="You have been inactive for 24 hours. Continue a task to keep momentum.",
        )
        sent += 1

    streak_cutoff = today - timedelta(days=1)
    for student in User.objects.filter(is_student=True, current_streak__gt=0):
        had_recent_completion = UserActivityLog.objects.filter(
            user=student,
            event_type=UserActivityLog.EVENT_TASK_COMPLETED,
            created_at__date__gte=streak_cutoff,
        ).exists()
        if not had_recent_completion:
            create_notification(
                user=student,
                type=Notification.TYPE_STREAK,
                title="Streak reminder",
                message="Complete a task today to protect your streak.",
            )
            sent += 1

    for assignment in ExpertAssignment.objects.filter(status=ExpertAssignment.STATUS_ACTIVE, expires_at__isnull=False):
        remaining = assignment.expires_at - now
        if timedelta(days=0) <= remaining <= timedelta(days=3):
            create_notification(
                user=assignment.student,
                type=Notification.TYPE_ASSIGNMENT_EXPIRY,
                title="Assignment expiring soon",
                message=f"Your mentorship assignment with {assignment.expert.username} expires soon.",
                related_id=assignment.id,
            )
            sent += 1
    return {"sent": sent}


@shared_task
def expire_assignments_task() -> dict:
    """Expire outdated active assignments."""
    now = timezone.now()
    expired = ExpertAssignment.objects.filter(status=ExpertAssignment.STATUS_ACTIVE, expires_at__lt=now)
    count = 0
    for assignment in expired:
        assignment.status = ExpertAssignment.STATUS_EXPIRED
        assignment.save(update_fields=["status", "updated_at"])
        create_notification(
            user=assignment.student,
            type=Notification.TYPE_ASSIGNMENT_EXPIRY,
            title="Assignment expired",
            message=f"Your mentorship assignment with {assignment.expert.username} has expired.",
            related_id=assignment.id,
        )
        count += 1
    return {"expired": count}
