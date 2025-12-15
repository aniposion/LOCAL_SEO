"""SEO score and recommendation router."""

from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account
from app.models.location import Location
from app.models.seo_score import SEOScore
from app.routers.deps import get_current_user
from app.schemas.seo import SEORecalcRequest, SEORecommendation, SEOScoreResponse
from app.services.seo import SEOService

router = APIRouter(prefix="/seo", tags=["seo"])


@router.get("/score", response_model=list[SEOScoreResponse])
def get_seo_scores(
    location_id: UUID,
    from_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    to_date: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> list[SEOScore]:
    """Get SEO scores for a location."""
    # Verify location ownership
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    return (
        db.query(SEOScore)
        .filter(
            SEOScore.location_id == location_id,
            SEOScore.date >= from_date,
            SEOScore.date <= to_date,
        )
        .order_by(SEOScore.date.desc())
        .all()
    )


@router.post("/score/recalc", response_model=SEOScoreResponse)
async def recalculate_seo_score(
    request: SEORecalcRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> SEOScore:
    """Recalculate SEO score for a location."""
    # Verify location ownership
    location = (
        db.query(Location)
        .filter(Location.id == request.location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    seo_service = SEOService(db)
    score = await seo_service.calculate_score(
        location_id=request.location_id,
        from_date=request.from_date,
        to_date=request.to_date,
    )

    return score


@router.get("/recommendation", response_model=SEORecommendation)
async def get_seo_recommendation(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> SEORecommendation:
    """Get SEO recommendations for next content."""
    # Verify location ownership
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    seo_service = SEOService(db)
    recommendation = await seo_service.get_recommendation(location_id=location_id)

    return recommendation
