"""Proof analysis orchestration helpers."""
from __future__ import annotations

from typing import Any

from PIL import Image, ImageFilter, ImageStat
from django.db import transaction

from ai.models import AIEventLog
from ai.models import AIModelWeight
from ai.services import get_ai_service, hash_text
from core.models import LearningPath, PathAdjustment
from proofs.models import ProgrammingQuestion, Proof, TodoItem


def evaluate_image_quality(image_path: str) -> dict[str, Any]:
    """Compute lightweight quality metrics."""
    with Image.open(image_path) as im:
        rgb = im.convert("RGB")
        gray = rgb.convert("L")
        width, height = rgb.size
        resolution_ok = width >= 900 and height >= 600
        blur_proxy = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).stddev[0]
        brightness = ImageStat.Stat(gray).mean[0]
        contrast = ImageStat.Stat(gray).stddev[0]
        blur_score = min(1.0, blur_proxy / 40.0)
        brightness_score = 1.0 - min(1.0, abs(brightness - 127) / 127)
        contrast_score = min(1.0, contrast / 64.0)
        quality_score = round((blur_score * 0.4 + brightness_score * 0.3 + contrast_score * 0.3), 3)
        decision = "OK" if quality_score >= 0.6 and resolution_ok else "RETRY"
        return {
            "quality_score": quality_score,
            "blur_score": round(blur_score, 3),
            "brightness_score": round(brightness_score, 3),
            "contrast_score": round(contrast_score, 3),
            "resolution_ok": resolution_ok,
            "glare_detected": False,
            "decision": decision,
        }


@transaction.atomic
def run_proof_analysis(proof: Proof) -> Proof:
    """Run AI proof analysis and create derived artifacts."""
    service = get_ai_service(capability=AIModelWeight.CAPABILITY_PROOF)
    task = proof.session.task
    quality = evaluate_image_quality(proof.image.path)
    payload = {
        "task_description": f"{task.title}. {task.description}. Expected: {task.expected_output_text}",
        "explanation_text": proof.explanation_text,
        "image_caption": f"Screenshot proof upload for task {task.title}",
        "quality": quality,
    }
    analysis = service.analyze(payload)
    proof.ai_analysis = analysis
    proof.analysis_status = "done"
    proof.save(update_fields=["ai_analysis", "analysis_status"])
    _apply_adaptive_learning_adjustment(proof=proof, analysis=analysis)

    if not analysis.get("matches_expected", False) or analysis.get("confidence_score", 0) < service.confidence_threshold:
        pq_data = service.generate_programming_question(
            suspected_issue=analysis.get("suspected_issue") or "General mismatch",
            proof_context=proof.explanation_text,
        )
        question = ProgrammingQuestion.objects.create(
            proof=proof,
            title=pq_data["title"],
            description=pq_data["description"],
            severity=pq_data["severity"],
            suggested_fixes=pq_data["suggested_fixes"],
        )
        for fix in pq_data["suggested_fixes"]:
            TodoItem.objects.create(
                programming_question=question,
                title=fix["title"],
                description=fix["description"],
                priority=fix.get("priority", "medium"),
            )

    prompt = payload["task_description"] + "\n" + payload["explanation_text"]
    response = str(analysis)
    AIEventLog.objects.create(
        user=proof.session.student,
        event_type="proof_analysis",
        prompt=prompt,
        response=response,
        prompt_hash=hash_text(prompt),
        response_hash=hash_text(response),
        embeddings_metadata={"proof_id": proof.id},
    )
    return proof


def _apply_adaptive_learning_adjustment(proof: Proof, analysis: dict[str, Any]) -> None:
    """Adjust student learning path level based on proof quality/performance."""
    student = proof.session.student
    path, _ = LearningPath.objects.get_or_create(student=student)
    before = path.current_level
    confidence = float(analysis.get("confidence_score", 0.0) or 0.0)
    matches = bool(analysis.get("matches_expected", False))

    if matches and confidence >= 0.85:
        after = min(before + 1, 10)
        reason = f"Increased level due to strong proof match (confidence={confidence:.2f})."
    elif not matches or confidence < 0.65:
        after = max(before - 1, 1)
        reason = f"Decreased level due to mismatch/low confidence (confidence={confidence:.2f})."
    else:
        after = before
        reason = f"No level change (confidence={confidence:.2f})."

    if after != before:
        path.current_level = after
        path.adaptation_notes = reason
        path.save(update_fields=["current_level", "adaptation_notes", "updated_at"])
        PathAdjustment.objects.create(
            learning_path=path,
            before_level=before,
            after_level=after,
            reason=reason,
            source=PathAdjustment.SOURCE_PROOF,
            related_proof=proof,
        )
