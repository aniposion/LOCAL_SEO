"""
Social Auto-Responder Router
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.routers.deps import get_current_account, get_db
from app.models.account import Account
from app.services.social_responder import SocialResponderService, ResponseType

router = APIRouter(prefix="/social", tags=["Social"])


# ============ Schemas ============

class SocialMessageResponse(BaseModel):
    id: str
    platform: str
    type: str
    sender_id: str
    sender_name: str
    message: str
    post_id: Optional[str] = None
    created_at: datetime
    suggested_response: Optional[str] = None


class MessagesListResponse(BaseModel):
    messages: list[SocialMessageResponse]
    total: int


class SendResponseRequest(BaseModel):
    message_id: str
    response_text: str


class GenerateResponseRequest(BaseModel):
    message_text: str
    message_type: str = "dm"


class SocialSettingsResponse(BaseModel):
    auto_respond_enabled: bool
    auto_respond_dms: bool
    auto_respond_comments: bool
    response_delay_seconds: int
    excluded_keywords: list[str]


class UpdateSocialSettingsRequest(BaseModel):
    auto_respond_enabled: Optional[bool] = None
    auto_respond_dms: Optional[bool] = None
    auto_respond_comments: Optional[bool] = None
    response_delay_seconds: Optional[int] = None
    excluded_keywords: Optional[list[str]] = None


class SocialStatsResponse(BaseModel):
    total_messages: int
    auto_responded: int
    manual_responses: int
    avg_response_time_minutes: float
    response_rate: float
    sentiment_positive: int
    sentiment_neutral: int
    sentiment_negative: int


# ============ Endpoints ============

@router.get("/{location_id}/messages", response_model=MessagesListResponse)
async def get_pending_messages(
    location_id: str,
    platform: str = "instagram",
    message_type: Optional[str] = None,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get pending messages that need responses."""
    from app.models.location import Location
    
    location = db.query(Location).filter(
        Location.id == location_id,
        Location.account_id == account.id
    ).first()
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    service = SocialResponderService()
    messages = await service.get_pending_messages(location_id, platform)
    
    # Filter by type if specified
    if message_type:
        messages = [m for m in messages if m.type.value == message_type]
    
    # Generate suggested responses
    business_info = {
        "address": location.address,
        "phone": location.phone,
        "category": location.category,
    }
    
    response_messages = []
    for msg in messages:
        suggested = await service.generate_response(msg, location.name, business_info)
        response_messages.append(SocialMessageResponse(
            id=msg.id,
            platform=msg.platform,
            type=msg.type.value,
            sender_id=msg.sender_id,
            sender_name=msg.sender_name,
            message=msg.message,
            post_id=msg.post_id,
            created_at=msg.created_at or datetime.now(),
            suggested_response=suggested,
        ))
    
    return MessagesListResponse(
        messages=response_messages,
        total=len(response_messages),
    )


@router.post("/{location_id}/respond")
async def send_response(
    location_id: str,
    request: SendResponseRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Send a response to a message."""
    from app.models.location import Location
    from app.services.social_responder import SocialMessage
    
    location = db.query(Location).filter(
        Location.id == location_id,
        Location.account_id == account.id
    ).first()
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    service = SocialResponderService()
    
    # Create a dummy message object for sending
    message = SocialMessage(
        id=request.message_id,
        platform="instagram",
        type=ResponseType.DM,
        sender_id="",
        sender_name="",
        message="",
    )
    
    result = await service.send_response(message, request.response_text)
    
    return {
        "success": result.success,
        "message": "Response sent successfully" if result.success else "Failed to send response",
        "sent_at": result.sent_at.isoformat(),
    }


@router.post("/{location_id}/generate-response")
async def generate_response(
    location_id: str,
    request: GenerateResponseRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Generate an AI response for a message."""
    from app.models.location import Location
    from app.services.social_responder import SocialMessage
    
    location = db.query(Location).filter(
        Location.id == location_id,
        Location.account_id == account.id
    ).first()
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    service = SocialResponderService()
    
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
        "category": location.category,
    }
    
    response = await service.generate_response(message, location.name, business_info)
    
    return {"suggested_response": response}


@router.post("/{location_id}/auto-respond")
async def auto_respond_all(
    location_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Auto-respond to all pending messages."""
    from app.models.location import Location
    
    location = db.query(Location).filter(
        Location.id == location_id,
        Location.account_id == account.id
    ).first()
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    service = SocialResponderService()
    
    business_info = {
        "address": location.address,
        "phone": location.phone,
        "category": location.category,
    }
    
    results = await service.auto_respond_all(location_id, location.name, business_info)
    
    success_count = sum(1 for r in results if r.success)
    
    return {
        "total_processed": len(results),
        "success_count": success_count,
        "failed_count": len(results) - success_count,
    }


@router.get("/{location_id}/settings", response_model=SocialSettingsResponse)
async def get_social_settings(
    location_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get social auto-responder settings."""
    # Demo settings
    return SocialSettingsResponse(
        auto_respond_enabled=True,
        auto_respond_dms=True,
        auto_respond_comments=False,
        response_delay_seconds=60,
        excluded_keywords=["spam", "unsubscribe"],
    )


@router.put("/{location_id}/settings", response_model=SocialSettingsResponse)
async def update_social_settings(
    location_id: str,
    request: UpdateSocialSettingsRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Update social auto-responder settings."""
    # In production, save to database
    return SocialSettingsResponse(
        auto_respond_enabled=request.auto_respond_enabled if request.auto_respond_enabled is not None else True,
        auto_respond_dms=request.auto_respond_dms if request.auto_respond_dms is not None else True,
        auto_respond_comments=request.auto_respond_comments if request.auto_respond_comments is not None else False,
        response_delay_seconds=request.response_delay_seconds or 60,
        excluded_keywords=request.excluded_keywords or [],
    )


@router.get("/{location_id}/stats", response_model=SocialStatsResponse)
async def get_social_stats(
    location_id: str,
    days: int = 7,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get social auto-responder statistics."""
    service = SocialResponderService()
    stats = service.get_response_stats(location_id, days)
    
    return SocialStatsResponse(**stats)
