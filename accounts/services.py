"""Service helpers for notifications and gamification."""
from __future__ import annotations

from typing import Any

from django.utils import timezone

from accounts.models import Badge, Notification, User, UserActivityLog, UserBadge

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
except Exception:  # pragma: no cover - optional dependency
    firebase_admin = None
    credentials = None
    messaging = None


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
    send_push_notification(user=user, title=title, body=message, data={"type": type, "related_id": str(related_id or "")})
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


def _firebase_ready() -> bool:
    return firebase_admin is not None


def send_push_notification(*, user: User, title: str, body: str, data: dict[str, str] | None = None) -> dict[str, Any]:
    """Send FCM push when configured, otherwise no-op with a mock payload."""
    if not user.fcm_token:
        return {"sent": False, "reason": "no_fcm_token"}
    if not _firebase_ready():
        print(f"[push:mock] user={user.id} title={title} body={body}")
        return {"sent": False, "reason": "firebase_not_configured"}
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
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
