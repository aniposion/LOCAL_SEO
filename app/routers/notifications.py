"""
Push Notifications Router
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.routers.deps import get_current_account, get_db
from app.models.account import Account
from app.services.push_notification import PushNotificationService, NotificationType

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ============ Schemas ============

class PushSubscriptionRequest(BaseModel):
    endpoint: str
    p256dh_key: str
    auth_key: str
    device_type: str = "web"


class NotificationPreferences(BaseModel):
    new_reviews: bool = True
    content_ready: bool = True
    approval_reminders: bool = True
    weekly_reports: bool = True
    missed_calls: bool = True
    new_messages: bool = True
    performance_alerts: bool = True
    email_notifications: bool = True
    push_notifications: bool = True
    quiet_hours_start: Optional[str] = None  # "22:00"
    quiet_hours_end: Optional[str] = None    # "08:00"


class VapidKeyResponse(BaseModel):
    public_key: str


class NotificationHistoryItem(BaseModel):
    id: str
    type: str
    title: str
    body: str
    url: Optional[str]
    read: bool
    created_at: datetime


class NotificationHistoryResponse(BaseModel):
    notifications: list[NotificationHistoryItem]
    unread_count: int


class TestNotificationRequest(BaseModel):
    type: str = "content_ready"


# ============ Endpoints ============

@router.get("/vapid-key", response_model=VapidKeyResponse)
async def get_vapid_public_key():
    """Get VAPID public key for push subscription."""
    service = PushNotificationService()
    return VapidKeyResponse(public_key=service.get_vapid_public_key())


@router.post("/subscribe")
async def subscribe_to_push(
    request: PushSubscriptionRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Subscribe to push notifications."""
    # In production, save subscription to database
    # For now, just acknowledge
    return {
        "success": True,
        "message": "Successfully subscribed to push notifications",
        "subscription_id": f"sub_{account.id}_{datetime.now().timestamp()}",
    }


@router.delete("/subscribe")
async def unsubscribe_from_push(
    endpoint: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Unsubscribe from push notifications."""
    # In production, remove subscription from database
    return {"success": True, "message": "Successfully unsubscribed"}


@router.get("/preferences", response_model=NotificationPreferences)
async def get_notification_preferences(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get notification preferences."""
    # In production, fetch from database
    # Return defaults for now
    return NotificationPreferences()


@router.put("/preferences", response_model=NotificationPreferences)
async def update_notification_preferences(
    request: NotificationPreferences,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Update notification preferences."""
    # In production, save to database
    return request


@router.get("/history", response_model=NotificationHistoryResponse)
async def get_notification_history(
    limit: int = 20,
    offset: int = 0,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get notification history."""
    # Demo data
    notifications = [
        NotificationHistoryItem(
            id="n1",
            type=NotificationType.NEW_REVIEW,
            title="New 5-Star Review! ⭐⭐⭐⭐⭐",
            body="John D. left a review: \"Amazing food and great service...\"",
            url="/dashboard/reviews",
            read=False,
            created_at=datetime.now(),
        ),
        NotificationHistoryItem(
            id="n2",
            type=NotificationType.CONTENT_READY,
            title="🎨 New Content Ready for Approval",
            body="AI generated a new post: \"Weekend Special BBQ Deal\"",
            url="/dashboard/content/123",
            read=False,
            created_at=datetime.now(),
        ),
        NotificationHistoryItem(
            id="n3",
            type=NotificationType.WEEKLY_REPORT,
            title="📊 Weekly Report Ready",
            body="Calls +21%, Directions +14% this week!",
            url="/dashboard/reports",
            read=True,
            created_at=datetime.now(),
        ),
    ]
    
    if unread_only:
        notifications = [n for n in notifications if not n.read]
    
    return NotificationHistoryResponse(
        notifications=notifications[offset:offset+limit],
        unread_count=sum(1 for n in notifications if not n.read),
    )


@router.post("/history/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Mark a notification as read."""
    return {"success": True}


@router.post("/history/read-all")
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Mark all notifications as read."""
    return {"success": True, "marked_count": 3}


@router.post("/test")
async def send_test_notification(
    request: TestNotificationRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Send a test notification."""
    service = PushNotificationService()
    
    if request.type == "new_review":
        await service.send_new_review_notification(
            account_id=str(account.id),
            location_name="Your Business",
            reviewer_name="Test User",
            rating=5,
            review_preview="This is a test review notification",
        )
    elif request.type == "content_ready":
        await service.send_content_ready_notification(
            account_id=str(account.id),
            location_name="Your Business",
            content_title="Test Content Post",
            content_id="test-123",
        )
    elif request.type == "missed_call":
        await service.send_missed_call_notification(
            account_id=str(account.id),
            location_name="Your Business",
            caller_number="+1 (555) 123-4567",
            sms_sent=True,
        )
    else:
        await service.send_weekly_report_notification(
            account_id=str(account.id),
            location_name="Your Business",
            calls_change=21,
            directions_change=14,
        )
    
    return {"success": True, "message": f"Test notification sent: {request.type}"}
