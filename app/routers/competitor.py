"""Competitor Stealth Watch API endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.rate_limiter import check_rate_limit, record_rate_limit_usage
from app.db.session import get_db
from app.models.account import Account
from app.models.location import Location
from app.routers.deps import get_current_account
from app.schemas.competitor import (
    CompetitorAnalysisResponse,
    CompetitorResponse,
    CompetitorSearchRequest,
    GenerateAnalysisRequest,
    WeeklyCompetitorReport,
)
from app.services.competitor_service import CompetitorService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/competitor", tags=["Competitor Analysis"])


def _require_owned_location(db: Session, location_id: UUID, account_id: UUID) -> Location:
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == account_id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return location


@router.post("/discover", response_model=list[CompetitorResponse])
async def discover_competitors(
    request: CompetitorSearchRequest,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> list[CompetitorResponse]:
    """
    Discover competitors near a location using Google Places API.

    This endpoint searches for nearby businesses of the same type within
    a specified radius and tracks them for competitive analysis.
    """
    try:
        _require_owned_location(db, request.location_id, current_account.id)
        # Check rate limit
        await check_rate_limit(
            request=None, db=db, account_id=current_account.id, feature="competitor_analysis"
        )

        service = CompetitorService(db)
        competitors = await service.discover_competitors(
            location_id=request.location_id,
            radius_miles=request.radius_miles,
            business_type=request.business_type,
            max_results=request.max_results,
        )
        record_rate_limit_usage(db, current_account.id, "competitor_analysis")

        return [CompetitorResponse.model_validate(c) for c in competitors]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error discovering competitors: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to discover competitors",
        )


@router.post("/analyze", response_model=CompetitorAnalysisResponse)
async def generate_competitor_analysis(
    request: GenerateAnalysisRequest,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> CompetitorAnalysisResponse:
    """
    Generate AI-powered competitor analysis.

    Analyzes competitor reviews, ratings, and trends to provide actionable
    insights and recommendations. Results are cached for 7 days to reduce
    API costs.
    """
    try:
        _require_owned_location(db, request.location_id, current_account.id)
        # Check rate limit
        await check_rate_limit(
            request=None, db=db, account_id=current_account.id, feature="competitor_analysis"
        )

        service = CompetitorService(db)
        analysis_result = await service.analyze_competitors_with_meta(
            location_id=request.location_id, force_refresh=request.force_refresh
        )
        if analysis_result.used_ai_generation:
            record_rate_limit_usage(db, current_account.id, "competitor_analysis")

        return CompetitorAnalysisResponse.model_validate(analysis_result.analysis)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate competitor analysis",
        )


@router.get("/report/{location_id}", response_model=WeeklyCompetitorReport)
async def get_weekly_report(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> WeeklyCompetitorReport:
    """
    Get weekly competitor analysis report.

    Returns a comprehensive report including competitor data, AI analysis,
    and recommended actions for the business owner.
    """
    try:
        _require_owned_location(db, location_id, current_account.id)
        service = CompetitorService(db)
        report = await service.get_weekly_report(location_id)
        return report
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting weekly report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get weekly report",
        )


@router.post("/sync-reviews/{competitor_id}")
async def sync_competitor_reviews(
    competitor_id: int,
    max_reviews: int = 50,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> dict:
    """
    Sync reviews for a specific competitor.

    Fetches the latest reviews from Google Places API and stores them
    for analysis.
    """
    try:
        from app.models.competitor import Competitor

        competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
        if not competitor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Competitor not found")
        _require_owned_location(db, competitor.location_id, current_account.id)

        service = CompetitorService(db)
        reviews = await service.sync_competitor_reviews(competitor_id, max_reviews)
        return {"success": True, "synced_count": len(reviews)}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing reviews: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync competitor reviews",
        )


@router.get("/list/{location_id}", response_model=list[CompetitorResponse])
async def list_competitors(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> list[CompetitorResponse]:
    """
    List all tracked competitors for a location.
    """
    from app.models.competitor import Competitor

    _require_owned_location(db, location_id, current_account.id)
    competitors = (
        db.query(Competitor).filter(Competitor.location_id == location_id).all()
    )

    return [CompetitorResponse.model_validate(c) for c in competitors]
