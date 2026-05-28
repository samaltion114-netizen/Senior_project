"""Service helpers for notifications and gamification."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from django.conf import settings
from django.db.models import Avg
from django.utils import timezone

from accounts.models import Badge, ExpertRating, Notification, User, UserActivityLog, UserBadge

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
except Exception:  # pragma: no cover - optional dependency
    firebase_admin = None
    credentials = None
    messaging = None


def _firebase_credentials_path() -> Path | None:
    """Return the configured Firebase service-account file if it exists."""
    configured_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "") or str(
        settings.BASE_DIR / "firebase-credentials.json"
    )
    path = Path(configured_path).expanduser()
    if not path.is_absolute():
        path = Path(settings.BASE_DIR) / path
    return path if path.is_file() else None


def create_notification(
    *,
    user: User,
    type: str,
    title: str,
    message: str,
    related_id: int | None = None,
    metadata: dict | None = None,
) -> Notification:
    """Persist one notification record for API consumption."""
    notification = Notification.objects.create(
        user=user,
        type=type,
        title=title,
        message=message,
        related_id=related_id,
        metadata=metadata or {},
    )
    send_push_notification(
        user=user,
        title=title,
        body=message,
        data={"type": type, "related_id": str(related_id or "")},
    )
    return notification


def log_user_activity(*, user: User, event_type: str, related_id: int | None = None, metadata: dict | None = None) -> UserActivityLog:
    """Append one user activity event."""
    return UserActivityLog.objects.create(user=user, event_type=event_type, related_id=related_id, metadata=metadata or {})


def award_badge_if_eligible(user: User) -> str | None:
    """Award one simple badge based on current XP/streak milestones."""
    badge_def: tuple[str, str, str] | None = None
    if user.current_streak >= 7:
        badge_def = ("7 Day Streak", "7-day-streak", "Maintain a seven-day streak.")
    elif user.total_xp >= 100:
        badge_def = ("100 XP", "100-xp", "Earn one hundred XP.")

    if badge_def is None:
        return None

    badge, _ = Badge.objects.get_or_create(
        slug=badge_def[1],
        defaults={"name": badge_def[0], "condition": badge_def[2]},
    )
    award, created = UserBadge.objects.get_or_create(user=user, badge=badge)
    if not created:
        return None
    award.awarded_at = timezone.now()
    award.save(update_fields=["awarded_at"])
    return badge.slug


def refresh_expert_rating_summary(*, expert: User) -> dict[str, Any]:
    """Recalculate the expert's average rating and apply demotion rules."""
    profile = expert.expert_profile
    aggregate = ExpertRating.objects.filter(expert=expert).aggregate(average=Avg("rating"))
    average_raw = aggregate["average"] or 0
    average_rating = round(float(average_raw), 2)
    previous_level = profile.expertise_level
    current_level = previous_level

    if average_rating < 2.0 and previous_level == "certified":
        current_level = "junior"
    elif average_rating < 3.0 and previous_level == "senior":
        current_level = "certified"

    update_fields = ["average_rating"]
    profile.average_rating = average_rating
    if current_level != previous_level:
        profile.expertise_level = current_level
        update_fields.append("expertise_level")
    profile.save(update_fields=update_fields)
    return {
        "average_rating": average_rating,
        "previous_level": previous_level,
        "current_level": current_level,
        "level_changed": current_level != previous_level,
    }


def _firebase_ready() -> bool:
    return firebase_admin is not None and credentials is not None and messaging is not None


def _ensure_firebase_app() -> bool:
    """Initialize Firebase using the bundled service-account file."""
    if not _firebase_ready():
        return False
    if firebase_admin._apps:
        return True
    creds_path = _firebase_credentials_path()
    if creds_path is None:
        return False
    firebase_admin.initialize_app(credentials.Certificate(str(creds_path)))
    return True


def send_push_notification(*, user: User, title: str, body: str, data: dict[str, str] | None = None) -> dict[str, Any]:
    """Send FCM push when configured, otherwise no-op with a mock payload."""
    if not user.fcm_token:
        return {"sent": False, "reason": "no_fcm_token"}
    if not _ensure_firebase_app():
        print(f"[push:mock] user={user.id} title={title} body={body}")
        return {"sent": False, "reason": "firebase_credentials_missing"}
    try:
        message = messaging.Message(
            token=user.fcm_token,
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
        )
        message_id = messaging.send(message)
        return {"sent": True, "message_id": message_id}
    except Exception as exc:  # pragma: no cover - external integration
        print(f"[push:error] user={user.id} error={exc}")
        return {"sent": False, "reason": str(exc)}
