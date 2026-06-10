"""Push Notification Service.

Web push delivery is only available when VAPID credentials and the web push SDK
are actually configured. This module intentionally avoids mock success paths so
callers can react to real unavailability.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class PushNotificationUnavailableError(RuntimeError):
    """Raised when push delivery cannot run with the current configuration."""


class PushNotificationDeliveryError(RuntimeError):
    """Raised when push delivery fails after initialization."""


class NotificationType(str, Enum):
    NEW_REVIEW = "new_review"
    CONTENT_READY = "content_ready"
    APPROVAL_NEEDED = "approval_needed"
    WEEKLY_REPORT = "weekly_report"
    MISSED_CALL = "missed_call"
    NEW_MESSAGE = "new_message"
    PERFORMANCE_ALERT = "performance_alert"


@dataclass
class PushSubscription:
    """Web Push subscription data."""

    endpoint: str
    p256dh_key: str
    auth_key: str
    account_id: str
    device_type: str = "web"
    created_at: Optional[datetime] = None


@dataclass
class PushNotification:
    """Push notification payload."""

    title: str
    body: str
    icon: Optional[str] = None
    badge: Optional[str] = None
    image: Optional[str] = None
    url: Optional[str] = None
    tag: Optional[str] = None
    data: Optional[dict] = None


class PushNotificationService:
    """Service for sending push notifications."""

    def __init__(self):
        self.vapid_private_key = getattr(settings, "vapid_private_key", None)
        self.vapid_public_key = getattr(settings, "vapid_public_key", None)
        self.vapid_email = getattr(settings, "vapid_email", None) or "admin@localseooptimizer.com"

    def is_configured(self) -> bool:
        """Return whether the service has the credentials it needs to send."""
        return bool(self.vapid_private_key and self.vapid_public_key)

    def availability_reason(self) -> str:
        """Explain why delivery is unavailable, if it is."""
        missing = []
        if not self.vapid_private_key:
            missing.append("VAPID private key")
        if not self.vapid_public_key:
            missing.append("VAPID public key")
        return ", ".join(missing)

    async def send_web_push(
        self,
        subscription: PushSubscription,
        notification: PushNotification,
    ) -> bool:
        """Send a web push notification.

        Raises:
            PushNotificationUnavailableError: when the SDK or credentials are missing.
            PushNotificationDeliveryError: when the provider rejects delivery.
        """
        if not self.is_configured():
            raise PushNotificationUnavailableError(
                f"Push delivery is unavailable: {self.availability_reason() or 'push credentials are missing'}"
            )

        try:
            from pywebpush import webpush
        except ImportError as exc:
            raise PushNotificationUnavailableError(
                "Push delivery is unavailable: pywebpush is not installed."
            ) from exc

        payload = {
            "title": notification.title,
            "body": notification.body,
            "icon": notification.icon or "/icons/icon-192x192.png",
            "badge": notification.badge or "/icons/badge-72x72.png",
            "data": {
                "url": notification.url or "/dashboard",
                **(notification.data or {}),
            },
        }

        if notification.image:
            payload["image"] = notification.image

        if notification.tag:
            payload["tag"] = notification.tag

        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh_key,
                "auth": subscription.auth_key,
            },
        }

        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=self.vapid_private_key,
                vapid_claims={"sub": f"mailto:{self.vapid_email}"},
            )
            return True
        except Exception as exc:
            logger.error("Web push delivery failed for account %s: %s", subscription.account_id, exc)
            raise PushNotificationDeliveryError(f"Web push delivery failed: {exc}") from exc

    async def send_to_account(
        self,
        account_id: str,
        notification: PushNotification,
        db_session=None,
    ) -> int:
        """Send a push notification to every stored subscription for an account.

        Returns the number of successfully delivered pushes (0 if no subscriptions
        exist or all deliveries fail).

        Raises:
            PushNotificationUnavailableError: when VAPID credentials are missing.
        """
        if not self.is_configured():
            raise PushNotificationUnavailableError(
                f"Push delivery is unavailable: {self.availability_reason() or 'push credentials are missing'}"
            )

        if db_session is None:
            logger.warning(
                "send_to_account called for account %s without a db_session; "
                "cannot load subscriptions — returning 0",
                account_id,
            )
            return 0

        from app.models.notification import PushSubscriptionRecord
        import uuid as _uuid

        try:
            account_uuid = _uuid.UUID(account_id) if not isinstance(account_id, _uuid.UUID) else account_id
        except (ValueError, AttributeError):
            account_uuid = account_id

        subscriptions = (
            db_session.query(PushSubscriptionRecord)
            .filter(PushSubscriptionRecord.account_id == account_uuid)
            .all()
        )

        if not subscriptions:
            logger.debug("No push subscriptions found for account %s", account_id)
            return 0

        delivered = 0
        stale_endpoints: list[str] = []

        for sub in subscriptions:
            push_sub = PushSubscription(
                endpoint=sub.endpoint,
                p256dh_key=sub.p256dh_key,
                auth_key=sub.auth_key,
                account_id=account_id,
                device_type=sub.device_type,
            )
            try:
                await self.send_web_push(push_sub, notification)
                delivered += 1
            except PushNotificationDeliveryError as exc:
                error_str = str(exc)
                # HTTP 410 Gone means the subscription has expired; clean it up.
                if "410" in error_str or "expired" in error_str.lower():
                    stale_endpoints.append(sub.endpoint)
                logger.warning(
                    "Push delivery failed for account %s endpoint %s: %s",
                    account_id,
                    sub.endpoint,
                    exc,
                )

        if stale_endpoints:
            for endpoint in stale_endpoints:
                db_session.query(PushSubscriptionRecord).filter(
                    PushSubscriptionRecord.account_id == account_uuid,
                    PushSubscriptionRecord.endpoint == endpoint,
                ).delete()
            db_session.commit()
            logger.info(
                "Removed %d expired push subscription(s) for account %s",
                len(stale_endpoints),
                account_id,
            )

        return delivered

    async def send_new_review_notification(
        self,
        account_id: str,
        location_name: str,
        reviewer_name: str,
        rating: int,
        review_preview: str,
        db_session=None,
    ) -> int:
        """Send notification for new review."""
        stars = "*" * max(rating, 0)
        notification = PushNotification(
            title=f"New {rating}-Star Review {stars}".strip(),
            body=f"{reviewer_name} left a review for {location_name}: \"{review_preview[:50]}...\"",
            url="/dashboard/reviews",
            tag=f"review-{account_id}",
            data={"type": NotificationType.NEW_REVIEW.value},
        )
        return await self.send_to_account(account_id, notification, db_session=db_session)

    async def send_content_ready_notification(
        self,
        account_id: str,
        location_name: str,
        content_title: str,
        content_id: str,
        db_session=None,
    ) -> int:
        """Send notification when AI content is ready for approval."""
        notification = PushNotification(
            title="New Content Ready for Approval",
            body=f"AI generated a new post for {location_name}: \"{content_title}\"",
            url=f"/dashboard/content/{content_id}",
            tag=f"content-{content_id}",
            data={"type": NotificationType.CONTENT_READY.value, "content_id": content_id},
        )
        return await self.send_to_account(account_id, notification, db_session=db_session)

    async def send_approval_reminder(
        self,
        account_id: str,
        pending_count: int,
        db_session=None,
    ) -> int:
        """Send reminder for pending approvals."""
        notification = PushNotification(
            title=f"{pending_count} Posts Waiting for Approval",
            body="Review and approve your AI-generated content to keep your Google Maps active!",
            url="/dashboard/content?status=pending",
            tag=f"approval-reminder-{account_id}",
            data={"type": NotificationType.APPROVAL_NEEDED.value, "count": pending_count},
        )
        return await self.send_to_account(account_id, notification, db_session=db_session)

    async def send_weekly_report_notification(
        self,
        account_id: str,
        location_name: str,
        calls_change: int,
        directions_change: int,
        db_session=None,
    ) -> int:
        """Send notification when weekly report is ready."""
        notification = PushNotification(
            title="Weekly Report Ready",
            body=(
                f"{location_name}: Calls {'+' if calls_change > 0 else ''}{calls_change}%, "
                f"Directions {'+' if directions_change > 0 else ''}{directions_change}%"
            ),
            url="/dashboard/reports",
            tag=f"report-{account_id}",
            data={"type": NotificationType.WEEKLY_REPORT.value},
        )
        return await self.send_to_account(account_id, notification, db_session=db_session)

    async def send_missed_call_notification(
        self,
        account_id: str,
        location_name: str,
        caller_number: str,
        sms_sent: bool,
        db_session=None,
    ) -> int:
        """Send notification for missed call."""
        body = f"Missed call from {caller_number} at {location_name}"
        if sms_sent:
            body += " - auto SMS sent"

        notification = PushNotification(
            title="Missed Call",
            body=body,
            url="/dashboard/calls",
            tag=f"call-{account_id}-{datetime.now().timestamp()}",
            data={"type": NotificationType.MISSED_CALL.value, "caller": caller_number},
        )
        return await self.send_to_account(account_id, notification, db_session=db_session)

    async def send_performance_alert(
        self,
        account_id: str,
        location_name: str,
        metric: str,
        change_percent: int,
        is_positive: bool,
        db_session=None,
    ) -> int:
        """Send alert for significant performance change."""
        direction = "increased" if is_positive else "decreased"
        prefix = "Positive" if is_positive else "Negative"

        notification = PushNotification(
            title=f"{prefix} Performance Alert",
            body=f"{location_name}: {metric} {direction} by {abs(change_percent)}%",
            url="/dashboard/analytics",
            tag=f"perf-{account_id}-{metric}",
            data={"type": NotificationType.PERFORMANCE_ALERT.value, "metric": metric},
        )
        return await self.send_to_account(account_id, notification, db_session=db_session)

    def get_vapid_public_key(self) -> str:
        """Get VAPID public key for client subscription."""
        return self.vapid_public_key or ""


NOTIFICATION_TEMPLATES = {
    NotificationType.NEW_REVIEW: {
        "title_template": "New {rating}-Star Review {stars}",
        "body_template": "{reviewer} left a review: \"{preview}...\"",
        "icon": "star",
        "url": "/dashboard/reviews",
    },
    NotificationType.CONTENT_READY: {
        "title_template": "New Content Ready",
        "body_template": "AI generated: \"{title}\" for {location}",
        "icon": "file-text",
        "url": "/dashboard/content",
    },
    NotificationType.APPROVAL_NEEDED: {
        "title_template": "{count} Posts Pending",
        "body_template": "Review and approve your content",
        "icon": "check-circle",
        "url": "/dashboard/content?status=pending",
    },
    NotificationType.WEEKLY_REPORT: {
        "title_template": "Weekly Report Ready",
        "body_template": "See your performance for {location}",
        "icon": "bar-chart",
        "url": "/dashboard/reports",
    },
    NotificationType.MISSED_CALL: {
        "title_template": "Missed Call",
        "body_template": "From {caller} at {location}",
        "icon": "phone-missed",
        "url": "/dashboard/calls",
    },
    NotificationType.NEW_MESSAGE: {
        "title_template": "New Message",
        "body_template": "{sender}: \"{preview}...\"",
        "icon": "message-circle",
        "url": "/dashboard/social",
    },
    NotificationType.PERFORMANCE_ALERT: {
        "title_template": "{metric} Alert",
        "body_template": "{direction} by {percent}% at {location}",
        "icon": "trending-up",
        "url": "/dashboard/analytics",
    },
}
