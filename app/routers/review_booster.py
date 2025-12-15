"""Review Booster Program router."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.routers.deps import get_current_user
from app.models.account import Account
from app.services.review_booster import ReviewBoosterService, ReviewRequestChannel

router = APIRouter(prefix="/review-booster", tags=["review-booster"])


# ============ Schemas ============

class ReviewRequestSingle(BaseModel):
    """Request to send a single review request."""
    location_id: UUID
    customer_name: str = Field(..., min_length=1)
    customer_email: EmailStr | None = None
    customer_phone: str | None = None
    channel: str = Field(default="both", description="sms, email, or both")


class ReviewRequestBulk(BaseModel):
    """Request to send bulk review requests."""
    location_id: UUID
    customers: list[dict] = Field(
        ...,
        description="List of {name, email, phone}",
        min_length=1,
    )
    channel: str = Field(default="both")


class ReviewAnalyticsRequest(BaseModel):
    """Request for review analytics."""
    location_id: UUID
    days: int = Field(default=30, ge=7, le=365)


# ============ Endpoints ============

@router.post("/send-request")
async def send_review_request(
    request: ReviewRequestSingle,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Send a review request to a single customer.
    
    The customer will receive an SMS and/or email with a link
    to leave a Google review.
    """
    # Validate channel
    try:
        channel = ReviewRequestChannel(request.channel.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid channel. Use 'sms', 'email', or 'both'",
        )

    # Validate contact info
    if channel == ReviewRequestChannel.SMS and not request.customer_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number required for SMS channel",
        )
    if channel == ReviewRequestChannel.EMAIL and not request.customer_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email required for email channel",
        )

    service = ReviewBoosterService(db)
    result = await service.send_review_request(
        location_id=request.location_id,
        customer_name=request.customer_name,
        customer_email=request.customer_email,
        customer_phone=request.customer_phone,
        channel=channel,
    )

    return result


@router.post("/send-bulk")
async def send_bulk_review_requests(
    request: ReviewRequestBulk,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Send review requests to multiple customers at once.
    
    Useful for sending requests after a busy day or event.
    """
    try:
        channel = ReviewRequestChannel(request.channel.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid channel",
        )

    service = ReviewBoosterService(db)
    result = await service.send_bulk_review_requests(
        location_id=request.location_id,
        customers=request.customers,
        channel=channel,
    )

    return result


@router.get("/analytics/{location_id}")
async def get_review_analytics(
    location_id: UUID,
    days: int = 30,
    current_user: Annotated[Account, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Get review analytics and trends for a location.
    
    Returns:
    - Total reviews in period
    - Average rating
    - Weekly breakdown
    - Growth rate
    - Projected monthly reviews
    """
    service = ReviewBoosterService(db)
    result = await service.get_review_analytics(
        location_id=location_id,
        days=days,
    )

    return result


@router.get("/templates")
async def get_review_request_templates(
    category: str = "default",
):
    """
    Get available review request templates by business category.
    """
    templates = ReviewBoosterService.REQUEST_TEMPLATES.get(
        category,
        ReviewBoosterService.REQUEST_TEMPLATES["default"],
    )

    return {
        "category": category,
        "templates": {
            "sms": templates["sms"],
            "email_subject": templates["email_subject"],
            "email_body_preview": templates["email_body"][:200] + "...",
        },
        "available_categories": list(ReviewBoosterService.REQUEST_TEMPLATES.keys()),
    }


@router.post("/handle-webhook")
async def handle_review_webhook(
    location_id: UUID,
    review_data: dict,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Handle incoming review webhook from Google.
    
    Routes positive reviews to thank the customer,
    and negative reviews to internal handling.
    """
    service = ReviewBoosterService(db)
    result = await service.handle_new_review(
        location_id=location_id,
        review_data=review_data,
    )

    return result
