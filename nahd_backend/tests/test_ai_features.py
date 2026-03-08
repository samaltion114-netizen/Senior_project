"""Unit tests for standalone AI feature APIs."""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import EmailVerificationToken, PasswordResetToken

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
def test_time_estimate_endpoint(client: APIClient) -> None:
    token = _register_and_auth(client, "s_est")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    resp = client.post(
        "/api/ai/time-estimate/",
        {"title": "Implement a classifier", "description": "Build model and evaluate", "metadata": {"complexity": 2}},
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["estimated_minutes"] > 0
    assert 0 <= body["confidence"] <= 1


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
