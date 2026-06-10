"""Push Notifications Router."""

import csv
import io
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.notification import NotificationDeliveryLog, NotificationEvent, PushSubscriptionRecord
from app.routers.deps import get_current_account, get_db
from app.services.push_notification import (
    NotificationType,
    PushNotificationService,
    PushNotificationUnavailableError,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])

DEFAULT_NOTIFICATION_PREFERENCES = {
    "new_reviews": True,
    "content_ready": True,
    "approval_reminders": True,
    "weekly_reports": True,
    "missed_calls": True,
    "new_messages": True,
    "performance_alerts": True,
    "email_notifications": True,
    "push_notifications": True,
    "quiet_hours_start": None,
    "quiet_hours_end": None,
}

NOTIFICATION_PREFERENCES_KEY = "notification_preferences"
DELIVERY_AUDIT_PRESETS_KEY = "notification_delivery_audit_presets"


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
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    persisted: bool = False
    storage_available: bool = True
    source: str = "defaults"
    note: Optional[str] = None


class PushSubscribeResponse(BaseModel):
    success: bool
    created: bool  # True = new subscription, False = updated existing
    message: str


class PushUnsubscribeResponse(BaseModel):
    success: bool
    removed: bool  # True = a record was deleted, False = endpoint was not found


class PushSubscriptionInfo(BaseModel):
    id: str
    device_type: str
    created_at: datetime


class PushSubscriptionsResponse(BaseModel):
    subscriptions: list[PushSubscriptionInfo]
    count: int


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
    storage_available: bool = True
    source: str = "database"
    note: Optional[str] = None


class NotificationDeleteResponse(BaseModel):
    success: bool
    id: str


class TestNotificationRequest(BaseModel):
    type: str = "content_ready"


class DeliveryLogItem(BaseModel):
    id: str
    notification_event_id: Optional[str]
    channel: str
    delivery_status: str
    failure_reason: Optional[str]
    attempted_at: datetime
    delivered_at: Optional[datetime]
    created_at: datetime


class DeliveryAuditResponse(BaseModel):
    logs: list[DeliveryLogItem]
    total: int
    source: str = "database"


class DeliveryAuditPreset(BaseModel):
    id: str
    name: str
    channel: str = "all"
    delivery_status: str = "all"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class DeliveryAuditPresetsResponse(BaseModel):
    presets: list[DeliveryAuditPreset]
    source: str = "account.settings"


def _delivery_audit_query(
    db: Session,
    account_id: uuid.UUID,
    channel: Optional[str] = None,
    delivery_status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    query = db.query(NotificationDeliveryLog).filter(
        NotificationDeliveryLog.account_id == account_id
    )
    if channel:
        query = query.filter(NotificationDeliveryLog.channel == channel)
    if delivery_status:
        query = query.filter(NotificationDeliveryLog.delivery_status == delivery_status)
    if start_date:
        start_at = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        query = query.filter(NotificationDeliveryLog.attempted_at >= start_at)
    if end_date:
        end_at = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
        query = query.filter(NotificationDeliveryLog.attempted_at < end_at)
    return query


class NotificationHealthSummaryResponse(BaseModel):
    subscription_count: int
    unread_count: int
    push_configured: bool
    push_availability_reason: Optional[str] = None
    last_delivery_attempt_at: Optional[datetime] = None
    last_delivery_status: Optional[str] = None
    last_delivery_channel: Optional[str] = None
    last_delivery_failure_reason: Optional[str] = None
    recent_delivered_count: int = 0
    recent_failed_count: int = 0
    recent_unavailable_count: int = 0
    recent_skipped_count: int = 0
    attention_needed: bool = False
    window_days: int = 7
    source: str = "database"


def _account_settings(account: Account) -> dict:
    settings = account.settings
    return dict(settings) if isinstance(settings, dict) else {}


def _notification_preferences(account: Account) -> tuple[dict, bool, str]:
    settings = _account_settings(account)
    stored = settings.get(NOTIFICATION_PREFERENCES_KEY)
    if isinstance(stored, dict):
        payload = {**DEFAULT_NOTIFICATION_PREFERENCES, **stored}
        return payload, True, "account.settings"
    return dict(DEFAULT_NOTIFICATION_PREFERENCES), False, "defaults"


def _delivery_audit_presets(account: Account) -> list[dict]:
    settings = _account_settings(account)
    stored = settings.get(DELIVERY_AUDIT_PRESETS_KEY)
    if isinstance(stored, list):
        cleaned: list[dict] = []
        for item in stored:
            if isinstance(item, dict) and item.get("id") and item.get("name"):
                cleaned.append(
                    {
                        "id": str(item["id"]),
                        "name": str(item["name"]),
                        "channel": str(item.get("channel") or "all"),
                        "delivery_status": str(item.get("delivery_status") or "all"),
                        "start_date": item.get("start_date"),
                        "end_date": item.get("end_date"),
                    }
                )
        return cleaned
    return []


def _persist_notification(
    db: Session,
    account_id: uuid.UUID,
    type: str,
    title: str,
    body: str,
    url: Optional[str] = None,
) -> NotificationEvent:
    """Create and persist a notification event for an account."""
    event = NotificationEvent(
        account_id=account_id,
        type=type,
        title=title,
        body=body,
        url=url,
        read=False,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _record_delivery(
    db: Session,
    account_id: uuid.UUID,
    channel: str,
    delivery_status: str,
    notification_event_id: Optional[uuid.UUID] = None,
    failure_reason: Optional[str] = None,
) -> NotificationDeliveryLog:
    """Persist a delivery audit record for one channel attempt."""
    now = datetime.now(timezone.utc)
    log = NotificationDeliveryLog(
        account_id=account_id,
        notification_event_id=notification_event_id,
        channel=channel,
        delivery_status=delivery_status,
        failure_reason=failure_reason,
        attempted_at=now,
        delivered_at=now if delivery_status == "delivered" else None,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _location_context_from_url(url: Optional[str]) -> str:
    """Return a best-effort location context string from a notification URL."""
    if not url:
        return ""
    return url


@router.get("/vapid-key", response_model=VapidKeyResponse)
async def get_vapid_public_key():
    """Get VAPID public key for push subscription."""
    service = PushNotificationService()
    if not service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Push notifications are unavailable: {service.availability_reason() or 'push credentials are missing'}",
        )
    return VapidKeyResponse(public_key=service.get_vapid_public_key())


@router.post("/subscribe", response_model=PushSubscribeResponse)
async def subscribe_to_push(
    request: PushSubscriptionRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Persist a push subscription for the current account.

    Upserts by (account_id, endpoint): re-subscribing the same endpoint
    updates the keys rather than creating a duplicate row.
    """
    existing = (
        db.query(PushSubscriptionRecord)
        .filter(
            PushSubscriptionRecord.account_id == account.id,
            PushSubscriptionRecord.endpoint == request.endpoint,
        )
        .first()
    )

    if existing:
        existing.p256dh_key = request.p256dh_key
        existing.auth_key = request.auth_key
        existing.device_type = request.device_type
        db.add(existing)
        db.commit()
        return PushSubscribeResponse(
            success=True,
            created=False,
            message="Push subscription updated.",
        )

    sub = PushSubscriptionRecord(
        account_id=account.id,
        endpoint=request.endpoint,
        p256dh_key=request.p256dh_key,
        auth_key=request.auth_key,
        device_type=request.device_type,
    )
    db.add(sub)
    db.commit()
    return PushSubscribeResponse(
        success=True,
        created=True,
        message="Push subscription stored.",
    )


@router.delete("/subscribe", response_model=PushUnsubscribeResponse)
async def unsubscribe_from_push(
    endpoint: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Remove a stored push subscription by endpoint URL."""
    deleted = (
        db.query(PushSubscriptionRecord)
        .filter(
            PushSubscriptionRecord.account_id == account.id,
            PushSubscriptionRecord.endpoint == endpoint,
        )
        .delete()
    )
    db.commit()
    return PushUnsubscribeResponse(success=True, removed=deleted > 0)


@router.delete("/subscriptions/{subscription_id}", response_model=PushUnsubscribeResponse)
async def remove_stored_push_subscription(
    subscription_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Remove a stored push subscription by record id."""
    try:
        subscription_uuid = uuid.UUID(subscription_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Push subscription not found.")

    deleted = (
        db.query(PushSubscriptionRecord)
        .filter(
            PushSubscriptionRecord.id == subscription_uuid,
            PushSubscriptionRecord.account_id == account.id,
        )
        .delete()
    )
    db.commit()
    return PushUnsubscribeResponse(success=True, removed=deleted > 0)


@router.get("/subscriptions", response_model=PushSubscriptionsResponse)
async def list_push_subscriptions(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Return metadata for all stored push subscriptions for the current account.

    Endpoints are intentionally omitted from the response; only device type
    and creation time are returned.
    """
    subs = (
        db.query(PushSubscriptionRecord)
        .filter(PushSubscriptionRecord.account_id == account.id)
        .order_by(PushSubscriptionRecord.created_at.desc())
        .all()
    )
    return PushSubscriptionsResponse(
        subscriptions=[
            PushSubscriptionInfo(
                id=str(s.id),
                device_type=s.device_type,
                created_at=s.created_at,
            )
            for s in subs
        ],
        count=len(subs),
    )


@router.get("/preferences", response_model=NotificationPreferences)
async def get_notification_preferences(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get notification preferences."""
    payload, persisted, source = _notification_preferences(account)
    return NotificationPreferences(
        **payload,
        persisted=persisted,
        storage_available=True,
        source=source,
        note=(
            "Notification preferences are stored in your account settings."
            if persisted
            else "Notification preferences will be stored in your account settings when you save them."
        ),
    )


@router.put("/preferences", response_model=NotificationPreferences)
async def update_notification_preferences(
    request: NotificationPreferences,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Update notification preferences."""
    preferences = request.model_dump(
        exclude={"persisted", "storage_available", "source", "note"}
    )
    settings = _account_settings(account)
    settings[NOTIFICATION_PREFERENCES_KEY] = preferences
    account.settings = settings
    db.add(account)
    db.commit()
    db.refresh(account)

    return NotificationPreferences(
        **preferences,
        persisted=True,
        storage_available=True,
        source="account.settings",
        note="Notification preferences saved to account settings.",
    )


@router.get("/delivery-audit/presets", response_model=DeliveryAuditPresetsResponse)
async def get_delivery_audit_presets(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Return saved delivery audit presets from account settings."""
    presets = _delivery_audit_presets(account)
    return DeliveryAuditPresetsResponse(
        presets=[DeliveryAuditPreset(**preset) for preset in presets],
        source="account.settings",
    )


@router.put("/delivery-audit/presets", response_model=DeliveryAuditPresetsResponse)
async def update_delivery_audit_presets(
    presets: list[DeliveryAuditPreset],
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Persist delivery audit presets to account settings."""
    trimmed = presets[:10]
    settings = _account_settings(account)
    settings[DELIVERY_AUDIT_PRESETS_KEY] = [preset.model_dump() for preset in trimmed]
    account.settings = settings
    db.add(account)
    db.commit()
    db.refresh(account)
    return DeliveryAuditPresetsResponse(
        presets=[DeliveryAuditPreset(**preset) for preset in _delivery_audit_presets(account)],
        source="account.settings",
    )


@router.get("/history", response_model=NotificationHistoryResponse)
async def get_notification_history(
    limit: int = 20,
    offset: int = 0,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get notification history."""
    query = db.query(NotificationEvent).filter(
        NotificationEvent.account_id == account.id
    )
    if unread_only:
        query = query.filter(NotificationEvent.read == False)  # noqa: E712

    total_unread = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == account.id,
            NotificationEvent.read == False,  # noqa: E712
        )
        .count()
    )

    events = (
        query.order_by(NotificationEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return NotificationHistoryResponse(
        notifications=[
            NotificationHistoryItem(
                id=str(event.id),
                type=event.type,
                title=event.title,
                body=event.body,
                url=event.url,
                read=event.read,
                created_at=event.created_at,
            )
            for event in events
        ],
        unread_count=total_unread,
        storage_available=True,
        source="database",
        note=None,
    )


@router.post("/history/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Mark a notification as read."""
    try:
        nid = uuid.UUID(notification_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.id == nid,
            NotificationEvent.account_id == account.id,
        )
        .first()
    )
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

    if not event.read:
        event.read = True
        db.add(event)
        db.commit()

    return {"success": True, "id": notification_id}


@router.delete("/history/{notification_id}", response_model=NotificationDeleteResponse)
async def delete_notification(
    notification_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Delete one inbox notification while preserving delivery audit rows."""
    try:
        nid = uuid.UUID(notification_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

    event = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.id == nid,
            NotificationEvent.account_id == account.id,
        )
        .first()
    )
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

    db.execute(
        update(NotificationDeliveryLog)
        .where(NotificationDeliveryLog.notification_event_id == nid)
        .values(notification_event_id=None)
    )
    db.delete(event)
    db.commit()

    return NotificationDeleteResponse(success=True, id=notification_id)


@router.post("/history/read-all")
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Mark all notifications as read."""
    db.execute(
        update(NotificationEvent)
        .where(
            NotificationEvent.account_id == account.id,
            NotificationEvent.read == False,  # noqa: E712
        )
        .values(read=True)
    )
    db.commit()
    return {"success": True}


@router.post("/test")
async def send_test_notification(
    request: TestNotificationRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Send a test notification. Always persists to inbox; attempts push delivery if configured."""
    templates = {
        "new_review": {
            "title": "New Review: Your Business",
            "body": "Test User left a 5-star review: \"This is a test review notification\"",
            "url": "/dashboard/reviews",
        },
        "content_ready": {
            "title": "Content Ready: Your Business",
            "body": "AI has generated a new post: Test Content Post",
            "url": "/dashboard/posts",
        },
        "missed_call": {
            "title": "Missed Call: Your Business",
            "body": "Missed call from +1 (555) 123-4567. A text-back was sent.",
            "url": "/dashboard/calls",
        },
        "weekly_report": {
            "title": "Weekly Report: Your Business",
            "body": "Calls +21%, directions +14% this week.",
            "url": "/dashboard/analytics",
        },
    }

    tpl = templates.get(request.type, templates["content_ready"])
    event = _persist_notification(
        db=db,
        account_id=account.id,
        type=request.type,
        title=tpl["title"],
        body=tpl["body"],
        url=tpl.get("url"),
    )

    # Inbox delivery always succeeds at this point.
    _record_delivery(
        db=db,
        account_id=account.id,
        channel="inbox",
        delivery_status="delivered",
        notification_event_id=event.id,
    )

    push_delivered = False
    push_note = None
    service = PushNotificationService()
    if service.is_configured():
        try:
            if request.type == "new_review":
                delivered_count = await service.send_new_review_notification(
                    account_id=str(account.id),
                    location_name="Your Business",
                    reviewer_name="Test User",
                    rating=5,
                    review_preview="This is a test review notification",
                    db_session=db,
                )
            elif request.type == "content_ready":
                delivered_count = await service.send_content_ready_notification(
                    account_id=str(account.id),
                    location_name="Your Business",
                    content_title="Test Content Post",
                    content_id="test-123",
                    db_session=db,
                )
            elif request.type == "missed_call":
                delivered_count = await service.send_missed_call_notification(
                    account_id=str(account.id),
                    location_name="Your Business",
                    caller_number="+1 (555) 123-4567",
                    sms_sent=True,
                    db_session=db,
                )
            else:
                delivered_count = await service.send_weekly_report_notification(
                    account_id=str(account.id),
                    location_name="Your Business",
                    calls_change=21,
                    directions_change=14,
                    db_session=db,
                )
            push_delivered = delivered_count > 0
            _record_delivery(
                db=db,
                account_id=account.id,
                channel="push",
                delivery_status="delivered" if push_delivered else "skipped",
                notification_event_id=event.id,
                failure_reason=None if push_delivered else "No stored push subscriptions for this account.",
            )
        except PushNotificationUnavailableError as exc:
            push_note = str(exc)
            _record_delivery(
                db=db,
                account_id=account.id,
                channel="push",
                delivery_status="unavailable",
                notification_event_id=event.id,
                failure_reason=str(exc),
            )
        except Exception as exc:
            push_note = str(exc)
            _record_delivery(
                db=db,
                account_id=account.id,
                channel="push",
                delivery_status="failed",
                notification_event_id=event.id,
                failure_reason=str(exc),
            )
    else:
        push_note = service.availability_reason() or "Push credentials are not configured."
        _record_delivery(
            db=db,
            account_id=account.id,
            channel="push",
            delivery_status="unavailable",
            notification_event_id=event.id,
            failure_reason=push_note,
        )

    return {
        "success": True,
        "notification_id": str(event.id),
        "message": f"Test notification persisted to inbox: {request.type}",
        "push_delivered": push_delivered,
        "push_note": push_note,
    }


@router.get("/delivery-audit", response_model=DeliveryAuditResponse)
async def get_delivery_audit(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    channel: Optional[str] = Query(default=None),
    delivery_status: Optional[str] = Query(default=None),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Return delivery audit logs for the current account.

    Each record captures one channel attempt (inbox, push, email, sms, slack)
    with its outcome and any failure reason, giving operators a queryable audit
    trail for notification delivery.
    """
    query = _delivery_audit_query(
        db=db,
        account_id=account.id,
        channel=channel,
        delivery_status=delivery_status,
        start_date=start_date,
        end_date=end_date,
    )

    total = query.count()
    logs = (
        query.order_by(NotificationDeliveryLog.attempted_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return DeliveryAuditResponse(
        logs=[
            DeliveryLogItem(
                id=str(log.id),
                notification_event_id=(
                    str(log.notification_event_id) if log.notification_event_id else None
                ),
                channel=log.channel,
                delivery_status=log.delivery_status,
                failure_reason=log.failure_reason,
                attempted_at=log.attempted_at,
                delivered_at=log.delivered_at,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=total,
        source="database",
    )


@router.get("/delivery-audit/export")
async def export_delivery_audit(
    channel: Optional[str] = Query(default=None),
    delivery_status: Optional[str] = Query(default=None),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Export filtered delivery audit logs as CSV."""
    logs = (
        _delivery_audit_query(
            db=db,
            account_id=account.id,
            channel=channel,
            delivery_status=delivery_status,
            start_date=start_date,
            end_date=end_date,
        )
        .order_by(NotificationDeliveryLog.attempted_at.desc())
        .all()
    )

    event_ids = [log.notification_event_id for log in logs if log.notification_event_id]
    event_map: dict[uuid.UUID, NotificationEvent] = {}
    if event_ids:
        events = (
            db.query(NotificationEvent)
            .filter(NotificationEvent.id.in_(event_ids))
            .all()
        )
        event_map = {event.id: event for event in events}

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "account_email",
            "notification_event_id",
            "notification_type",
            "location_context",
            "context_url",
            "channel",
            "delivery_status",
            "failure_reason",
            "attempted_at",
            "delivered_at",
            "created_at",
        ],
    )
    writer.writeheader()
    for log in logs:
        writer.writerow(
            {
                "id": str(log.id),
                "account_email": account.email,
                "notification_event_id": str(log.notification_event_id) if log.notification_event_id else "",
                "notification_type": event_map.get(log.notification_event_id).type if log.notification_event_id in event_map else "",
                "location_context": _location_context_from_url(
                    event_map.get(log.notification_event_id).url if log.notification_event_id in event_map else None
                ),
                "context_url": event_map.get(log.notification_event_id).url if log.notification_event_id in event_map and event_map.get(log.notification_event_id).url else "",
                "channel": log.channel,
                "delivery_status": log.delivery_status,
                "failure_reason": log.failure_reason or "",
                "attempted_at": log.attempted_at.isoformat() if log.attempted_at else "",
                "delivered_at": log.delivered_at.isoformat() if log.delivered_at else "",
                "created_at": log.created_at.isoformat() if log.created_at else "",
            }
        )

    filename = "notification-delivery-audit.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/health-summary", response_model=NotificationHealthSummaryResponse)
async def get_notification_health_summary(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Return account-level notification health for dashboard/integrations surfaces."""
    service = PushNotificationService()
    subscription_count = (
        db.query(PushSubscriptionRecord)
        .filter(PushSubscriptionRecord.account_id == account.id)
        .count()
    )
    unread_count = (
        db.query(NotificationEvent)
        .filter(
            NotificationEvent.account_id == account.id,
            NotificationEvent.read == False,  # noqa: E712
        )
        .count()
    )
    last_log = (
        db.query(NotificationDeliveryLog)
        .filter(NotificationDeliveryLog.account_id == account.id)
        .order_by(NotificationDeliveryLog.attempted_at.desc())
        .first()
    )

    window_days = 7
    window_start = datetime.now(timezone.utc) - timedelta(days=window_days)
    recent_logs = (
        db.query(NotificationDeliveryLog)
        .filter(
            NotificationDeliveryLog.account_id == account.id,
            NotificationDeliveryLog.attempted_at >= window_start,
        )
        .all()
    )
    recent_counts = {
        "delivered": 0,
        "failed": 0,
        "unavailable": 0,
        "skipped": 0,
    }
    for log in recent_logs:
        if log.delivery_status in recent_counts:
            recent_counts[log.delivery_status] += 1

    push_configured = service.is_configured()
    push_availability_reason = None if push_configured else (
        service.availability_reason() or "Push credentials are not configured."
    )
    attention_needed = (
        not push_configured
        or subscription_count == 0
        or recent_counts["failed"] > 0
        or recent_counts["unavailable"] > 0
    )

    return NotificationHealthSummaryResponse(
        subscription_count=subscription_count,
        unread_count=unread_count,
        push_configured=push_configured,
        push_availability_reason=push_availability_reason,
        last_delivery_attempt_at=last_log.attempted_at if last_log else None,
        last_delivery_status=last_log.delivery_status if last_log else None,
        last_delivery_channel=last_log.channel if last_log else None,
        last_delivery_failure_reason=last_log.failure_reason if last_log else None,
        recent_delivered_count=recent_counts["delivered"],
        recent_failed_count=recent_counts["failed"],
        recent_unavailable_count=recent_counts["unavailable"],
        recent_skipped_count=recent_counts["skipped"],
        attention_needed=attention_needed,
        window_days=window_days,
        source="database",
    )
