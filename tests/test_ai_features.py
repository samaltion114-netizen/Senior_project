"""Unit tests for standalone AI feature APIs."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import EmailVerificationToken, PasswordResetToken
from core.models import Objective
from ai.tasks import send_reminder_notifications_task
from scheduling.models import Session

User = get_user_model()

@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _register_and_auth(client: APIClient, username: str, role: str = "student") -> str:
    register_payload = {"username": username, "email": f"{username}@example.com", "password": "pass12345", "role": role}
    resp = client.post("/api/auth/register/", register_payload, format="json")
    assert resp.status_code == 201
    token_resp = client.post("/api/auth/token/", {"username": username, "password": "pass12345"}, format="json")
    assert token_resp.status_code == 200
    return token_resp.json()["access"]


@pytest.mark.django_db
def test_tagging_endpoints(client: APIClient) -> None:
    token = _register_and_auth(client, "s_tag")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    r1 = client.post("/api/ai/tagging/informatics/", {"text": "Django REST API returns 401 with JWT"}, format="json")
    assert r1.status_code == 200
    assert len(r1.json()["tags"]) >= 3

    r2 = client.post("/api/ai/tagging/legal/", {"text": "هل يحق فسخ العقد عند التأخير؟"}, format="json")
    assert r2.status_code == 200
    assert "disclaimer" in r2.json()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("start_url", "message_url", "username"),
    [
        ("/api/voice/start/", "/api/voice/message/", "voice_root"),
        ("/api/ai/voice/start/", "/api/ai/voice/message/", "voice_ai"),
    ],
)
def test_voice_mock_endpoints(client: APIClient, start_url: str, message_url: str, username: str) -> None:
    token = _register_and_auth(client, username)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    start = client.post(start_url, {}, format="json")
    assert start.status_code == 201
    conversation_id = start.json()["conversation_id"]

    resp = client.post(
        message_url,
        {"conversation_id": conversation_id, "transcript": "I want training in AI backend for internship"},
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["conversation_id"] == conversation_id
    assert body["reply"]
    assert body["recommended_objective"] is not None


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("endpoint", "username"),
    [
        ("/api/voice/", "voice_one_shot_root"),
        ("/api/ai/voice/", "voice_one_shot_ai"),
    ],
)
def test_voice_one_shot_aliases(client: APIClient, endpoint: str, username: str) -> None:
    token = _register_and_auth(client, username)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    resp = client.post(endpoint, {"transcript": "I want training in AI backend for internship"}, format="json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["conversation_id"]
    assert body["reply"]
    assert body["recommended_objective"] is not None


@pytest.mark.django_db
def test_time_estimate_endpoint(client: APIClient) -> None:
    token = _register_and_auth(client, "s_est")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    resp = client.post(
        "/api/ai/time-estimate/",
        {
            "title": "Implement a classifier",
            "description": "Build model and evaluate",
            "metadata": {"complexity": 2, "specialty": "Artificial Intelligence", "task_type": "Model Training", "user_level": 2},
        },
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["estimated_minutes"] > 0
    assert 0 <= body["confidence"] <= 1
    assert body["source"] in {"informatics_task_times_synthetic_csv", "heuristic_fallback"}


@pytest.mark.django_db
def test_model_weight_selection_endpoints(client: APIClient) -> None:
    token = _register_and_auth(client, "s_model")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    list_resp = client.get("/api/ai/models/weights/")
    assert list_resp.status_code == 200
    assert "files" in list_resp.json()

    select_resp = client.post(
        "/api/ai/models/select/",
        {
            "capability": "interview",
            "provider": "local",
            "model_name": "interview_v1",
            "weight_path": "C:/models/interview_v1.onnx",
            "metadata": {"framework": "onnx"},
        },
        format="json",
    )
    assert select_resp.status_code == 200
    assert select_resp.json()["is_active"] is True


@pytest.mark.django_db
def test_email_verification_and_password_reset_flow(client: APIClient) -> None:
    _register_and_auth(client, "security_user")
    user = User.objects.get(username="security_user")
    assert user.is_email_verified is False

    token = EmailVerificationToken.objects.filter(user=user).order_by("-created_at").first()
    assert token is not None
    verify = client.post("/api/auth/verify-email/confirm/", {"token": token.token}, format="json")
    assert verify.status_code == 200
    user.refresh_from_db()
    assert user.is_email_verified is True

    req = client.post("/api/auth/password-reset/request/", {"email": user.email}, format="json")
    assert req.status_code == 200
    reset_token = PasswordResetToken.objects.filter(user=user).order_by("-created_at").first()
    assert reset_token is not None
    confirm = client.post(
        "/api/auth/password-reset/confirm/",
        {"token": reset_token.token, "new_password": "newpass123"},
        format="json",
    )
    assert confirm.status_code == 200

    login = client.post("/api/auth/token/", {"username": "security_user", "password": "newpass123"}, format="json")
    assert login.status_code == 200


@pytest.mark.django_db
def test_v1_routes_work(client: APIClient) -> None:
    resp = client.post(
        "/api/v1/auth/register/",
        {"username": "v1user", "email": "v1user@example.com", "password": "pass12345", "role": "student"},
        format="json",
    )
    assert resp.status_code == 201


@pytest.mark.django_db
def test_dashboard_decompose_performance_and_portfolio(client: APIClient) -> None:
    token = _register_and_auth(client, "student_feat")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    obj = client.post(
        "/api/objectives/",
        {"title": "Goal", "description": "desc", "suggested_by": "ai", "status": "active"},
        format="json",
    )
    assert obj.status_code == 201
    objective_id = obj.json()["id"]
    task = client.post(
        f"/api/objectives/{objective_id}/tasks/",
        {"title": "Task A", "description": "Build X", "order": 1, "metadata": {"complexity": 1}},
        format="json",
    )
    assert task.status_code == 201

    decompose = client.post(f"/api/objectives/{objective_id}/decompose/", {}, format="json")
    assert decompose.status_code == 201
    assert len(decompose.json()["milestones"]) >= 1

    dashboard = client.get("/api/dashboard/progress/")
    assert dashboard.status_code == 200
    assert "overall_progress_percent" in dashboard.json()

    perf = client.get("/api/performance/summary/")
    assert perf.status_code == 200
    assert "success_rate" in perf.json()

    project = client.post(
        "/api/portfolio/projects/",
        {"title": "My Project", "description": "Demo", "tech_stack": ["django"], "visibility": "private"},
        format="json",
    )
    assert project.status_code == 201
    project_id = project.json()["id"]
    lst = client.get("/api/portfolio/projects/")
    assert lst.status_code == 200
    assert len(lst.json()) >= 1
    detail = client.patch(f"/api/portfolio/projects/{project_id}/", {"description": "Updated"}, format="json")
    assert detail.status_code == 200


@pytest.mark.django_db
def test_goal_validation_and_portfolio_linkedin_flow(client: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = _register_and_auth(client, "portfolio_goal_student")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    invalid = client.post(
        "/api/ai/goals/generate/",
        {"goal": "xqz", "user_level": "beginner", "count": 3},
        format="json",
    )
    assert invalid.status_code == 400
    assert "detail" in invalid.json()

    preview = client.post(
        "/api/ai/goals/generate/",
        {"goal": "Backend AI Portfolio", "user_level": "beginner", "count": 3},
        format="json",
    )
    assert preview.status_code == 200
    assert preview.json()["status"] == "valid"
    assert len(preview.json()["tasks"]) == 3
    assert any("Backend AI Portfolio" in task["task_name"] for task in preview.json()["tasks"])

    objective = client.post(
        "/api/objectives/",
        {"title": "Backend AI Portfolio", "description": "desc", "suggested_by": "ai", "status": "active"},
        format="json",
    )
    assert objective.status_code == 201
    objective_id = objective.json()["id"]

    task1 = client.post(
        f"/api/objectives/{objective_id}/tasks/",
        {"title": "Build backend API", "description": "Create endpoints", "order": 1, "metadata": {"complexity": 2}},
        format="json",
    )
    task2 = client.post(
        f"/api/objectives/{objective_id}/tasks/",
        {"title": "Write deployment notes", "description": "Document release", "order": 2, "metadata": {"complexity": 1}},
        format="json",
    )
    assert task1.status_code == 201 and task2.status_code == 201
    client.post(f"/api/tasks/{task1.json()['id']}/complete/", {}, format="json")
    client.post(f"/api/tasks/{task2.json()['id']}/complete/", {}, format="json")

    generated = client.post(f"/api/portfolio/goals/{objective_id}/", {}, format="json")
    assert generated.status_code == 200
    body = generated.json()
    assert body["goal_title"] == "Backend AI Portfolio"
    assert body["all_tasks_completed"] is True
    assert len(body["completed_tasks"]) == 2
    assert body["linkedin_generated_text"]
    assert Objective.objects.get(id=objective_id).linkedin_generated_text == body["linkedin_generated_text"]

    cached = client.post(f"/api/portfolio/goals/{objective_id}/", {}, format="json")
    assert cached.status_code == 200
    assert cached.json()["linkedin_generated_text"] == body["linkedin_generated_text"]

    fallback_objective = client.post(
        "/api/objectives/",
        {"title": "Legal Career Portfolio", "description": "desc", "suggested_by": "ai", "status": "active"},
        format="json",
    )
    assert fallback_objective.status_code == 201
    fallback_objective_id = fallback_objective.json()["id"]
    fallback_task = client.post(
        f"/api/objectives/{fallback_objective_id}/tasks/",
        {"title": "Review contract clauses", "description": "Read and summarize", "order": 1, "metadata": {"complexity": 1}},
        format="json",
    )
    assert fallback_task.status_code == 201
    client.post(f"/api/tasks/{fallback_task.json()['id']}/complete/", {}, format="json")

    class BrokenService:
        def generate_linkedin_post(self, **_kwargs):
            raise TimeoutError("timeout")

    monkeypatch.setattr("core.views.get_ai_service", lambda capability=None: BrokenService())
    fallback = client.post(f"/api/portfolio/goals/{fallback_objective_id}/", {}, format="json")
    assert fallback.status_code == 200
    assert fallback.json()["linkedin_generated_text"]
    assert Objective.objects.get(id=fallback_objective_id).linkedin_generated_text == fallback.json()["linkedin_generated_text"]


@pytest.mark.django_db
def test_generated_tasks_assignments_notifications_and_payments(client: APIClient) -> None:
    student_token = _register_and_auth(client, "student_market")
    expert_client = APIClient()
    expert_token = _register_and_auth(expert_client, "expert_market", role="expert")

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {student_token}")
    objective = client.post(
        "/api/objectives/",
        {"title": "Backend AI Goal", "description": "desc", "suggested_by": "ai", "status": "active"},
        format="json",
    )
    assert objective.status_code == 201
    objective_id = objective.json()["id"]

    generated = client.post(
        f"/api/objectives/{objective_id}/generate-tasks/",
        {"user_level": "beginner", "count": 3},
        format="json",
    )
    assert generated.status_code == 201
    assert len(generated.json()["tasks"]) == 3

    experts = client.get("/api/experts/?search=expert")
    assert experts.status_code == 200
    expert_user_id = experts.json()[0]["user_id"]
    assign = client.post("/api/assignments/request/", {"expert_id": expert_user_id, "request_message": "Need help"}, format="json")
    assert assign.status_code == 201
    assignment_id = assign.json()["id"]

    expert_client.credentials(HTTP_AUTHORIZATION=f"Bearer {expert_token}")
    accept = expert_client.post(f"/api/trainer/assignments/{assignment_id}/accept/", {}, format="json")
    assert accept.status_code == 200
    assert accept.json()["status"] == "awaiting_payment"

    notifications = client.get("/api/notifications/")
    assert notifications.status_code == 200
    assert any(item["type"] == "assignment_accepted" for item in notifications.json())

    payment = client.post("/api/payments/intent/", {"assignment_id": assignment_id, "currency": "usd"}, format="json")
    assert payment.status_code == 200
    assert "client_secret" in payment.json()
    payment_intent_id = payment.json()["payment_intent_id"]

    webhook = client.post(
        "/api/payments/webhook/",
        {"payment_intent_id": payment_intent_id, "status": "succeeded", "metadata": {"source": "test"}},
        format="json",
    )
    assert webhook.status_code == 200
    assert webhook.json()["status"] == "succeeded"

    threads = client.get("/api/chat/threads/")
    assert threads.status_code == 200
    assert len(threads.json()) == 1
    thread_id = threads.json()[0]["id"]

    student_message = client.post(f"/api/chat/threads/{thread_id}/messages/", {"body": "Hello expert"}, format="json")
    assert student_message.status_code == 201

    expert_client.credentials(HTTP_AUTHORIZATION=f"Bearer {expert_token}")
    expert_messages = expert_client.get(f"/api/chat/threads/{thread_id}/messages/")
    assert expert_messages.status_code == 200
    assert len(expert_messages.json()) >= 1

    payments = client.get("/api/payments/")
    assert payments.status_code == 200
    assert payments.json()[0]["payment_intent_id"] == payment_intent_id


@pytest.mark.django_db
def test_expert_rating_and_profile_update(client: APIClient) -> None:
    student_token = _register_and_auth(client, "rating_student")
    expert_client = APIClient()
    expert_token = _register_and_auth(expert_client, "rating_expert", role="expert")
    expert = User.objects.get(username="rating_expert")

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {student_token}")
    assign = client.post(
        "/api/assignments/request/",
        {"expert_id": expert.id, "request_message": "Need mentorship"},
        format="json",
    )
    assert assign.status_code == 201

    expert_client.credentials(HTTP_AUTHORIZATION=f"Bearer {expert_token}")
    accept = expert_client.post(f"/api/trainer/assignments/{assign.json()['id']}/accept/", {}, format="json")
    assert accept.status_code == 200

    rating = client.post(
        f"/api/experts/{expert.id}/rate/",
        {"rating": 5, "feedback": "Very helpful"},
        format="json",
    )
    assert rating.status_code == 201
    assert rating.json()["average_rating"] == 5.0

    me = expert_client.get("/api/experts/me/")
    assert me.status_code == 200
    assert me.json()["average_rating"] == 5.0

    patch = expert_client.patch("/api/experts/me/", {"bio": "Updated bio", "is_accepting_new_students": False}, format="json")
    assert patch.status_code == 200
    assert patch.json()["bio"] == "Updated bio"
    assert patch.json()["is_accepting_new_students"] is False


@pytest.mark.django_db
def test_reminder_notification_task_creates_session_and_inactivity_notifications(client: APIClient) -> None:
    token = _register_and_auth(client, "student_reminder")
    expert_client = APIClient()
    expert_token = _register_and_auth(expert_client, "expert_reminder", role="expert")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    objective = client.post(
        "/api/objectives/",
        {"title": "Reminder Goal", "description": "desc", "suggested_by": "ai", "status": "active"},
        format="json",
    )
    objective_id = objective.json()["id"]
    task = client.post(
        f"/api/objectives/{objective_id}/tasks/",
        {"title": "Implement API", "description": "build endpoint", "order": 1, "metadata": {"complexity": 1}},
        format="json",
    )
    task_id = task.json()["id"]
    student = User.objects.get(username="student_reminder")
    Session.objects.create(
        student=student,
        task_id=task_id,
        scheduled_start=timezone.now() + timedelta(minutes=10),
        scheduled_end=timezone.now() + timedelta(minutes=40),
        duration_minutes=30,
    )

    experts = client.get("/api/experts/?search=expert").json()
    assign = client.post("/api/assignments/request/", {"expert_id": experts[0]["user_id"]}, format="json")
    expert_client.credentials(HTTP_AUTHORIZATION=f"Bearer {expert_token}")
    expert_client.post(f"/api/trainer/assignments/{assign.json()['id']}/accept/", {}, format="json")

    result = send_reminder_notifications_task()
    assert result["sent"] >= 1
    notifications = client.get("/api/notifications/")
    assert notifications.status_code == 200
    assert any(item["type"] in {"session_reminder", "inactivity", "assignment_expiry", "streak"} for item in notifications.json())
