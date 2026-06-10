"""Shared operator alerts for background job failures."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.account import Account, AccountRole
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)


def notify_active_admins(
    db: Session,
    *,
    title: str,
    message: str,
    notification_type: str,
    url: str = "/admin",
) -> int:
    """Persist inbox-only alerts for all active admin operators."""
    admins = (
        db.query(Account)
        .filter(
            Account.role == AccountRole.ADMIN,
            Account.is_active == True,  # noqa: E712
        )
        .all()
    )
    if not admins:
        logger.warning("No active admin accounts available for job alert %s", notification_type)
        return 0

    notification_service = NotificationService(db)
    for admin in admins:
        notification_service.send_inbox_notification(
            account_id=admin.id,
            title=title,
            message=message,
            notification_type=notification_type,
            url=url,
        )
    return len(admins)
