"""AI services abstraction layer for Nahd."""
from __future__ import annotations

import hashlib
import math
import os
import re
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone

from ai.models import AIModelWeight

def sanitize_text(value: str) -> str:
    """Small sanitizer for user-provided free text."""
    return re.sub(r"\s+", " ", value.strip())


def hash_text(value: str) -> str:
    """Create deterministic sha256 digest for event logging."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def text_to_embedding(text: str) -> dict[str, float]:
    """Simple bag-of-words embedding used by deterministic mock services."""
    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    counts = Counter(tokens)
    total = sum(counts.values()) or 1
    return {token: count / total for token, count in counts.items()}


def cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity on sparse dict vectors."""
    keys = set(a.keys()) | set(b.keys())
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if not na or not nb:
        return 0.0
    return dot / (na * nb)


class InterviewAgent(ABC):
    @abstractmethod
    def process_message(self, history: list[dict[str, str]], message: str) -> dict[str, Any]:
        """Return response message and optional suggested objective."""


class ObjectiveScorer(ABC):
    @abstractmethod
    def score_objective(self, objective_title: str, context: dict[str, Any]) -> float:
        """Score objective relevance."""


class TimeEstimator(ABC):
    @abstractmethod
    def estimate_time(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        """Return estimated minutes and confidence."""


class ScheduleOptimizer(ABC):
    @abstractmethod
    def optimize_schedule(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Return optimized session plan."""


class ProofAnalyzer(ABC):
    @abstractmethod
    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return proof analysis with similarity and decision."""


class ChallengeGenerator(ABC):
    @abstractmethod
    def generate(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate 1-3 adaptive micro challenges."""


@dataclass
class MockAIService(InterviewAgent, ObjectiveScorer, TimeEstimator, ScheduleOptimizer, ProofAnalyzer, ChallengeGenerator):
    """Deterministic local implementation for tests and development."""

    confidence_threshold: float = 0.75

    def _goal_from_message(self, message: str) -> dict[str, str]:
        msg = message.lower()
        if "backend" in msg or "django" in msg:
            return {
                "title": "Backend Internship Readiness (Django/REST)",
                "description": "Build one portfolio backend with auth, CRUD, and tests in 8 weeks.",
            }
        if "law" in msg or "contract" in msg:
            return {
                "title": "Commercial Legal Assistant Readiness",
                "description": "Prepare a contract-focused portfolio with drafting and review exercises.",
            }
        return {
            "title": "Software Training Foundation",
            "description": "Complete fundamentals in software, networks, and AI track selection.",
        }

    def process_message(self, history: list[dict[str, str]], message: str) -> dict[str, Any]:
        normalized = sanitize_text(message)
        completed = len(history) >= 3 or any(k in normalized.lower() for k in ["goal", "training", "internship", "ai"])
        objective = self._goal_from_message(normalized) if completed else None
        reply = "Thanks. I noted your priorities. " + (
            "Interview is complete; I prepared one recommended objective." if completed else "Please share your weekly hours and preferred track."
        )
        return {"reply": reply, "completed": completed, "suggested_objective": objective, "facts": {"last_message": normalized}}

    def score_objective(self, objective_title: str, context: dict[str, Any]) -> float:
        student_goal = context.get("goal_text", "")
        return round(cosine_similarity(text_to_embedding(objective_title), text_to_embedding(student_goal)), 4)

    def estimate_time(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        text = f"{task_payload.get('title', '')} {task_payload.get('description', '')}"
        words = len(re.findall(r"\w+", text))
        complexity = float(task_payload.get("metadata", {}).get("complexity", 1))
        predicted = int(max(20, min(240, words * 2 + complexity * 15)))
        confidence = round(min(0.95, 0.55 + min(words / 200, 0.35)), 2)
        return {"estimated_minutes": predicted, "confidence": confidence}

    def optimize_schedule(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        availability = payload["weekly_availability"]
        task_blocks = payload["task_blocks"]
        max_daily = int(payload.get("max_daily_minutes", 120))
        break_minutes = int(payload.get("break_minutes", 10))
        start_date = datetime.fromisoformat(payload.get("start_date") or timezone.now().date().isoformat()).date()
        existing = payload.get("existing_sessions", [])

        occupied: dict[date, list[tuple[datetime, datetime]]] = defaultdict(list)
        for s in existing:
            occupied_dt_start = datetime.fromisoformat(s["scheduled_start"])
            occupied_dt_end = datetime.fromisoformat(s["scheduled_end"])
            occupied[occupied_dt_start.date()].append((occupied_dt_start, occupied_dt_end))

        sessions: list[dict[str, Any]] = []
        remaining = list(task_blocks)
        for day_offset in range(0, 28):
            if not remaining:
                break
            current_date = start_date + timedelta(days=day_offset)
            day_key = current_date.strftime("%A").lower()
            slots = availability.get(day_key, [])
            if not slots:
                continue
            daily_used = 0
            for slot in slots:
                slot_start = timezone.make_aware(datetime.combine(current_date, time.fromisoformat(slot["start"])))
                slot_end = timezone.make_aware(datetime.combine(current_date, time.fromisoformat(slot["end"])))
                cursor = slot_start
                while remaining and cursor < slot_end and daily_used < max_daily:
                    block = remaining[0]
                    duration = int(block["duration_minutes"])
                    if duration + daily_used > max_daily:
                        break
                    candidate_end = cursor + timedelta(minutes=duration)
                    if candidate_end > slot_end:
                        break
                    overlap = any(
                        not (candidate_end <= occ_start or cursor >= occ_end) for occ_start, occ_end in occupied[current_date]
                    )
                    if overlap:
                        cursor += timedelta(minutes=10)
                        continue
                    sessions.append(
                        {
                            "task_id": block["task_id"],
                            "scheduled_start": cursor.isoformat(),
                            "scheduled_end": candidate_end.isoformat(),
                            "duration_minutes": duration,
                            "status": "planned",
                        }
                    )
                    occupied[current_date].append((cursor, candidate_end))
                    daily_used += duration
                    cursor = candidate_end + timedelta(minutes=break_minutes)
                    remaining.pop(0)
        return sessions

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        task_text = sanitize_text(payload.get("task_description", ""))
        explanation = sanitize_text(payload.get("explanation_text", ""))
        image_stub = sanitize_text(payload.get("image_caption", ""))
        quality = payload.get("quality", {})

        task_emb = text_to_embedding(task_text)
        expl_emb = text_to_embedding(explanation)
        cap_emb = text_to_embedding(image_stub)
        text_score = cosine_similarity(task_emb, expl_emb)
        image_score = cosine_similarity(task_emb, cap_emb)
        score = round((text_score * 0.6 + image_score * 0.4), 3)
        matches = score >= self.confidence_threshold

        suspected_issue = None if matches else "Mismatch between expected output and submitted proof."
        if quality.get("quality_score", 1.0) < 0.6:
            suspected_issue = "Proof image quality is low; evidence may be unclear."

        evidence = "Task and explanation align." if matches else "Evidence does not sufficiently match task expectations."
        return {
            "matches_expected": matches,
            "evidence": evidence,
            "suspected_issue": suspected_issue,
            "confidence_score": score,
            "quality": quality,
            "summary": f"Similarity score={score:.2f}, threshold={self.confidence_threshold:.2f}",
            "task_embedding": task_emb,
            "explanation_embedding": expl_emb,
        }

    def generate_programming_question(self, suspected_issue: str, proof_context: str) -> dict[str, Any]:
        title = "Investigate proof mismatch in submitted task"
        description = (
            f"Observed issue: {suspected_issue}\n"
            f"Context: {proof_context}\n"
            "Steps: 1) Reproduce current output. 2) Compare expected vs actual. 3) Patch and retest."
        )
        fixes = [
            {"title": "Reproduce", "description": "Run the task flow and capture exact error/output.", "priority": "high"},
            {"title": "Compare outputs", "description": "Diff expected artifact with current result.", "priority": "high"},
            {"title": "Apply fix", "description": "Implement minimal corrective change and rerun tests.", "priority": "medium"},
        ]
        return {"title": title, "description": description, "severity": "medium", "suggested_fixes": fixes}

    def generate(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        open_issues = payload.get("open_issues", [])
        if open_issues:
            base = open_issues[0]
            return [
                {
                    "text": f"Micro-task: verify one edge case for '{base}' and document result in 5 lines.",
                    "difficulty": "easy",
                    "estimated_minutes": 15,
                }
            ]
        return [
            {"text": "Build a tiny API endpoint and add one test.", "difficulty": "easy", "estimated_minutes": 20},
            {"text": "Refactor one serializer and run test suite.", "difficulty": "medium", "estimated_minutes": 25},
        ]

    def generate_tagged_checklist(self, text: str, domain: str = "informatics") -> dict[str, Any]:
        text_l = text.lower()
        if domain == "law":
            candidates = [
                ("termination", 0.89 if "فسخ" in text or "termination" in text_l else 0.55),
                ("breach", 0.84 if "breach" in text_l or "إخلال" in text else 0.53),
                ("notice", 0.78 if "notice" in text_l or "إشعار" in text else 0.52),
                ("liability", 0.67),
                ("damages", 0.62),
            ]
            checklist = [
                "Identify contract type and governing jurisdiction.",
                "Locate termination and notice clauses.",
                "Assess whether delay qualifies as material breach.",
                "Check cure period and formal notice requirements.",
                "Evaluate liability and damages limitations.",
                "Summarize educational next steps before any action.",
            ]
            refs = ["https://www.law.cornell.edu/wex", "https://www.uncitral.org/"]
        else:
            candidates = [
                ("jwt", 0.92 if "jwt" in text_l else 0.6),
                ("authentication", 0.86 if "401" in text_l or "auth" in text_l else 0.59),
                ("drf", 0.8 if "drf" in text_l or "django rest" in text_l else 0.58),
                ("permissions", 0.71),
                ("headers", 0.65),
            ]
            checklist = [
                "Verify JWT token is issued and not expired.",
                "Confirm Authorization header uses 'Bearer <token>'.",
                "Check DRF authentication classes in settings and view.",
                "Validate user permissions and role flags.",
                "Inspect token signing key and clock skew.",
                "Retest endpoint with reproducible curl request.",
            ]
            refs = [
                "https://www.django-rest-framework.org/api-guide/authentication/",
                "https://django-rest-framework-simplejwt.readthedocs.io/",
                "https://owasp.org/www-project-api-security/",
            ]
        tags = [{"tag": t, "confidence": round(c, 2)} for t, c in sorted(candidates, key=lambda x: x[1], reverse=True)[:5]]
        return {"tags": tags, "checklist": checklist, "references": refs}

    def generate_daily_challenges(self, domain: str, level: str, minutes: int) -> list[dict[str, Any]]:
        prefix = "Legal" if domain == "law" else "Coding"
        return [
            {
                "title": f"{prefix} Daily Challenge",
                "time_minutes": minutes,
                "requirements": f"Level: {level}. Complete one focused task.",
                "success_criteria": "Submit concise evidence of completion.",
                "hint": "Focus on one clear deliverable.",
            }
        ]


class OpenAIAdapter(MockAIService):
    """Example adapter shape for real providers; currently delegates to mock logic.

    TODO:
    - Inject OpenAI (or other) client using API keys from environment variables.
    - Replace `process_message` with LLM interview orchestration.
    - Replace `analyze` with vision + OCR + semantic matching pipeline.
    - Replace checklist/challenge generation methods with controlled prompting.
    """

    pass


class LocalWeightsAdapter(MockAIService):
    """Local model adapter for user-provided weight files.

    This adapter currently reuses deterministic fallback behavior and exposes
    selected weight metadata; replace TODO points with your model loading/inference.
    """

    def __init__(self, confidence_threshold: float, selected_model: AIModelWeight | None = None) -> None:
        super().__init__(confidence_threshold=confidence_threshold)
        self.selected_model = selected_model
        self.model_info = self._load_model_info(selected_model)

    def _load_model_info(self, selected_model: AIModelWeight | None) -> dict[str, Any]:
        if selected_model is None:
            return {"loaded": False, "reason": "no active model selected"}
        exists = os.path.exists(selected_model.weight_path)
        return {
            "loaded": exists,
            "name": selected_model.name,
            "capability": selected_model.capability,
            "weight_path": selected_model.weight_path,
            "provider": selected_model.provider,
            "reason": "ready" if exists else "weight path not found",
        }

    # TODO: Override inference methods to run your local model framework.


def get_selected_model(capability: str) -> AIModelWeight | None:
    """Resolve active model for specific capability with fallback to `all`."""
    selected = AIModelWeight.objects.filter(capability=capability, is_active=True).order_by("-updated_at").first()
    if selected:
        return selected
    return AIModelWeight.objects.filter(capability=AIModelWeight.CAPABILITY_ALL, is_active=True).order_by("-updated_at").first()


def list_weight_files() -> list[dict[str, str]]:
    """Discover local weight files from configured folder."""
    base_dir = settings.AI_WEIGHTS_DIR
    os.makedirs(base_dir, exist_ok=True)
    files: list[dict[str, str]] = []
    allowed_ext = {".pt", ".pth", ".bin", ".onnx", ".safetensors", ".pkl", ".joblib"}
    for root, _, filenames in os.walk(base_dir):
        for filename in filenames:
            _, ext = os.path.splitext(filename)
            if ext.lower() not in allowed_ext:
                continue
            full_path = os.path.join(root, filename)
            files.append({"name": filename, "path": os.path.abspath(full_path)})
    files.sort(key=lambda f: f["name"].lower())
    return files


def get_ai_service(capability: str = AIModelWeight.CAPABILITY_ALL) -> MockAIService | OpenAIAdapter | LocalWeightsAdapter:
    """Factory for AI provider with per-capability model selection."""
    selected_model = get_selected_model(capability)
    provider = (selected_model.provider if selected_model else settings.AI_PROVIDER).lower()
    if provider == "openai":
        return OpenAIAdapter(confidence_threshold=settings.PROOF_CONFIDENCE_THRESHOLD)
    if provider == "local":
        return LocalWeightsAdapter(confidence_threshold=settings.PROOF_CONFIDENCE_THRESHOLD, selected_model=selected_model)
    return MockAIService(confidence_threshold=settings.PROOF_CONFIDENCE_THRESHOLD)
