"""P3: Calls & SMS Router - aligned with existing models."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account
from app.models.calls import SMSThread
from app.models.location import Location
from app.routers.deps import get_current_account
from app.services.call_text_back_service import SMSUsageLimitError, get_call_text_back_service
from app.services.feature_access import FeatureAccessService
from app.services.twilio_service import TwilioDeliveryError, TwilioUnavailableError

router = APIRouter(prefix="/calls", tags=["Calls"])


class CallLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    caller_phone: str
    masked_phone: str
    call_status: str
    call_duration: int
    sms_sent: bool
    sms_sent_at: Optional[datetime]
    created_at: datetime


class CallStatsResponse(BaseModel):
    total_calls: int
    missed_calls: int
    answered_calls: int
    text_backs_sent: int
    text_back_rate: float


class ThreadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_phone: str
    status: str
    last_message_at: Optional[datetime]
    unread_count: int
    created_at: datetime


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    direction: str
    body: str
    status: Optional[str]
    created_at: datetime


class SettingsResponse(BaseModel):
    twilio_number: str
    forward_to: str
    missed_call_sms_enabled: bool
    sms_template: str


class SendMessageRequest(BaseModel):
    body: str


class UpdateSettingsRequest(BaseModel):
    enabled: Optional[bool] = None
    sms_template: Optional[str] = None


def _mask_phone(phone: str) -> str:
    if len(phone) >= 8:
        return phone[:3] + "****" + phone[-4:]
    return "****"


def _get_owned_location(db: Session, location_id: UUID, account_id: UUID) -> Location:
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == account_id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location


def _get_owned_thread(db: Session, location_id: UUID, thread_id: UUID, account_id: UUID) -> SMSThread:
    thread = (
        db.query(SMSThread)
        .filter(SMSThread.id == thread_id, SMSThread.location_id == location_id)
        .first()
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    _get_owned_location(db, location_id, account_id)
    return thread


@router.get("/{location_id}/logs")
def get_call_logs(
    location_id: UUID,
    status: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=90),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    _get_owned_location(db, location_id, current_user.id)
    logs = get_call_text_back_service(db).get_call_logs(location_id, status, days, limit)
    return {
        "items": [
            {
                "id": str(log.id),
                "caller_phone": log.caller_number,
                "masked_phone": _mask_phone(log.caller_number),
                "call_status": log.call_status,
                "call_duration": log.call_duration,
                "sms_sent": log.sms_sent,
                "sms_sent_at": log.sms_sent_at,
                "created_at": log.created_at,
            }
            for log in logs
        ],
        "total": len(logs),
    }


@router.get("/{location_id}/stats")
def get_call_stats(
    location_id: UUID,
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    _get_owned_location(db, location_id, current_user.id)
    return get_call_text_back_service(db).get_call_stats(location_id, days)


@router.get("/{location_id}/threads")
def get_threads(
    location_id: UUID,
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    _get_owned_location(db, location_id, current_user.id)
    threads = get_call_text_back_service(db).get_threads(location_id, None, limit)
    if unread_only:
        threads = [thread for thread in threads if thread.unread_count > 0]
    total_unread = sum(thread.unread_count for thread in threads)
    return {
        "items": [
            {
                "id": str(thread.id),
                "customer_phone": thread.customer_phone,
                "masked_phone": _mask_phone(thread.customer_phone),
                "status": thread.status.value if hasattr(thread.status, "value") else str(thread.status),
                "last_message_at": thread.last_message_at,
                "unread_count": thread.unread_count,
                "created_at": thread.created_at,
            }
            for thread in threads
        ],
        "total": len(threads),
        "total_unread": total_unread,
    }


@router.get("/{location_id}/threads/{thread_id}")
def get_thread_messages(
    location_id: UUID,
    thread_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    _get_owned_thread(db, location_id, thread_id, current_user.id)
    messages = get_call_text_back_service(db).get_thread_messages(thread_id, limit)
    return {
        "messages": [
            {
                "id": str(message.id),
                "direction": message.direction.value if hasattr(message.direction, "value") else str(message.direction),
                "body": message.body,
                "status": message.status,
                "created_at": message.created_at,
            }
            for message in messages
        ]
    }


@router.post("/{location_id}/threads/{thread_id}/send")
async def send_message(
    location_id: UUID,
    thread_id: UUID,
    payload: Optional[SendMessageRequest] = Body(default=None),
    body_query: Optional[str] = Query(default=None, alias="body", min_length=1, max_length=1000),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    _get_owned_thread(db, location_id, thread_id, current_user.id)
    message_body = payload.body.strip() if payload and payload.body else None
    if not message_body and body_query:
        message_body = body_query.strip()
    if not message_body:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message body is required")

    FeatureAccessService(db).check_feature_access(current_user, "missed_call_text_back")

    try:
        message = await get_call_text_back_service(db).send_sms(thread_id, message_body)
    except SMSUsageLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=exc.detail) from exc
    except TwilioUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except TwilioDeliveryError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"success": True, "message_id": str(message.id), "status": message.status}


@router.post("/{location_id}/threads/{thread_id}/read")
def mark_thread_read(
    location_id: UUID,
    thread_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    thread = _get_owned_thread(db, location_id, thread_id, current_user.id)
    thread.unread_count = 0
    db.commit()
    return {"success": True}


@router.get("/{location_id}/settings")
def get_settings(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    _get_owned_location(db, location_id, current_user.id)
    settings = get_call_text_back_service(db).get_settings(location_id)
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Settings not found. Please configure a Twilio number first.",
        )
    return {
        "twilio_number": settings.twilio_number,
        "forward_to": settings.forward_to,
        "enabled": settings.missed_call_sms_enabled,
        "sms_template": settings.sms_template,
    }


@router.put("/{location_id}/settings")
def update_settings(
    location_id: UUID,
    payload: Optional[UpdateSettingsRequest] = Body(default=None),
    enabled_query: Optional[bool] = Query(default=None, alias="enabled"),
    sms_template_query: Optional[str] = Query(default=None, alias="sms_template"),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    _get_owned_location(db, location_id, current_user.id)
    enabled = payload.enabled if payload and payload.enabled is not None else enabled_query
    sms_template = payload.sms_template if payload and payload.sms_template is not None else sms_template_query

    if enabled is True:
        FeatureAccessService(db).check_feature_access(current_user, "missed_call_text_back")

    settings = get_call_text_back_service(db).update_settings(location_id, enabled, sms_template)
    if not settings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Settings not found")
    return {
        "success": True,
        "enabled": settings.missed_call_sms_enabled,
        "sms_template": settings.sms_template,
    }
