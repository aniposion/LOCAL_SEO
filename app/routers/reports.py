"""Reports router."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account
from app.models.location import Location
from app.models.report import Report
from app.routers.deps import get_current_user
from app.schemas.report import ReportGenerateRequest, ReportResponse
from app.services.reporting import ReportingService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=list[ReportResponse])
def list_reports(
    location_id: UUID,
    limit: int = Query(10, le=50),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> list[Report]:
    """List reports for a location."""
    # Verify location ownership
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    return (
        db.query(Report)
        .filter(Report.location_id == location_id)
        .order_by(Report.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> Report:
    """Get a specific report."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    # Verify ownership
    location = db.query(Location).filter(Location.id == report.location_id).first()
    if not location or location.account_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    return report


@router.post("/weekly", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def generate_weekly_report(
    request: ReportGenerateRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> Report:
    """Generate a weekly report for a location."""
    # Verify location ownership
    location = (
        db.query(Location)
        .filter(Location.id == request.location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    reporting_service = ReportingService(db)
    report = await reporting_service.generate_weekly_report(
        location_id=request.location_id,
        send_email=request.send_email,
    )

    return report
