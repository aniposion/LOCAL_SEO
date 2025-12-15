"""
Push Notification Service
Web Push (Browser) and Firebase Cloud Messaging support
"""
import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from enum import Enum

from app.core.config import settings


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
        self.vapid_private_key = settings.vapid_private_key if hasattr(settings, 'vapid_private_key') else None
        self.vapid_public_key = settings.vapid_public_key if hasattr(settings, 'vapid_public_key') else None
        self.vapid_email = settings.vapid_email if hasattr(settings, 'vapid_email') else "admin@localseooptimizer.com"
    
    async def send_web_push(
        self,
        subscription: PushSubscription,
        notification: PushNotification,
    ) -> bool:
        """Send a web push notification."""
        try:
            from pywebpush import webpush, WebPushException
            
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
            
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=self.vapid_private_key,
                vapid_claims={"sub": f"mailto:{self.vapid_email}"},
            )
            
            return True
        except Exception as e:
            print(f"Web push failed: {e}")
            return False
    
    async def send_to_account(
        self,
        account_id: str,
        notification: PushNotification,
        db_session=None,
    ) -> int:
        """Send notification to all subscriptions for an account."""
        # In production, fetch subscriptions from database
        # For now, return demo success
        sent_count = 0
        
        # Demo: simulate sending
        print(f"[Push] Sending to account {account_id}: {notification.title}")
        sent_count = 1
        
        return sent_count
    
    async def send_new_review_notification(
        self,
        account_id: str,
        location_name: str,
        reviewer_name: str,
        rating: int,
        review_preview: str,
    ) -> int:
        """Send notification for new review."""
        stars = "⭐" * rating
        notification = PushNotification(
            title=f"New {rating}-Star Review! {stars}",
            body=f"{reviewer_name} left a review for {location_name}: \"{review_preview[:50]}...\"",
            url="/dashboard/reviews",
            tag=f"review-{account_id}",
            data={"type": NotificationType.NEW_REVIEW},
        )
        return await self.send_to_account(account_id, notification)
    
    async def send_content_ready_notification(
        self,
        account_id: str,
        location_name: str,
        content_title: str,
        content_id: str,
    ) -> int:
        """Send notification when AI content is ready for approval."""
        notification = PushNotification(
            title="🎨 New Content Ready for Approval",
            body=f"AI generated a new post for {location_name}: \"{content_title}\"",
            url=f"/dashboard/content/{content_id}",
            tag=f"content-{content_id}",
            data={"type": NotificationType.CONTENT_READY, "content_id": content_id},
        )
        return await self.send_to_account(account_id, notification)
    
    async def send_approval_reminder(
        self,
        account_id: str,
        pending_count: int,
    ) -> int:
        """Send reminder for pending approvals."""
        notification = PushNotification(
            title=f"📝 {pending_count} Posts Waiting for Approval",
            body="Review and approve your AI-generated content to keep your Google Maps active!",
            url="/dashboard/content?status=pending",
            tag=f"approval-reminder-{account_id}",
            data={"type": NotificationType.APPROVAL_NEEDED, "count": pending_count},
        )
        return await self.send_to_account(account_id, notification)
    
    async def send_weekly_report_notification(
        self,
        account_id: str,
        location_name: str,
        calls_change: int,
        directions_change: int,
    ) -> int:
        """Send notification when weekly report is ready."""
        trend = "📈" if calls_change > 0 else "📉"
        notification = PushNotification(
            title=f"{trend} Weekly Report Ready",
            body=f"{location_name}: Calls {'+' if calls_change > 0 else ''}{calls_change}%, Directions {'+' if directions_change > 0 else ''}{directions_change}%",
            url="/dashboard/reports",
            tag=f"report-{account_id}",
            data={"type": NotificationType.WEEKLY_REPORT},
        )
        return await self.send_to_account(account_id, notification)
    
    async def send_missed_call_notification(
        self,
        account_id: str,
        location_name: str,
        caller_number: str,
        sms_sent: bool,
    ) -> int:
        """Send notification for missed call."""
        body = f"Missed call from {caller_number} at {location_name}"
        if sms_sent:
            body += " - Auto SMS sent ✓"
        
        notification = PushNotification(
            title="📞 Missed Call",
            body=body,
            url="/dashboard/calls",
            tag=f"call-{account_id}-{datetime.now().timestamp()}",
            data={"type": NotificationType.MISSED_CALL, "caller": caller_number},
        )
        return await self.send_to_account(account_id, notification)
    
    async def send_performance_alert(
        self,
        account_id: str,
        location_name: str,
        metric: str,
        change_percent: int,
        is_positive: bool,
    ) -> int:
        """Send alert for significant performance change."""
        emoji = "🚀" if is_positive else "⚠️"
        direction = "increased" if is_positive else "decreased"
        
        notification = PushNotification(
            title=f"{emoji} Performance Alert",
            body=f"{location_name}: {metric} {direction} by {abs(change_percent)}%",
            url="/dashboard/analytics",
            tag=f"perf-{account_id}-{metric}",
            data={"type": NotificationType.PERFORMANCE_ALERT, "metric": metric},
        )
        return await self.send_to_account(account_id, notification)
    
    def get_vapid_public_key(self) -> str:
        """Get VAPID public key for client subscription."""
        return self.vapid_public_key or ""


# Notification templates by type
NOTIFICATION_TEMPLATES = {
    NotificationType.NEW_REVIEW: {
        "title_template": "New {rating}-Star Review! {stars}",
        "body_template": "{reviewer} left a review: \"{preview}...\"",
        "icon": "star",
        "url": "/dashboard/reviews",
    },
    NotificationType.CONTENT_READY: {
        "title_template": "🎨 New Content Ready",
        "body_template": "AI generated: \"{title}\" for {location}",
        "icon": "file-text",
        "url": "/dashboard/content",
    },
    NotificationType.APPROVAL_NEEDED: {
        "title_template": "📝 {count} Posts Pending",
        "body_template": "Review and approve your content",
        "icon": "check-circle",
        "url": "/dashboard/content?status=pending",
    },
    NotificationType.WEEKLY_REPORT: {
        "title_template": "📊 Weekly Report Ready",
        "body_template": "See your performance for {location}",
        "icon": "bar-chart",
        "url": "/dashboard/reports",
    },
    NotificationType.MISSED_CALL: {
        "title_template": "📞 Missed Call",
        "body_template": "From {caller} at {location}",
        "icon": "phone-missed",
        "url": "/dashboard/calls",
    },
    NotificationType.NEW_MESSAGE: {
        "title_template": "💬 New Message",
        "body_template": "{sender}: \"{preview}...\"",
        "icon": "message-circle",
        "url": "/dashboard/social",
    },
    NotificationType.PERFORMANCE_ALERT: {
        "title_template": "{emoji} {metric} Alert",
        "body_template": "{direction} by {percent}% at {location}",
        "icon": "trending-up",
        "url": "/dashboard/analytics",
    },
}
