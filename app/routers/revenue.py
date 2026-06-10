"""Revenue profile API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account
from app.routers.deps import get_current_user
from app.schemas.revenue import (
    RevenueProfileCreate,
    RevenueProfileResponse,
    RevenueProfileUpdate,
    RevenueProjectionResponse,
)
from app.services.revenue_service import RevenueService

router = APIRouter(prefix="/revenue", tags=["revenue"])


@router.get("/{location_id}/profile", response_model=RevenueProfileResponse)
def get_revenue_profile(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> RevenueProfileResponse:
    """Get or create revenue profile for a location."""
    service = RevenueService(db)
    location = service.get_location_for_account(location_id, current_user.id)
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    profile = service.get_or_create_profile(location_id)
    return RevenueProfileResponse.model_validate(profile)


@router.put("/{location_id}/profile", response_model=RevenueProfileResponse)
def upsert_revenue_profile(
    location_id: UUID,
    payload: RevenueProfileCreate | RevenueProfileUpdate,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> RevenueProfileResponse:
    """Create or update revenue profile for a location."""
    service = RevenueService(db)
    location = service.get_location_for_account(location_id, current_user.id)
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    profile = service.update_profile(location_id, payload)
    return RevenueProfileResponse.model_validate(profile)


@router.get("/{location_id}/projection", response_model=RevenueProjectionResponse)
def get_revenue_projection(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> RevenueProjectionResponse:
    """Get revenue projection summary for a location."""
    service = RevenueService(db)
    location = service.get_location_for_account(location_id, current_user.id)
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return service.build_projection(location_id)
