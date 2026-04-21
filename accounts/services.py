"""Service helpers for notifications and gamification."""
from __future__ import annotations

from django.utils import timezone

from accounts.models import Badge, Notification, User, UserActivityLog, UserBadge


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
    return Notification.objects.create(
        user=user,
        type=type,
        title=title,
        message=message,
        related_id=related_id,
        metadata=metadata or {},
    )


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
