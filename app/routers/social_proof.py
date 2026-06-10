"""Neighborhood Social Proof API endpoints."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.rate_limiter import check_rate_limit, record_rate_limit_usage
from app.db.session import get_db
from app.models.account import Account
from app.models.location import Location
from app.routers.deps import get_current_account
from app.schemas.social_proof import (
    ApproveCardRequest,
    AutoGenerateCardsRequest,
    GenerateCardRequest,
    RejectCardRequest,
    SocialProofHistoryResponse,
    SocialProofCardResponse,
    SocialProofScheduleCreate,
    SocialProofScheduleResponse,
    SocialProofScheduleUpdate,
)
from app.services.social_proof_service import SocialProofService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/social-proof", tags=["Social Proof"])


def _require_owned_location(db: Session, location_id: UUID, account_id: UUID) -> Location:
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == account_id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return location


def _is_chargeable_card(card) -> bool:
    """Only charge when a composed final card asset exists."""
    return bool(getattr(card, "final_card_url", None))


@router.post("/generate-card", response_model=SocialProofCardResponse)
async def generate_social_proof_card(
    request: GenerateCardRequest,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> SocialProofCardResponse:
    """
    Generate a social proof card from a review.

    Creates an Instagram-ready card news image with AI-generated background
    (using Imagen 3) and formatted review text overlay.
    """
    try:
        _require_owned_location(db, request.location_id, current_account.id)
        # Check rate limit
        await check_rate_limit(
            request=None, db=db, account_id=current_account.id, feature="social_proof_cards"
        )

        service = SocialProofService(db)
        card = await service.generate_card(request)
        if _is_chargeable_card(card):
            record_rate_limit_usage(db, current_account.id, "social_proof_cards")
        return SocialProofCardResponse.model_validate(card)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating card: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate social proof card",
        )


@router.post("/auto-generate", response_model=list[SocialProofCardResponse])
async def auto_generate_cards(
    request: AutoGenerateCardsRequest,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> list[SocialProofCardResponse]:
    """
    Auto-generate cards from best reviews.

    Automatically selects the best reviews based on rating and content quality,
    then generates social proof cards for each.
    """
    try:
        _require_owned_location(db, request.location_id, current_account.id)
        # Check rate limit
        await check_rate_limit(
            request=None,
            db=db,
            account_id=current_account.id,
            feature="social_proof_cards",
            count=request.max_cards,
        )

        service = SocialProofService(db)
        cards = await service.auto_generate_cards(request)
        chargeable_count = sum(1 for card in cards if _is_chargeable_card(card))
        if chargeable_count:
            record_rate_limit_usage(
                db, current_account.id, "social_proof_cards", count=chargeable_count
            )
        return [SocialProofCardResponse.model_validate(c) for c in cards]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error auto-generating cards: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to auto-generate cards",
        )


@router.get("/pending", response_model=list[SocialProofCardResponse])
async def get_pending_cards(
    location_id: Optional[UUID] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> list[SocialProofCardResponse]:
    """
    Get pending social proof cards awaiting approval.
    """
    try:
        allowed_location_ids = {
            location_id
            for (location_id,) in db.query(Location.id)
            .filter(Location.account_id == current_account.id)
            .all()
        }
        if location_id is not None and location_id not in allowed_location_ids:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

        service = SocialProofService(db)
        cards = service.get_pending_cards(location_id=location_id, limit=limit, offset=offset)
        cards = [card for card in cards if card.location_id in allowed_location_ids]
        return [SocialProofCardResponse.model_validate(c) for c in cards]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pending cards: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pending cards",
        )


@router.get("/history/{location_id}", response_model=SocialProofHistoryResponse)
async def get_card_history(
    location_id: UUID,
    status_filter: str = "all",
    search: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> SocialProofHistoryResponse:
    """Get social proof card history and operational metrics for a location."""
    try:
        _require_owned_location(db, location_id, current_account.id)
        service = SocialProofService(db)
        return service.get_history(
            location_id=location_id,
            status_filter=status_filter,
            search=search,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting social proof history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get social proof history",
        )


@router.post("/{card_id}/approve", response_model=SocialProofCardResponse)
async def approve_card(
    card_id: int,
    request: ApproveCardRequest,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> SocialProofCardResponse:
    """
    Approve a social proof card.

    Optionally publishes the card immediately to specified social media platforms.
    """
    try:
        from app.models.social_proof import SocialProofCard

        existing = db.query(SocialProofCard).filter(SocialProofCard.id == card_id).first()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
        _require_owned_location(db, existing.location_id, current_account.id)

        service = SocialProofService(db)
        card = await service.approve_card(
            card_id=card_id,
            account_id=current_account.id,
            publish_immediately=request.publish_immediately,
        )
        return SocialProofCardResponse.model_validate(card)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving card: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve card",
        )


@router.post("/{card_id}/reject", response_model=SocialProofCardResponse)
async def reject_card(
    card_id: int,
    request: RejectCardRequest,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> SocialProofCardResponse:
    """
    Reject a social proof card.
    """
    try:
        from app.models.social_proof import SocialProofCard

        existing = db.query(SocialProofCard).filter(SocialProofCard.id == card_id).first()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
        _require_owned_location(db, existing.location_id, current_account.id)

        service = SocialProofService(db)
        card = await service.reject_card(
            card_id=card_id, account_id=current_account.id, reason=request.reason
        )
        return SocialProofCardResponse.model_validate(card)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting card: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject card",
        )


@router.get("/{card_id}", response_model=SocialProofCardResponse)
async def get_card(
    card_id: int,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> SocialProofCardResponse:
    """
    Get a specific social proof card by ID.
    """
    from app.models.social_proof import SocialProofCard

    card = db.query(SocialProofCard).filter(SocialProofCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    location = (
        db.query(Location)
        .filter(Location.id == card.location_id, Location.account_id == current_account.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

    return SocialProofCardResponse.model_validate(card)


# Schedule endpoints
@router.post("/schedule", response_model=SocialProofScheduleResponse)
async def create_schedule(
    request: SocialProofScheduleCreate,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> SocialProofScheduleResponse:
    """
    Create an automatic schedule for social proof card generation.

    Sets up weekly/monthly automatic generation of cards from best reviews.
    """
    from app.models.social_proof import SocialProofSchedule

    _require_owned_location(db, request.location_id, current_account.id)
    schedule = SocialProofSchedule(**request.model_dump())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)

    return SocialProofScheduleResponse.model_validate(schedule)


@router.get("/schedule/{location_id}", response_model=SocialProofScheduleResponse)
async def get_schedule(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> SocialProofScheduleResponse:
    """
    Get the schedule for a location.
    """
    from app.models.social_proof import SocialProofSchedule

    schedule = (
        db.query(SocialProofSchedule)
        .filter(SocialProofSchedule.location_id == location_id)
        .first()
    )

    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    _require_owned_location(db, location_id, current_account.id)

    return SocialProofScheduleResponse.model_validate(schedule)


@router.patch("/schedule/{schedule_id}", response_model=SocialProofScheduleResponse)
async def update_schedule(
    schedule_id: int,
    request: SocialProofScheduleUpdate,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> SocialProofScheduleResponse:
    """
    Update schedule settings.
    """
    from app.models.social_proof import SocialProofSchedule

    schedule = (
        db.query(SocialProofSchedule).filter(SocialProofSchedule.id == schedule_id).first()
    )

    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    _require_owned_location(db, schedule.location_id, current_account.id)

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(schedule, field, value)

    db.commit()
    db.refresh(schedule)

    return SocialProofScheduleResponse.model_validate(schedule)


@router.delete("/schedule/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> None:
    """
    Delete a schedule.
    """
    from app.models.social_proof import SocialProofSchedule

    schedule = (
        db.query(SocialProofSchedule).filter(SocialProofSchedule.id == schedule_id).first()
    )

    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    _require_owned_location(db, schedule.location_id, current_account.id)

    db.delete(schedule)
    db.commit()
