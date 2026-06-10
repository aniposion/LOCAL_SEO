"""P3: Call & SMS schemas."""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ====================
# Call Log Schemas
# ====================

class CallLogResponse(BaseModel):
    """Call log entry."""
    id: UUID
    location_id: UUID
    caller_phone: str
    masked_phone: str  # For privacy display
    direction: str  # inbound, outbound
    status: str  # missed, answered, voicemail
    duration_seconds: Optional[int]
    call_started_at: datetime
    call_ended_at: Optional[datetime]
    text_back_sent: bool
    text_back_at: Optional[datetime]
    text_back_response: Optional[str]
    recording_url: Optional[str]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CallLogList(BaseModel):
    """List of call logs."""
    items: list[CallLogResponse]
    total: int
    total_missed: int
    total_answered: int
    text_back_rate: float  # % of missed calls with text back


# ====================
# Text Back Settings
# ====================

class TextBackSettingsCreate(BaseModel):
    """Create text back settings for location."""
    enabled: bool = True
    
    # Response time
    delay_seconds: int = Field(
        default=60,
        ge=30,
        le=300,
        description="Seconds to wait before sending (30-300)"
    )
    
    # Business hours only
    respect_business_hours: bool = True
    
    # Templates
    default_message: str = Field(
        default="안녕하세요! 방금 전화 주셨군요. 지금 통화가 어려워 문자 드립니다. "
                "어떤 용건이신가요? 빠르게 답변 드리겠습니다.",
        max_length=500,
    )
    
    after_hours_message: Optional[str] = Field(
        default="안녕하세요! 현재 영업시간 외입니다. "
                "내일 영업 시작하면 바로 연락 드리겠습니다. "
                "급한 용건은 문자로 남겨주세요!",
        max_length=500,
    )
    
    # Quick replies
    enable_quick_replies: bool = True
    quick_reply_options: list[str] = Field(
        default=[
            "예약 문의",
            "가격 문의",
            "영업시간 문의",
            "기타 문의",
        ]
    )


class TextBackSettingsUpdate(BaseModel):
    """Update text back settings."""
    enabled: Optional[bool] = None
    delay_seconds: Optional[int] = Field(None, ge=30, le=300)
    respect_business_hours: Optional[bool] = None
    default_message: Optional[str] = Field(None, max_length=500)
    after_hours_message: Optional[str] = Field(None, max_length=500)
    enable_quick_replies: Optional[bool] = None
    quick_reply_options: Optional[list[str]] = None


class TextBackSettingsResponse(BaseModel):
    """Text back settings response."""
    id: UUID
    location_id: UUID
    enabled: bool
    delay_seconds: int
    respect_business_hours: bool
    default_message: str
    after_hours_message: Optional[str]
    enable_quick_replies: bool
    quick_reply_options: list[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ====================
# SMS Thread Schemas
# ====================

class SMSMessage(BaseModel):
    """Single SMS message."""
    id: UUID
    direction: str  # inbound, outbound
    body: str
    sent_at: datetime
    status: str  # sent, delivered, failed
    is_read: bool


class SMSThreadResponse(BaseModel):
    """SMS conversation thread."""
    id: UUID
    location_id: UUID
    customer_phone: str
    masked_phone: str
    customer_name: Optional[str]
    last_message_at: datetime
    last_message_preview: str
    unread_count: int
    messages: list[SMSMessage] = []

    class Config:
        from_attributes = True


class SMSThreadList(BaseModel):
    """List of SMS threads."""
    items: list[SMSThreadResponse]
    total: int
    total_unread: int


class SMSSendRequest(BaseModel):
    """Send SMS in thread."""
    body: str = Field(..., min_length=1, max_length=1600)


class SMSSendResponse(BaseModel):
    """Send SMS response."""
    message_id: UUID
    status: str
    sent_at: datetime


# ====================
# Analytics Schemas
# ====================

class CallAnalytics(BaseModel):
    """Call analytics summary."""
    period_start: datetime
    period_end: datetime
    
    # Call stats
    total_calls: int
    total_missed: int
    total_answered: int
    miss_rate: float
    
    # Text back stats
    text_backs_sent: int
    text_back_rate: float
    response_rate: float  # Customer replies to text back
    
    # Conversion
    estimated_saves: int  # Customers who might have been lost
    save_rate: float
    
    # Time breakdown
    busiest_hour: int
    busiest_day: str
    calls_by_hour: dict[int, int]
    calls_by_day: dict[str, int]


class CallStatsDaily(BaseModel):
    """Daily call stats for charts."""
    date: str
    total: int
    missed: int
    answered: int
    text_backs: int
