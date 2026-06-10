"""Onboarding progress API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account
from app.routers.deps import get_current_user
from app.services.onboarding_service import OnboardingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class CompleteStepRequest(BaseModel):
    """Request to complete onboarding step."""

    step: str


@router.get("/progress")
async def get_onboarding_progress(
    current_user: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current account's onboarding progress."""
    service = OnboardingService(db)
    return service.get_progress(current_user.id)


@router.post("/complete-step")
async def complete_onboarding_step(
    request: CompleteStepRequest,
    current_user: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark an onboarding step as completed and return the updated progress."""
    service = OnboardingService(db)

    try:
        service.complete_step(
            account_id=current_user.id,
            step=request.step,
            event_account_id=current_user.id,
        )
        db.commit()
        return service.get_progress(current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        db.rollback()
        logger.error("Error completing onboarding step: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to complete step")


@router.get("/time-to-activation")
async def get_time_to_activation(
    current_user: Account = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return time-to-activation in minutes for the current account."""
    service = OnboardingService(db)
    time_minutes = service.calculate_time_to_activation(current_user.id)

    return {
        "time_to_activation_minutes": time_minutes,
        "completed": time_minutes is not None,
    }
