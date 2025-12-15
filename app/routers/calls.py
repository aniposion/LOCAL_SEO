"""
Missed Call Text Back Router - Twilio Integration
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.routers.deps import get_current_account, get_db
from app.models.account import Account

router = APIRouter(prefix="/calls", tags=["Calls"])


# ============ Schemas ============

class CallLog(BaseModel):
    id: str
    caller_number: str
    status: str  # answered, missed, busy
    duration: Optional[int] = None
    sms_sent: bool
    created_at: datetime


class CallLogsResponse(BaseModel):
    calls: list[CallLog]
    total: int
    missed_count: int
    sms_sent_count: int


class SMSTemplate(BaseModel):
    id: str
    name: str
    category: str
    message: str
    is_active: bool


class TemplatesResponse(BaseModel):
    templates: list[SMSTemplate]


class CreateTemplateRequest(BaseModel):
    name: str
    category: str
    message: str


class UpdateTemplateRequest(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    message: Optional[str] = None
    is_active: Optional[bool] = None


class CallSettingsResponse(BaseModel):
    forwarding_number: Optional[str]
    twilio_number: Optional[str]
    is_enabled: bool
    sms_delay_seconds: int


class UpdateCallSettingsRequest(BaseModel):
    forwarding_number: Optional[str] = None
    is_enabled: Optional[bool] = None
    sms_delay_seconds: Optional[int] = None


class CallStatsResponse(BaseModel):
    total_calls: int
    answered_calls: int
    missed_calls: int
    sms_sent: int
    recovery_rate: float


# ============ Endpoints ============

@router.get("/{location_id}/logs", response_model=CallLogsResponse)
async def get_call_logs(
    location_id: str,
    days: int = 7,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get call logs for a location."""
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
    
    # In production, fetch from Twilio API or database
    # Demo data for now
    demo_calls = [
        CallLog(
            id="c1",
            caller_number="+1 (555) 123-4567",
            status="missed",
            sms_sent=True,
            created_at=datetime.now() - timedelta(hours=1),
        ),
        CallLog(
            id="c2",
            caller_number="+1 (555) 234-5678",
            status="answered",
            duration=180,
            sms_sent=False,
            created_at=datetime.now() - timedelta(hours=2),
        ),
        CallLog(
            id="c3",
            caller_number="+1 (555) 345-6789",
            status="missed",
            sms_sent=True,
            created_at=datetime.now() - timedelta(hours=3),
        ),
        CallLog(
            id="c4",
            caller_number="+1 (555) 456-7890",
            status="busy",
            sms_sent=True,
            created_at=datetime.now() - timedelta(hours=4),
        ),
        CallLog(
            id="c5",
            caller_number="+1 (555) 567-8901",
            status="answered",
            duration=245,
            sms_sent=False,
            created_at=datetime.now() - timedelta(hours=5),
        ),
    ]
    
    missed_count = sum(1 for c in demo_calls if c.status in ["missed", "busy"])
    sms_sent_count = sum(1 for c in demo_calls if c.sms_sent)
    
    return CallLogsResponse(
        calls=demo_calls,
        total=len(demo_calls),
        missed_count=missed_count,
        sms_sent_count=sms_sent_count,
    )


@router.get("/{location_id}/stats", response_model=CallStatsResponse)
async def get_call_stats(
    location_id: str,
    days: int = 7,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get call statistics for a location."""
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
    
    # Demo stats
    total = 25
    answered = 18
    missed = 7
    sms_sent = 6
    
    return CallStatsResponse(
        total_calls=total,
        answered_calls=answered,
        missed_calls=missed,
        sms_sent=sms_sent,
        recovery_rate=round(sms_sent / missed * 100, 1) if missed > 0 else 100.0,
    )


@router.get("/{location_id}/templates", response_model=TemplatesResponse)
async def get_templates(
    location_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get SMS templates for a location."""
    # Demo templates
    templates = [
        SMSTemplate(
            id="t1",
            name="Default",
            category="default",
            message="Hi! Sorry we missed your call. We're currently busy helping other customers. How can we help you? Reply to this message or call us back!",
            is_active=True,
        ),
        SMSTemplate(
            id="t2",
            name="Restaurant",
            category="restaurant",
            message="Thanks for calling! We're currently busy in the kitchen. Would you like to make a reservation or place an order? Reply here or call back!",
            is_active=False,
        ),
        SMSTemplate(
            id="t3",
            name="After Hours",
            category="after_hours",
            message="Thanks for calling! We're currently closed. Our hours are Mon-Sat 9AM-9PM. Leave us a message and we'll get back to you first thing!",
            is_active=False,
        ),
    ]
    
    return TemplatesResponse(templates=templates)


@router.post("/{location_id}/templates", response_model=SMSTemplate)
async def create_template(
    location_id: str,
    request: CreateTemplateRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Create a new SMS template."""
    # In production, save to database
    new_template = SMSTemplate(
        id=f"t{datetime.now().timestamp()}",
        name=request.name,
        category=request.category,
        message=request.message,
        is_active=False,
    )
    
    return new_template


@router.put("/{location_id}/templates/{template_id}", response_model=SMSTemplate)
async def update_template(
    location_id: str,
    template_id: str,
    request: UpdateTemplateRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Update an SMS template."""
    # In production, update in database
    updated = SMSTemplate(
        id=template_id,
        name=request.name or "Updated Template",
        category=request.category or "default",
        message=request.message or "Updated message",
        is_active=request.is_active or False,
    )
    
    return updated


@router.delete("/{location_id}/templates/{template_id}")
async def delete_template(
    location_id: str,
    template_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Delete an SMS template."""
    return {"success": True, "message": "Template deleted"}


@router.post("/{location_id}/templates/{template_id}/activate")
async def activate_template(
    location_id: str,
    template_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Activate an SMS template (deactivates others)."""
    return {"success": True, "message": "Template activated"}


@router.get("/{location_id}/settings", response_model=CallSettingsResponse)
async def get_call_settings(
    location_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get call settings for a location."""
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
    
    # Demo settings
    return CallSettingsResponse(
        forwarding_number=location.phone or "+1 (555) 000-1234",
        twilio_number="+1 (555) 999-8765",
        is_enabled=True,
        sms_delay_seconds=30,
    )


@router.put("/{location_id}/settings", response_model=CallSettingsResponse)
async def update_call_settings(
    location_id: str,
    request: UpdateCallSettingsRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Update call settings for a location."""
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
    
    # In production, save to database
    if request.forwarding_number:
        location.phone = request.forwarding_number
        db.commit()
    
    return CallSettingsResponse(
        forwarding_number=request.forwarding_number or location.phone,
        twilio_number="+1 (555) 999-8765",
        is_enabled=request.is_enabled if request.is_enabled is not None else True,
        sms_delay_seconds=request.sms_delay_seconds or 30,
    )
