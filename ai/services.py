"""AI services abstraction layer for Nahd."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import lru_cache
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


@lru_cache(maxsize=1)
def load_task_time_dataset() -> list[dict[str, Any]]:
    """Load the synthetic task-time dataset used by the backend estimator."""
    path = settings.AI_TASK_TIME_DATASET
    if not path or not os.path.exists(path):
        return []
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                rows.append(
                    {
                        "specialty": sanitize_text(row["specialty"]).lower(),
                        "task_type": sanitize_text(row["task_type"]).lower(),
                        "task_size": int(float(row["task_size"])),
                        "difficulty": int(float(row["difficulty"])),
                        "user_level": int(float(row["user_level"])),
                        "actual_minutes": int(float(row["actual_minutes"])),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
    return rows


def normalize_specialty(payload: dict[str, Any]) -> str:
    """Infer dataset specialty from explicit metadata or task text."""
    metadata = payload.get("metadata", {}) or {}
    specialty = str(payload.get("specialty") or metadata.get("specialty") or "").strip()
    if specialty:
        return specialty.lower()
    text = f"{payload.get('title', '')} {payload.get('description', '')}".lower()
    if any(token in text for token in ["network", "protocol", "security", "router"]):
        return "computer networks"
    if any(token in text for token in ["ai", "model", "ml", "classifier", "training"]):
        return "artificial intelligence"
    return "software engineering"


def normalize_task_type(payload: dict[str, Any]) -> str:
    """Map API payloads to dataset task-type labels."""
    metadata = payload.get("metadata", {}) or {}
    explicit = str(payload.get("task_type") or payload.get("type") or metadata.get("task_type") or "").strip()
    if explicit:
        return explicit.lower()
    text = f"{payload.get('title', '')} {payload.get('description', '')}".lower()
    if any(token in text for token in ["document", "readme", "docs", "documentation"]):
        return "reading documentation"
    if any(token in text for token in ["review", "audit"]):
        return "code review"
    if any(token in text for token in ["train", "classifier", "model"]):
        return "model training"
    if any(token in text for token in ["network", "protocol"]):
        return "reading protocols"
    return "writing code"


def normalize_task_size(payload: dict[str, Any]) -> int:
    """Convert API task-size representations to the numeric dataset scale."""
    metadata = payload.get("metadata", {}) or {}
    raw = payload.get("task_size", metadata.get("task_size"))
    if isinstance(raw, (int, float)):
        return max(1, int(raw))
    if isinstance(raw, str) and raw.strip():
        lowered = raw.strip().lower()
        if lowered.isdigit():
            return max(1, int(lowered))
        return {"small": 5, "medium": 12, "large": 20}.get(lowered, 10)
    words = len(re.findall(r"\w+", f"{payload.get('title', '')} {payload.get('description', '')}"))
    return max(1, min(24, math.ceil(words / 6) or 1))


def normalize_difficulty(payload: dict[str, Any]) -> int:
    """Convert difficulty fields to the dataset's numeric 1-3 scale."""
    metadata = payload.get("metadata", {}) or {}
    raw = payload.get("difficulty_level", metadata.get("difficulty"))
    if isinstance(raw, (int, float)):
        return min(3, max(1, int(raw)))
    if isinstance(raw, str) and raw.strip():
        return {"easy": 1, "medium": 2, "hard": 3}.get(raw.strip().lower(), 2)
    complexity = metadata.get("complexity")
    if isinstance(complexity, (int, float)):
        return min(3, max(1, int(complexity)))
    return 2


def normalize_user_level(payload: dict[str, Any]) -> int:
    """Convert user-level representations to the dataset's numeric 1-3 scale."""
    metadata = payload.get("metadata", {}) or {}
    raw = payload.get("user_level", metadata.get("user_level"))
    if isinstance(raw, (int, float)):
        return min(3, max(1, int(raw)))
    if isinstance(raw, str) and raw.strip():
        return {
            "beginner": 1,
            "intermediate": 2,
            "advanced": 3,
        }.get(raw.strip().lower(), 2)
    return 2


def dataset_time_estimate(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Estimate task duration from the synthetic CSV using nearest-neighbor scoring."""
    dataset = load_task_time_dataset()
    if not dataset:
        return None

    specialty = normalize_specialty(payload)
    task_type = normalize_task_type(payload)
    task_size = normalize_task_size(payload)
    difficulty = normalize_difficulty(payload)
    user_level = normalize_user_level(payload)

    ranked: list[tuple[float, dict[str, Any]]] = []
    for row in dataset:
        score = 0.0
        if row["specialty"] == specialty:
            score += 6.0
        if row["task_type"] == task_type:
            score += 5.0
        score += max(0.0, 3.0 - abs(row["difficulty"] - difficulty) * 1.5)
        score += max(0.0, 3.0 - abs(row["user_level"] - user_level) * 1.5)
        score += max(0.0, 4.0 - abs(row["task_size"] - task_size) / 4.0)
        if score > 0:
            ranked.append((score, row))

    if not ranked:
        return None

    ranked.sort(key=lambda item: item[0], reverse=True)
    top = ranked[: min(15, len(ranked))]
    total_weight = sum(score for score, _ in top) or 1.0
    weighted_minutes = sum(score * row["actual_minutes"] for score, row in top) / total_weight
    confidence = min(0.97, 0.55 + (top[0][0] / 21.0) * 0.4)
    return {
        "estimated_minutes": int(round(weighted_minutes)),
        "confidence": round(confidence, 2),
        "source": "informatics_task_times_synthetic_csv",
        "features": {
            "specialty": specialty,
            "task_type": task_type,
            "task_size": task_size,
            "difficulty": difficulty,
            "user_level": user_level,
            "matched_rows": len(top),
        },
    }


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

    def _goal_is_clear(self, objective_title: str) -> bool:
        cleaned = sanitize_text(objective_title)
        if len(cleaned) < 4:
            return False
        tokens = re.findall(r"[A-Za-z0-9]+", cleaned)
        alpha_tokens = [token for token in tokens if re.search(r"[A-Za-z]", token)]
        if not alpha_tokens:
            return False
        if len(alpha_tokens) == 1:
            token = alpha_tokens[0]
            if token.lower() in {"goal", "project", "portfolio", "plan", "roadmap"}:
                return True
            if len(token) < 4:
                return False
            return bool(re.search(r"[aeiou]", token.lower()) or token.isupper())
        meaningful = [token for token in alpha_tokens if len(token) >= 4 and (re.search(r"[aeiou]", token.lower()) or token.isupper())]
        return bool(meaningful)

    def _goal_domain(self, objective_title: str) -> str:
        text = sanitize_text(objective_title).lower()
        if any(token in text for token in ["backend", "django", "api", "server", "database", "auth", "deployment"]):
            return "backend"
        if any(token in text for token in ["ai", "ml", "model", "classifier", "training", "data"]):
            return "ai"
        if any(token in text for token in ["law", "legal", "contract", "compliance", "draft"]):
            return "legal"
        if any(token in text for token in ["frontend", "ui", "design", "ux", "portfolio"]):
            return "product"
        return "general"

    def _goal_task_labels(self, objective_title: str, count: int) -> list[str]:
        subject = sanitize_text(objective_title)
        domain = self._goal_domain(subject)
        if domain == "backend":
            templates = [
                f"Map the architecture for {subject}",
                f"Implement the core backend flow for {subject}",
                f"Add validation and authentication for {subject}",
                f"Write tests and fix edge cases for {subject}",
                f"Prepare deployment notes and portfolio evidence for {subject}",
                f"Refine observability and documentation for {subject}",
                f"Review feedback and improve {subject}",
            ]
        elif domain == "ai":
            templates = [
                f"Define the dataset and success criteria for {subject}",
                f"Build the model pipeline for {subject}",
                f"Evaluate model quality for {subject}",
                f"Tune the results and capture experiments for {subject}",
                f"Document the final AI workflow for {subject}",
                f"Prepare portfolio evidence for {subject}",
                f"Review feedback and improve {subject}",
            ]
        elif domain == "legal":
            templates = [
                f"Review the source material for {subject}",
                f"Draft the core analysis for {subject}",
                f"Check compliance and risks for {subject}",
                f"Refine recommendations for {subject}",
                f"Prepare the final submission for {subject}",
                f"Summarize the outcome of {subject}",
                f"Review feedback and improve {subject}",
            ]
        elif domain == "product":
            templates = [
                f"Research the scope of {subject}",
                f"Design the first deliverable for {subject}",
                f"Build and test the portfolio output for {subject}",
                f"Refine the presentation for {subject}",
                f"Prepare the final portfolio entry for {subject}",
                f"Review feedback and improve {subject}",
                f"Summarize lessons learned from {subject}",
            ]
        else:
            templates = [
                f"Research the scope of {subject}",
                f"Build the first deliverable for {subject}",
                f"Test and refine {subject}",
                f"Document the outcome of {subject}",
                f"Prepare the final portfolio entry for {subject}",
                f"Review feedback and improve {subject}",
                f"Summarize lessons learned from {subject}",
            ]
        return templates[: max(1, min(count, 10))]

    def validate_or_generate_tasks(
        self,
        *,
        objective_title: str,
        task_name: str = "",
        user_level: str = "intermediate",
        count: int = 5,
    ) -> dict[str, Any]:
        """Validate one task against an objective or generate tasks with resources."""
        objective_lower = objective_title.lower()

        def infer_task(task_label: str, position: int) -> dict[str, Any]:
            label = sanitize_text(task_label)
            lowered = label.lower()
            if any(token in lowered for token in ["read", "document", "protocol"]):
                task_type = "reading"
                youtube_suffix = "documentation"
            elif any(token in lowered for token in ["review", "audit"]):
                task_type = "review"
                youtube_suffix = "review"
            elif any(token in lowered for token in ["watch", "video"]):
                task_type = "watching"
                youtube_suffix = "tutorial"
            elif any(token in lowered for token in ["exercise", "practice"]):
                task_type = "exercise"
                youtube_suffix = "practice"
            else:
                task_type = "coding"
                youtube_suffix = "implementation"

            difficulty = "easy" if position == 1 else "medium" if position < max(count, 3) else "hard"
            size = "small" if position == 1 else "medium" if position < max(count, 4) else "large"
            slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-") or f"task-{position}"
            return {
                "task_name": label,
                "task_type": task_type,
                "task_size": size,
                "difficulty": difficulty,
                "youtube_link_ar": f"https://youtube.com/results?search_query={slug}+arabic+{youtube_suffix}",
                "youtube_link_en": f"https://youtube.com/results?search_query={slug}+english+{youtube_suffix}",
                "xp_reward": {"easy": 10, "medium": 20, "hard": 40}[difficulty],
                "type": "standard",
                "user_level": user_level,
            }

        if task_name:
            task_lower = task_name.lower()
            objective_is_legal = any(token in objective_lower for token in ["law", "legal", "contract"])
            task_is_legal = any(token in task_lower for token in ["law", "legal", "contract"])
            objective_is_technical = any(
                token in objective_lower for token in ["software", "backend", "django", "api", "network", "ai", "training"]
            )
            task_is_technical = any(
                token in task_lower for token in ["implement", "build", "code", "api", "model", "network", "docs", "classifier", "test"]
            )
            strong_mismatch = (objective_is_legal and task_is_technical) or (objective_is_technical and task_is_legal)
            is_valid = (
                any(token in objective_lower for token in task_lower.split()[:2])
                or any(token in task_lower for token in objective_lower.split()[:3])
                or (objective_is_legal and task_is_legal)
                or (objective_is_technical and task_is_technical)
                or not strong_mismatch
                or not task_lower.strip()
            )
            tasks = [infer_task(task_name, 1)] if is_valid else []
            return {
                "status": "valid" if is_valid else "invalid",
                "is_valid": is_valid,
                "message": None if is_valid else "Task is not relevant to the selected objective.",
                "tasks": tasks,
            }

        if not self._goal_is_clear(objective_title):
            return {
                "status": "invalid",
                "is_valid": False,
                "message": "Goal is not clear enough. Please enter a specific learning or career goal.",
                "tasks": [],
            }

        seed = self._goal_task_labels(objective_title, count)
        generated = [infer_task(name, idx) for idx, name in enumerate(seed, start=1)]
        return {"status": "valid", "is_valid": True, "message": None, "tasks": generated}

    def generate_linkedin_post(
        self,
        *,
        objective_title: str,
        completed_tasks: list[str],
        student_name: str = "",
    ) -> dict[str, Any]:
        """Build a LinkedIn-ready portfolio post from a completed objective."""
        title = sanitize_text(objective_title)
        tasks = [sanitize_text(task) for task in completed_tasks if sanitize_text(task)]
        domain = self._goal_domain(title)
        subject = f"{title}" if title else "my goal"
        intro = f"I am proud to share that I completed '{subject}'."
        if student_name:
            intro = f"{sanitize_text(student_name)} has completed '{subject}'."
        if tasks:
            highlights = ", ".join(tasks[:5])
            body = f"Key milestones included: {highlights}."
        else:
            body = "The journey focused on steady progress, execution, and learning."
        closing = "Grateful for the support and ready for the next challenge."
        hashtags_map = {
            "backend": ["#BackendDevelopment", "#Django", "#APIs", "#Portfolio"],
            "ai": ["#ArtificialIntelligence", "#MachineLearning", "#Portfolio", "#Learning"],
            "legal": ["#LegalTech", "#ProfessionalGrowth", "#Portfolio", "#Learning"],
            "product": ["#ProductDesign", "#Portfolio", "#Learning", "#CareerGrowth"],
            "general": ["#Portfolio", "#LearningJourney", "#CareerGrowth", "#LinkedIn"],
        }
        hashtags = hashtags_map.get(domain, hashtags_map["general"])
        text = " ".join([intro, body, closing, " ".join(hashtags)]).strip()
        return {
            "linkedin_generated_text": text,
            "hashtags": hashtags,
            "domain": domain,
            "source": "mock",
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
        dataset_result = dataset_time_estimate(task_payload)
        if dataset_result is not None:
            return dataset_result
        text = f"{task_payload.get('title', '')} {task_payload.get('description', '')}"
        words = len(re.findall(r"\w+", text))
        complexity = float(task_payload.get("metadata", {}).get("complexity", 1))
        predicted = int(max(20, min(240, words * 2 + complexity * 15)))
        confidence = round(min(0.95, 0.55 + min(words / 200, 0.35)), 2)
        return {"estimated_minutes": predicted, "confidence": confidence, "source": "heuristic_fallback"}

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

    def generate_mindmap(self, topic: str, context: str = "", max_branches: int = 6) -> dict[str, Any]:
        base = sanitize_text(topic)
        context_text = sanitize_text(context)
        hints = re.findall(r"[A-Za-z0-9_]+", context_text)[: max(0, max_branches - 1)]
        default_branches = ["Overview", "Requirements", "Architecture", "Implementation", "Testing", "Deployment"]
        merged = []
        for label in hints + default_branches:
            if label not in merged:
                merged.append(label)
            if len(merged) >= max_branches:
                break
        return {
            "topic": base,
            "branches": [{"title": title, "children": []} for title in merged],
            "provider": "mock",
            "model_loaded": getattr(self, "model_info", {"loaded": False}),
        }


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

    def _extract_json_object(self, text: str) -> dict[str, Any] | None:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        candidate = text[start : end + 1]
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    def _try_repair_json(self, text: str) -> dict[str, Any] | None:
        candidate = text.strip()
        if not candidate:
            return None
        if not candidate.startswith("{"):
            first = candidate.find("{")
            if first >= 0:
                candidate = candidate[first:]
        if not candidate.endswith("}"):
            last = candidate.rfind("}")
            if last >= 0:
                candidate = candidate[: last + 1]
        if candidate.count("{") > candidate.count("}"):
            candidate += "}" * (candidate.count("{") - candidate.count("}"))
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    def _normalize_mindmap(self, payload: dict[str, Any], topic: str, max_branches: int) -> dict[str, Any]:
        branches = payload.get("branches", [])
        if not isinstance(branches, list):
            branches = []
        normalized = []
        for branch in branches[:max_branches]:
            if isinstance(branch, dict):
                title = sanitize_text(str(branch.get("title", "")))
                if not title:
                    continue
                children = branch.get("children", [])
                children = children if isinstance(children, list) else []
                normalized.append({"title": title, "children": children})
            elif isinstance(branch, str):
                normalized.append({"title": sanitize_text(branch), "children": []})
        return {
            "topic": sanitize_text(str(payload.get("topic") or topic)),
            "branches": normalized,
        }

    def _generate_mindmap_via_local_runtime(self, topic: str, context: str, max_branches: int) -> dict[str, Any] | None:
        if not self.model_info.get("loaded"):
            return None
        grammar = r'''
root ::= "{" ws "\"topic\"" ws ":" ws string ws "," ws "\"branches\"" ws ":" ws "[" ws branchlist ws "]" ws "}"
branchlist ::= branch | branch ws "," ws branchlist
branch ::= "{" ws "\"title\"" ws ":" ws string ws "," ws "\"children\"" ws ":" ws "[]" ws "}"
string ::= "\"" chars "\""
chars ::= "" | char chars
char ::= [^"\\\n] | "\\" escape
escape ::= ["\\/bfnrt] | "u" hex hex hex hex
hex ::= [0-9a-fA-F]
ws ::= [ \t\n\r]*
'''
        prompt = (
            "You generate a mindmap JSON. "
            "Return one JSON object with keys topic and branches only. "
            "Each branch must be {\"title\": string, \"children\": []}. "
            f"Use concise labels and keep branches around {max_branches}. "
            f"Topic: {topic}\nContext: {context}"
        )
        request_body = {
            "prompt": prompt,
            "n_predict": 300,
            "temperature": 0.0,
            "top_p": 0.9,
            "top_k": 40,
            "repeat_penalty": 1.05,
            "grammar": grammar,
            "stop": ["\n\n", "```", "</json>"],
        }
        attempts = [
            request_body,
            {
                **request_body,
                "temperature": 0.0,
                "top_p": 0.2,
                "top_k": 20,
                "n_predict": 220,
            },
        ]
        for attempt in attempts:
            req = urllib.request.Request(
                f"{settings.AI_LOCAL_INFERENCE_URL.rstrip('/')}/completion",
                data=json.dumps(attempt).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=settings.AI_LOCAL_INFERENCE_TIMEOUT) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                content = str(payload.get("content", ""))
                parsed = self._extract_json_object(content)
                if parsed is None:
                    parsed = self._try_repair_json(content)
                if parsed is None:
                    continue
                normalized = self._normalize_mindmap(parsed, topic=topic, max_branches=max_branches)
                if not normalized.get("branches"):
                    continue
                return {
                    **normalized,
                    "provider": "local",
                    "model_loaded": self.model_info,
                    "inference": "gguf_runtime",
                }
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, ValueError):
                continue
        return None

    def generate_mindmap(self, topic: str, context: str = "", max_branches: int = 6) -> dict[str, Any]:
        runtime_result = self._generate_mindmap_via_local_runtime(topic=topic, context=context, max_branches=max_branches)
        if runtime_result is not None:
            return runtime_result
        fallback = super().generate_mindmap(topic=topic, context=context, max_branches=max_branches)
        fallback["inference"] = "fallback_mock"
        return fallback


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
    allowed_ext = {".pt", ".pth", ".bin", ".onnx", ".safetensors", ".pkl", ".joblib", ".gguf"}
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
