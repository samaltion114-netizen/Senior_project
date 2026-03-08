"""Celery tasks for AI workflows."""
from __future__ import annotations

try:
    from celery import shared_task
except Exception:  # pragma: no cover
    def shared_task(func=None, **_kwargs):
        if func is None:
            return lambda f: f
        return func
from django.utils import timezone

from ai.models import AIModelWeight
from ai.services import get_ai_service
from proofs.models import Challenge, ProgrammingQuestion, Proof
from proofs.services import run_proof_analysis


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
        Proof.objects.filter(session__student__is_student=True).values_list("session__student_id", flat=True).distinct()
    ):
        open_issues = list(
            ProgrammingQuestion.objects.filter(proof__session__student_id=student_id).values_list("title", flat=True)[:3]
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
