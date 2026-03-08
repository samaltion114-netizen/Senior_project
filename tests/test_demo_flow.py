"""Integration test for end-to-end senior project flow."""
from __future__ import annotations

from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from proofs.models import ProgrammingQuestion, TodoItem


def register_and_login(client: APIClient, username: str, role: str, extra: dict | None = None) -> str:
    payload = {"username": username, "email": f"{username}@example.com", "password": "pass12345", "role": role}
    if extra:
        payload.update(extra)
    r = client.post("/api/auth/register/", payload, format="json")
    assert r.status_code == 201
    t = client.post("/api/auth/token/", {"username": username, "password": "pass12345"}, format="json")
    assert t.status_code == 200
    return t.json()["access"]


@pytest.mark.django_db(transaction=True)
def test_demo_flow_e2e() -> None:
    student_client = APIClient()

    student_token = register_and_login(student_client, "student1", "student", {"major": "IT"})
    register_and_login(student_client, "expert1", "expert", {"bio": "AI mentor", "expertise_tags": ["ai", "backend"]})

    student_client.credentials(HTTP_AUTHORIZATION=f"Bearer {student_token}")

    start = student_client.post("/api/interview/start/", {}, format="json")
    assert start.status_code == 201
    conversation_id = start.json()["conversation_id"]
    msg = student_client.post(
        "/api/interview/message/",
        {"conversation_id": conversation_id, "message": "I want training in AI backend for internship"},
        format="json",
    )
    assert msg.status_code == 200
    suggested = msg.json()["recommended_objective"]
    assert suggested is not None

    obj = student_client.post(
        "/api/objectives/",
        {
            "title": suggested["title"],
            "description": suggested["description"],
            "suggested_by": "ai",
            "status": "active",
        },
        format="json",
    )
    assert obj.status_code == 201
    objective_id = obj.json()["id"]

    t1 = student_client.post(
        f"/api/objectives/{objective_id}/tasks/",
        {
            "title": "Implement classifier",
            "description": "build a basic classifier API",
            "metadata": {"complexity": 2},
            "order": 1,
            "expected_output_text": "trained model and test output",
        },
        format="json",
    )
    t2 = student_client.post(
        f"/api/objectives/{objective_id}/tasks/",
        {"title": "Write docs", "description": "document endpoints", "metadata": {"complexity": 1}, "order": 2},
        format="json",
    )
    assert t1.status_code == 201 and t2.status_code == 201

    schedule = student_client.post(
        "/api/schedule/optimize/",
        {
            "objective_id": objective_id,
            "weekly_availability": {
                "monday": [{"start": "18:00", "end": "20:00"}],
                "wednesday": [{"start": "18:00", "end": "20:00"}],
            },
            "max_daily_minutes": 90,
            "break_minutes": 10,
        },
        format="json",
    )
    assert schedule.status_code == 201
    sessions = schedule.json()["sessions"]
    assert sessions
    session_id = sessions[0]["id"]

    image_path = Path(__file__).parent / "fixtures" / "screenshot1.png"
    image = SimpleUploadedFile("screenshot1.png", image_path.read_bytes(), content_type="image/png")
    complete = student_client.post(
        f"/api/sessions/{session_id}/complete/",
        {"image": image, "explanation": "I uploaded unrelated output so this should mismatch."},
        format="multipart",
    )
    assert complete.status_code == 201
    proof_id = complete.json()["id"]

    analysis = student_client.get(f"/api/proofs/{proof_id}/analysis/")
    assert analysis.status_code == 200
    ai_analysis = analysis.json()["ai_analysis"]
    assert "confidence_score" in ai_analysis

    assert ProgrammingQuestion.objects.filter(proof_id=proof_id).exists()
    pq = ProgrammingQuestion.objects.filter(proof_id=proof_id).first()
    assert TodoItem.objects.filter(programming_question=pq).exists()

    gen = student_client.post("/api/ai/challenges/generate/", {"domain": "informatics", "level": "beginner", "minutes": 15}, format="json")
    assert gen.status_code == 200
    challenges = student_client.get("/api/challenges/")
    assert challenges.status_code == 200
    assert len(challenges.json()) >= 1
