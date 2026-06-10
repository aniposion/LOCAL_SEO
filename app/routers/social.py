"""Social Auto-Responder router."""

import logging
from datetime import UTC, datetime
from io import StringIO
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.channel import Channel, ChannelType
from app.models.social_response import SocialAutomationSettings, SocialResponseLog, SocialResponseMode
from app.routers.deps import get_current_account, get_db
from app.services.credits import CreditsService
from app.services.feature_access import FeatureAccessService
from app.services.notification import NotificationService
from app.services.social_responder import ResponseType, SocialResponderService

router = APIRouter(prefix="/social", tags=["Social"])
logger = logging.getLogger(__name__)


class SocialUsageLimitError(Exception):
    """Raised when AI response generation exceeds account limits."""

    def __init__(self, detail: dict):
        super().__init__(detail.get("message") or "AI response rate limit exceeded")
        self.detail = detail


class SocialMessageResponse(BaseModel):
    id: str
    platform: str
    type: str
    sender_id: str
    sender_name: str
    message: str
    post_id: Optional[str] = None
    created_at: datetime
    sentiment: Optional[str] = None
    triage_priority: str = "normal"
    triage_reason: Optional[str] = None
    suggested_response: Optional[str] = None


class MessagesListResponse(BaseModel):
    messages: list[SocialMessageResponse]
    total: int


class SendResponseRequest(BaseModel):
    message_id: str
    response_text: str
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None
    message_text: Optional[str] = None
    message_type: str = "dm"
    platform: str = "instagram"
    post_id: Optional[str] = None
    message_created_at: Optional[datetime] = None


class GenerateResponseRequest(BaseModel):
    message_text: str
    message_type: str = "dm"


class SocialSettingsResponse(BaseModel):
    auto_respond_enabled: bool
    auto_respond_dms: bool
    auto_respond_comments: bool
    response_delay_seconds: int
    excluded_keywords: list[str]
    high_priority_alerts_enabled: bool
    high_priority_alert_channel: str


class UpdateSocialSettingsRequest(BaseModel):
    auto_respond_enabled: Optional[bool] = None
    auto_respond_dms: Optional[bool] = None
    auto_respond_comments: Optional[bool] = None
    response_delay_seconds: Optional[int] = None
    excluded_keywords: Optional[list[str]] = None
    high_priority_alerts_enabled: Optional[bool] = None
    high_priority_alert_channel: Optional[str] = None


class SocialStatsResponse(BaseModel):
    total_messages: int
    auto_responded: int
    manual_responses: int
    failed_responses: int
    avg_response_time_minutes: float
    response_rate: float
    sentiment_positive: int
    sentiment_neutral: int
    sentiment_negative: int
    last_successful_response_at: Optional[datetime] = None
    last_failed_response_at: Optional[datetime] = None
    automation_health: str = "paused"
    automation_health_reason: Optional[str] = None


class SocialResponseLogResponse(BaseModel):
    id: str
    platform: str
    message_type: str
    response_mode: str
    message_id: str
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None
    post_id: Optional[str] = None
    source_message: Optional[str] = None
    sentiment: Optional[str] = None
    response_text: str
    success: bool
    error_message: Optional[str] = None
    source_created_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    created_at: datetime


class SocialHistoryResponse(BaseModel):
    items: list[SocialResponseLogResponse]
    total: int
    limit: int
    offset: int


def _preview_ai_response_usage(db: Session, account_id: UUID, count: int = 1) -> None:
    result = CreditsService(db).preview_usage(str(account_id), "ai_response", count)
    if result.get("allowed"):
        return

    raise SocialUsageLimitError(
        {
            "error": "Rate limit exceeded",
            "message": result.get("reason"),
            "remaining_daily": result.get("remaining_daily", 0),
            "remaining_monthly": result.get("remaining_monthly", 0),
            "cooldown_seconds": result.get("cooldown_remaining_seconds", 0),
            "overage_available": result.get("overage_available", False),
            "overage_cost_cents": result.get("overage_cost_cents", 0),
        }
    )


def _record_ai_response_usage(db: Session, account_id: UUID, count: int = 1) -> None:
    result = CreditsService(db).use_credits(str(account_id), "ai_response", count)
    if result.get("allowed"):
        return

    logger.warning(
        "Social ai_response usage record failed after successful generation for account %s x%s: %s",
        account_id,
        count,
        result.get("reason"),
    )


def _build_history_query(
    db: Session,
    *,
    location_id: UUID,
    mode: Optional[str] = None,
    success: Optional[bool] = None,
    sentiment: Optional[str] = None,
    search: Optional[str] = None,
):
    query = db.query(SocialResponseLog).filter(SocialResponseLog.location_id == location_id)
    if mode:
        query = query.filter(SocialResponseLog.response_mode == mode)
    if success is not None:
        query = query.filter(SocialResponseLog.success == success)
    if sentiment:
        query = query.filter(SocialResponseLog.sentiment == sentiment)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                SocialResponseLog.sender_name.ilike(term),
                SocialResponseLog.source_message.ilike(term),
                SocialResponseLog.response_text.ilike(term),
            )
        )
    return query


def _get_location(db: Session, location_id: str, account: Account):
    from app.models.location import Location

    location = db.query(Location).filter(
        Location.id == location_id,
        Location.account_id == account.id,
    ).first()
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return location


def _get_instagram_channel(db: Session, location_id: str) -> Channel | None:
    normalized_location_id = UUID(str(location_id))
    channel = (
        db.query(Channel)
        .filter(Channel.location_id == normalized_location_id, Channel.type == ChannelType.INSTAGRAM)
        .first()
    )
    if not channel or not channel.is_active:
        return None
    credentials = channel.get_credentials() if channel.credentials_encrypted else {}
    if not credentials.get("access_token"):
        return None
    if channel.is_token_expired:
        return None
    return channel


def _safe_aware_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _log_social_response(
    db: Session,
    *,
    location_id: str | UUID,
    platform: str,
    message_type: str,
    response_mode: SocialResponseMode,
    message_id: str,
    sender_id: Optional[str],
    sender_name: Optional[str],
    post_id: Optional[str],
    source_message: Optional[str],
    sentiment: Optional[str],
    response_text: str,
    success: bool,
    error_message: Optional[str],
    source_created_at: Optional[datetime],
    responded_at: Optional[datetime],
) -> SocialResponseLog:
    log = SocialResponseLog(
        location_id=UUID(str(location_id)),
        platform=platform,
        message_type=message_type,
        response_mode=response_mode,
        message_id=message_id,
        sender_id=sender_id,
        sender_name=sender_name,
        post_id=post_id,
        source_message=source_message,
        sentiment=sentiment,
        response_text=response_text,
        success=success,
        error_message=error_message,
        source_created_at=_safe_aware_datetime(source_created_at),
        responded_at=_safe_aware_datetime(responded_at) or datetime.now(UTC),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _get_or_create_settings(db: Session, location_id: UUID) -> SocialAutomationSettings:
    settings = db.query(SocialAutomationSettings).filter(
        SocialAutomationSettings.location_id == location_id
    ).first()
    if settings:
        return settings

    settings = SocialAutomationSettings(
        location_id=location_id,
        auto_respond_enabled=True,
        auto_respond_dms=True,
        auto_respond_comments=False,
        response_delay_seconds=60,
        excluded_keywords="spam,unsubscribe",
        high_priority_alerts_enabled=False,
        high_priority_alert_channel="preferred",
    )
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


def _triage_message(
    service: SocialResponderService,
    message,
    settings: SocialAutomationSettings,
) -> tuple[str, str | None, str]:
    sentiment = service.classify_sentiment(message.message)
    excluded_keywords = [item.strip().lower() for item in (settings.excluded_keywords or "").split(",") if item.strip()]

    if any(keyword in message.message.lower() for keyword in excluded_keywords):
        return "low", "contains excluded keyword", sentiment
    if sentiment == "negative":
        return "high", "negative sentiment", sentiment
    if message.type == ResponseType.COMMENT:
        return "high", "public comment", sentiment
    if any(term in message.message.lower() for term in ["refund", "cancel", "angry", "complaint", "problem"]):
        return "high", "needs manual review", sentiment
    if any(term in message.message.lower() for term in ["book", "appointment", "reservation", "price", "quote"]):
        return "medium", "conversion intent", sentiment
    return "normal", None, sentiment


@router.get("/{location_id}/messages", response_model=MessagesListResponse)
async def get_pending_messages(
    location_id: str,
    platform: str = "instagram",
    message_type: Optional[str] = None,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get pending messages that need responses."""
    location = _get_location(db, location_id, account)
    channel = _get_instagram_channel(db, location.id) if platform == "instagram" else None
    service = SocialResponderService(channel.get_credentials() if channel else None)
    settings = _get_or_create_settings(db, location.id)
    messages = await service.get_pending_messages(location_id, platform)

    if message_type:
        messages = [item for item in messages if item.type.value == message_type]

    business_info = {
        "address": location.address,
        "phone": location.phone,
        "category": getattr(location, "category", None),
    }

    response_messages = []
    for message in messages:
        triage_priority, triage_reason, sentiment = _triage_message(service, message, settings)
        response_messages.append(
            SocialMessageResponse(
                id=message.id,
                platform=message.platform,
                type=message.type.value,
                sender_id=message.sender_id,
                sender_name=message.sender_name,
                message=message.message,
                post_id=message.post_id,
                created_at=message.created_at or datetime.now(),
                sentiment=sentiment,
                triage_priority=triage_priority,
                triage_reason=triage_reason,
            )
        )

    priority_order = {"high": 0, "medium": 1, "normal": 2, "low": 3}
    response_messages.sort(
        key=lambda item: (
            priority_order.get(item.triage_priority, 9),
            item.created_at,
        )
    )

    return MessagesListResponse(messages=response_messages, total=len(response_messages))


@router.get("/{location_id}/history", response_model=SocialHistoryResponse)
def get_response_history(
    location_id: str,
    limit: int = 50,
    offset: int = 0,
    mode: Optional[str] = None,
    success: Optional[bool] = None,
    sentiment: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get persisted social response audit history."""
    location = _get_location(db, location_id, account)
    query = _build_history_query(
        db,
        location_id=location.id,
        mode=mode,
        success=success,
        sentiment=sentiment,
        search=search,
    )

    total = query.count()
    items = (
        query.order_by(SocialResponseLog.responded_at.desc(), SocialResponseLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return SocialHistoryResponse(
        items=[
            SocialResponseLogResponse(
                id=str(item.id),
                platform=item.platform,
                message_type=item.message_type,
                response_mode=item.response_mode.value,
                message_id=item.message_id,
                sender_id=item.sender_id,
                sender_name=item.sender_name,
                post_id=item.post_id,
                source_message=item.source_message,
                sentiment=item.sentiment,
                response_text=item.response_text,
                success=item.success,
                error_message=item.error_message,
                source_created_at=item.source_created_at,
                responded_at=item.responded_at,
                created_at=item.created_at,
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{location_id}/history/export")
def export_response_history(
    location_id: str,
    mode: Optional[str] = None,
    success: Optional[bool] = None,
    sentiment: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Export persisted social response history as CSV."""
    import csv

    location = _get_location(db, location_id, account)
    query = _build_history_query(
        db,
        location_id=location.id,
        mode=mode,
        success=success,
        sentiment=sentiment,
        search=search,
    )
    items = query.order_by(SocialResponseLog.responded_at.desc(), SocialResponseLog.created_at.desc()).all()

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "responded_at",
            "platform",
            "message_type",
            "response_mode",
            "sender_name",
            "sentiment",
            "success",
            "source_message",
            "response_text",
            "error_message",
        ]
    )
    for item in items:
        writer.writerow(
            [
                item.responded_at.isoformat() if item.responded_at else "",
                item.platform,
                item.message_type,
                item.response_mode.value,
                item.sender_name or "",
                item.sentiment or "",
                "true" if item.success else "false",
                item.source_message or "",
                item.response_text,
                item.error_message or "",
            ]
        )

    filename = f"social-history-{location.id}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{location_id}/respond")
async def send_response(
    location_id: str,
    request: SendResponseRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Send a response to a message."""
    from app.services.social_responder import SocialMessage

    location = _get_location(db, location_id, account)
    FeatureAccessService(db).check_feature_access(account, "social_auto_responder")
    channel = _get_instagram_channel(db, location.id)
    if not channel:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Instagram is not connected for this location")

    service = SocialResponderService(channel.get_credentials())
    response_type = ResponseType.DM if request.message_type == "dm" else ResponseType.COMMENT
    # Manual replies should not trigger hidden AI work just to enrich audit logs.
    sentiment = service.classify_sentiment(request.message_text or "")
    message = SocialMessage(
        id=request.message_id,
        platform=request.platform,
        type=response_type,
        sender_id=request.sender_id or "",
        sender_name=request.sender_name or "",
        message=request.message_text or "",
        post_id=request.post_id,
        created_at=request.message_created_at,
    )

    result = await service.send_response(message, request.response_text)
    log = _log_social_response(
        db,
        location_id=location.id,
        platform=request.platform,
        message_type=request.message_type,
        response_mode=SocialResponseMode.MANUAL,
        message_id=request.message_id,
        sender_id=request.sender_id,
        sender_name=request.sender_name,
        post_id=request.post_id,
        source_message=request.message_text,
        sentiment=sentiment,
        response_text=request.response_text,
        success=result.success,
        error_message=None if result.success else result.error_message or "Failed to send response",
        source_created_at=request.message_created_at,
        responded_at=result.sent_at,
    )

    return {
        "success": result.success,
        "message": "Response sent successfully" if result.success else result.error_message or "Failed to send response",
        "sent_at": result.sent_at.isoformat(),
        "log_id": str(log.id),
    }


@router.post("/{location_id}/generate-response")
async def generate_response(
    location_id: str,
    request: GenerateResponseRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Generate an AI response for a message."""
    from app.services.social_responder import SocialMessage

    location = _get_location(db, location_id, account)
    FeatureAccessService(db).check_feature_access(account, "social_auto_responder")
    service = SocialResponderService()
    try:
        _preview_ai_response_usage(db, account.id, 1)
    except SocialUsageLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=exc.detail) from exc
    message = SocialMessage(
        id="temp",
        platform="instagram",
        type=ResponseType.DM if request.message_type == "dm" else ResponseType.COMMENT,
        sender_id="",
        sender_name="Customer",
        message=request.message_text,
    )
    business_info = {
        "address": location.address,
        "phone": location.phone,
        "category": getattr(location, "category", None),
    }
    service.last_generation_used_ai = True
    response = await service.generate_response(message, location.name, business_info)
    if service.last_generation_used_ai:
        _record_ai_response_usage(db, account.id, 1)
    return {"suggested_response": response}


@router.post("/{location_id}/auto-respond")
async def auto_respond_all(
    location_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Auto-respond to all pending messages."""
    location = _get_location(db, location_id, account)
    FeatureAccessService(db).check_feature_access(account, "social_auto_responder")
    channel = _get_instagram_channel(db, location.id)
    if not channel:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Instagram is not connected for this location")

    service = SocialResponderService(channel.get_credentials())
    settings = _get_or_create_settings(db, location.id)
    business_info = {
        "address": location.address,
        "phone": location.phone,
        "category": getattr(location, "category", None),
    }

    messages = await service.get_pending_messages(location_id)
    success_count = 0
    failure_count = 0
    skipped_count = 0
    skipped_excluded_keywords = 0
    skipped_too_recent = 0
    skipped_disabled_type = 0
    rate_limited_count = 0
    rate_limit_detail: dict | None = None
    high_priority_messages: list[dict] = []

    for message in messages:
        triage_priority, triage_reason, sentiment = _triage_message(service, message, settings)
        if triage_priority == "high":
            high_priority_messages.append(
                {
                    "sender_name": message.sender_name,
                    "message": message.message,
                    "reason": triage_reason or "manual review",
                    "type": message.type.value,
                }
            )
        if not settings.auto_respond_enabled:
            break
        if message.type == ResponseType.DM and not settings.auto_respond_dms:
            skipped_count += 1
            skipped_disabled_type += 1
            continue
        if message.type == ResponseType.COMMENT and not settings.auto_respond_comments:
            skipped_count += 1
            skipped_disabled_type += 1
            continue
        excluded_keywords = [item.strip().lower() for item in (settings.excluded_keywords or "").split(",") if item.strip()]
        if any(keyword in message.message.lower() for keyword in excluded_keywords):
            skipped_count += 1
            skipped_excluded_keywords += 1
            continue
        if message.created_at:
            age_seconds = (datetime.now(UTC) - _safe_aware_datetime(message.created_at)).total_seconds()
            if age_seconds < settings.response_delay_seconds:
                skipped_count += 1
                skipped_too_recent += 1
                continue
        if message.type == ResponseType.MENTION:
            skipped_count += 1
            skipped_disabled_type += 1
            continue

        try:
            _preview_ai_response_usage(db, account.id, 1)
        except SocialUsageLimitError as exc:
            rate_limited_count += 1
            rate_limit_detail = exc.detail
            break

        service.last_generation_used_ai = True
        response_text = await service.generate_response(message, location.name, business_info)
        if service.last_generation_used_ai:
            _record_ai_response_usage(db, account.id, 1)
        result = await service.send_response(message, response_text)
        _log_social_response(
            db,
            location_id=location.id,
            platform=message.platform,
            message_type=message.type.value,
            response_mode=SocialResponseMode.AUTO,
            message_id=message.id,
            sender_id=message.sender_id,
            sender_name=message.sender_name,
            post_id=message.post_id,
            source_message=message.message,
            sentiment=sentiment,
            response_text=response_text,
            success=result.success,
            error_message=None if result.success else result.error_message or "Failed to send response",
            source_created_at=message.created_at,
            responded_at=result.sent_at,
        )
        if result.success:
            success_count += 1
        else:
            failure_count += 1

    alerted_high_priority_count = 0
    if settings.high_priority_alerts_enabled and high_priority_messages:
        notification_service = NotificationService(db)
        sample_lines = [
            f"- {item['sender_name']}: {item['reason']} ({item['type']})"
            for item in high_priority_messages[:5]
        ]
        await notification_service.send_notification(
            account_id=account.id,
            title=f"High-priority social messages for {location.name}",
            message=(
                f"{len(high_priority_messages)} message(s) need manual review.\n\n"
                + "\n".join(sample_lines)
            ),
            notification_type="social_high_priority_alert",
            data={
                "location_id": str(location.id),
                "count": len(high_priority_messages),
                "messages": high_priority_messages[:5],
            },
            channel_override=settings.high_priority_alert_channel
            if settings.high_priority_alert_channel != "preferred"
            else None,
        )
        alerted_high_priority_count = len(high_priority_messages)

    return {
        "total_processed": len(messages),
        "success_count": success_count,
        "failed_count": failure_count,
        "skipped_count": skipped_count,
        "skipped_excluded_keywords": skipped_excluded_keywords,
        "skipped_too_recent": skipped_too_recent,
        "skipped_disabled_type": skipped_disabled_type,
        "rate_limited_count": rate_limited_count,
        "rate_limit_detail": rate_limit_detail,
        "high_priority_count": len(high_priority_messages),
        "alerted_high_priority_count": alerted_high_priority_count,
    }


@router.get("/{location_id}/settings", response_model=SocialSettingsResponse)
def get_social_settings(
    location_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get social auto-responder settings."""
    location = _get_location(db, location_id, account)
    settings = _get_or_create_settings(db, location.id)
    return SocialSettingsResponse(
        auto_respond_enabled=settings.auto_respond_enabled,
        auto_respond_dms=settings.auto_respond_dms,
        auto_respond_comments=settings.auto_respond_comments,
        response_delay_seconds=settings.response_delay_seconds,
        excluded_keywords=[item.strip() for item in (settings.excluded_keywords or "").split(",") if item.strip()],
        high_priority_alerts_enabled=settings.high_priority_alerts_enabled,
        high_priority_alert_channel=settings.high_priority_alert_channel,
    )


@router.put("/{location_id}/settings", response_model=SocialSettingsResponse)
def update_social_settings(
    location_id: str,
    request: UpdateSocialSettingsRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Update social auto-responder settings."""
    location = _get_location(db, location_id, account)
    if (
        request.auto_respond_enabled is True
        or request.auto_respond_dms is True
        or request.auto_respond_comments is True
    ):
        FeatureAccessService(db).check_feature_access(account, "social_auto_responder")
    settings = _get_or_create_settings(db, location.id)
    if request.auto_respond_enabled is not None:
        settings.auto_respond_enabled = request.auto_respond_enabled
    if request.auto_respond_dms is not None:
        settings.auto_respond_dms = request.auto_respond_dms
    if request.auto_respond_comments is not None:
        settings.auto_respond_comments = request.auto_respond_comments
    if request.response_delay_seconds is not None:
        settings.response_delay_seconds = request.response_delay_seconds
    if request.excluded_keywords is not None:
        settings.excluded_keywords = ",".join(request.excluded_keywords)
    if request.high_priority_alerts_enabled is not None:
        settings.high_priority_alerts_enabled = request.high_priority_alerts_enabled
    if request.high_priority_alert_channel is not None:
        settings.high_priority_alert_channel = request.high_priority_alert_channel
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return SocialSettingsResponse(
        auto_respond_enabled=settings.auto_respond_enabled,
        auto_respond_dms=settings.auto_respond_dms,
        auto_respond_comments=settings.auto_respond_comments,
        response_delay_seconds=settings.response_delay_seconds,
        excluded_keywords=[item.strip() for item in (settings.excluded_keywords or "").split(",") if item.strip()],
        high_priority_alerts_enabled=settings.high_priority_alerts_enabled,
        high_priority_alert_channel=settings.high_priority_alert_channel,
    )


@router.get("/{location_id}/stats", response_model=SocialStatsResponse)
def get_social_stats(
    location_id: str,
    days: int = 7,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get social auto-responder statistics from persisted audit logs."""
    location = _get_location(db, location_id, account)
    channel = _get_instagram_channel(db, location.id)
    settings = _get_or_create_settings(db, location.id)

    cutoff = datetime.now(UTC)
    cutoff = cutoff.replace(microsecond=0)
    if days > 0:
        from datetime import timedelta
        cutoff = cutoff - timedelta(days=days)

    base_query = db.query(SocialResponseLog).filter(
        SocialResponseLog.location_id == location.id,
        SocialResponseLog.created_at >= cutoff,
    )

    total_messages = base_query.count()
    successful_count = base_query.filter(SocialResponseLog.success.is_(True)).count()
    failed_responses = base_query.filter(SocialResponseLog.success.is_(False)).count()
    auto_responded = base_query.filter(
        SocialResponseLog.response_mode == SocialResponseMode.AUTO,
        SocialResponseLog.success.is_(True),
    ).count()
    manual_responses = base_query.filter(
        SocialResponseLog.response_mode == SocialResponseMode.MANUAL,
        SocialResponseLog.success.is_(True),
    ).count()

    response_logs = base_query.filter(
        SocialResponseLog.success.is_(True),
        SocialResponseLog.source_created_at.is_not(None),
        SocialResponseLog.responded_at.is_not(None),
    ).all()
    response_times = [
        (item.responded_at - item.source_created_at).total_seconds() / 60.0
        for item in response_logs
        if item.responded_at and item.source_created_at and item.responded_at >= item.source_created_at
    ]
    avg_response_time_minutes = round(sum(response_times) / len(response_times), 1) if response_times else 0.0
    response_rate = round((successful_count / total_messages) * 100, 1) if total_messages else 0.0
    sentiment_positive = base_query.filter(SocialResponseLog.sentiment == "positive").count()
    sentiment_neutral = base_query.filter(SocialResponseLog.sentiment == "neutral").count()
    sentiment_negative = base_query.filter(SocialResponseLog.sentiment == "negative").count()
    last_successful_log = (
        base_query.filter(SocialResponseLog.success.is_(True))
        .order_by(SocialResponseLog.responded_at.desc(), SocialResponseLog.created_at.desc())
        .first()
    )
    last_failed_log = (
        base_query.filter(SocialResponseLog.success.is_(False))
        .order_by(SocialResponseLog.responded_at.desc(), SocialResponseLog.created_at.desc())
        .first()
    )
    if not channel:
        automation_health = "disconnected"
        automation_health_reason = "Instagram is not connected."
    elif not settings.auto_respond_enabled:
        automation_health = "paused"
        automation_health_reason = "Automatic responses are disabled."
    elif not settings.auto_respond_dms and not settings.auto_respond_comments:
        automation_health = "partial"
        automation_health_reason = "Automatic responses are enabled, but both DMs and comments are turned off."
    else:
        automation_health = "ready"
        automation_health_reason = "Automation is connected and ready."

    return SocialStatsResponse(
        total_messages=total_messages,
        auto_responded=auto_responded,
        manual_responses=manual_responses,
        failed_responses=failed_responses,
        avg_response_time_minutes=avg_response_time_minutes,
        response_rate=response_rate,
        sentiment_positive=sentiment_positive,
        sentiment_neutral=sentiment_neutral,
        sentiment_negative=sentiment_negative,
        last_successful_response_at=(
            last_successful_log.responded_at if last_successful_log else None
        ),
        last_failed_response_at=(
            last_failed_log.responded_at if last_failed_log else None
        ),
        automation_health=automation_health,
        automation_health_reason=automation_health_reason,
    )
