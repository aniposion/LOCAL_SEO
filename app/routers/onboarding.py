"""Onboarding router for new user audit flow."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.routers.deps import get_current_user
from app.models.account import Account
from app.models.onboarding import OnboardingStatus
from app.services.onboarding import OnboardingAuditService

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


# ============ Schemas ============

class OnboardingStartRequest(BaseModel):
    """Request to start onboarding process."""
    business_name: str = Field(..., min_length=1, max_length=255)
    address: str = Field(..., min_length=1, max_length=500)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=50)
    phone: str | None = Field(None, max_length=50)
    website_url: str | None = Field(None, max_length=500)


class OnboardingStartResponse(BaseModel):
    """Response after starting onboarding."""
    audit_id: str
    status: str
    message: str


class BusinessCandidate(BaseModel):
    """A candidate business from search."""
    place_id: str
    name: str
    address: str
    rating: float | None
    review_count: int


class OnboardingStatusResponse(BaseModel):
    """Status of onboarding process."""
    audit_id: str
    status: str
    message: str
    progress: int
    candidates: list[BusinessCandidate] | None = None
    needs_selection: bool = False
    result: dict[str, Any] | None = None


class SelectBusinessRequest(BaseModel):
    """Request to select a specific business."""
    place_id: str


class ScoreBreakdown(BaseModel):
    """Score breakdown."""
    total: float
    grade: str | None
    review: float
    activity: float
    completeness: float
    competition: float


class DiagnosisInfo(BaseModel):
    """Diagnosis information."""
    review_gap: int
    days_since_post: int | None
    missing_info: list[str]


class EstimatedLoss(BaseModel):
    """Estimated loss information."""
    monthly_dollars: float
    missed_calls: int


class Recommendation(BaseModel):
    """A single recommendation."""
    priority: int
    category: str
    status: str
    title: str
    description: str
    action: str


class CompetitorInfo(BaseModel):
    """Competitor information."""
    name: str
    rating: float | None
    review_count: int


class OnboardingResultResponse(BaseModel):
    """Full onboarding result."""
    business: dict[str, Any]
    scores: ScoreBreakdown
    diagnosis: DiagnosisInfo
    estimated_loss: EstimatedLoss
    summary: str
    recommendations: list[Recommendation]
    recommended_plan: str
    competitors: list[CompetitorInfo] | None = None


# ============ Background Tasks ============

async def run_business_search(
    audit_id: UUID,
    db: Session,
):
    """Background task to search for business."""
    service = OnboardingAuditService(db)
    await service.search_and_match_business(audit_id)


async def run_full_analysis(
    audit_id: UUID,
    place_id: str,
    db: Session,
):
    """Background task to run full analysis."""
    service = OnboardingAuditService(db)
    await service.select_business(audit_id, place_id)


# ============ Endpoints ============

@router.post("/start", response_model=OnboardingStartResponse)
async def start_onboarding(
    request: OnboardingStartRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """
    Start the onboarding process.
    
    This initiates the AI search and analysis of the business.
    The process runs in the background - poll /status for updates.
    """
    service = OnboardingAuditService(db)

    # Check if user already has an audit
    existing = await service.get_audit_result(current_user.id)
    if existing:
        return OnboardingStartResponse(
            audit_id=str(existing.id),
            status="completed",
            message="You already have a completed audit. View your results.",
        )

    # Create new audit
    audit = await service.start_onboarding(
        account_id=current_user.id,
        business_name=request.business_name,
        address=request.address,
        city=request.city,
        state=request.state,
        phone=request.phone,
        website_url=request.website_url,
    )

    # Start background search
    background_tasks.add_task(
        run_business_search,
        audit.id,
        db,
    )

    return OnboardingStartResponse(
        audit_id=str(audit.id),
        status="processing",
        message="Searching for your business on Google Maps...",
    )


@router.get("/status/{audit_id}", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    audit_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """
    Get the current status of the onboarding process.
    
    Poll this endpoint to track progress and get results.
    """
    service = OnboardingAuditService(db)

    try:
        status_data = await service.get_audit_status(audit_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return OnboardingStatusResponse(**status_data)


@router.post("/select-business/{audit_id}")
async def select_business(
    audit_id: UUID,
    request: SelectBusinessRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """
    Select a specific business from candidates.
    
    Use this when multiple business matches are found.
    """
    from app.models.onboarding import OnboardingAudit

    audit = db.query(OnboardingAudit).filter(
        OnboardingAudit.id == audit_id,
        OnboardingAudit.account_id == current_user.id,
    ).first()

    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found",
        )

    # Validate place_id is in candidates
    if audit.place_candidates:
        valid_ids = [c["place_id"] for c in audit.place_candidates]
        if request.place_id not in valid_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid place_id. Must be one of the candidates.",
            )

    # Update status and start analysis
    audit.status = OnboardingStatus.ANALYZING
    db.commit()

    background_tasks.add_task(
        run_full_analysis,
        audit_id,
        request.place_id,
        db,
    )

    return {
        "audit_id": str(audit_id),
        "status": "analyzing",
        "message": "Analyzing your business...",
    }


@router.get("/result", response_model=OnboardingResultResponse)
async def get_onboarding_result(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """
    Get the completed onboarding result for the current user.
    """
    service = OnboardingAuditService(db)
    audit = await service.get_audit_result(current_user.id)

    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No completed audit found. Start onboarding first.",
        )

    result = audit.to_result_dict()

    # Add competitors
    if audit.competitors_data:
        result["competitors"] = [
            CompetitorInfo(
                name=c["name"],
                rating=c.get("rating"),
                review_count=c.get("review_count", 0),
            )
            for c in audit.competitors_data
        ]

    return OnboardingResultResponse(**result)


@router.get("/progress-steps")
async def get_progress_steps():
    """
    Get the list of progress steps for the UI.
    
    Use this to display the checklist during analysis.
    """
    return {
        "steps": [
            {
                "id": "search",
                "label": "Google Maps에서 비즈니스 찾는 중",
                "label_en": "Finding your business on Google Maps",
            },
            {
                "id": "reviews",
                "label": "리뷰와 평점 분석 중",
                "label_en": "Analyzing reviews and ratings",
            },
            {
                "id": "competitors",
                "label": "경쟁 매장과 비교 중",
                "label_en": "Comparing with competitors",
            },
            {
                "id": "opportunities",
                "label": "놓치고 있는 기회 계산 중",
                "label_en": "Calculating missed opportunities",
            },
            {
                "id": "recommendations",
                "label": "맞춤 추천 생성 중",
                "label_en": "Generating personalized recommendations",
            },
        ]
    }


# ============ Solution Presentation (Conversion Funnel) ============

@router.get("/solution")
async def get_solution_presentation(
    language: str = "en",
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """
    Get personalized solution presentation after onboarding analysis.
    
    This is the critical conversion step:
    1. "당신의 문제는 이것입니다"
    2. "해결하는 가장 쉬운 방법은 이것입니다"  
    3. "우리가 다 자동으로 해드립니다"
    
    Returns the full solution presentation with:
    - Opening statement
    - Problem summary (from audit)
    - 3-step solution recipe
    - Value propositions
    - Projected improvement scenario
    - CTA with pricing
    """
    from app.services.conversion import ConversionFunnelService

    service = OnboardingAuditService(db)
    audit = await service.get_audit_result(current_user.id)

    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complete onboarding analysis first.",
        )

    conversion_service = ConversionFunnelService()
    presentation = conversion_service.generate_solution_presentation(
        audit=audit,
        language=language,
    )

    return presentation


@router.get("/solution/{audit_id}")
async def get_solution_by_audit_id(
    audit_id: UUID,
    language: str = "en",
    db: Session = Depends(get_db),
):
    """
    Get solution presentation for a specific audit (public endpoint for free audits).
    """
    from app.services.conversion import ConversionFunnelService
    from app.models.onboarding import OnboardingAudit

    audit = db.query(OnboardingAudit).filter(
        OnboardingAudit.id == audit_id,
        OnboardingAudit.status == OnboardingStatus.COMPLETED,
    ).first()

    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found or not completed.",
        )

    conversion_service = ConversionFunnelService()
    presentation = conversion_service.generate_solution_presentation(
        audit=audit,
        language=language,
    )

    return presentation


@router.post("/start-trial")
async def start_free_trial(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """
    Start a no-card free preview after viewing the solution presentation.
    
    This is the final CTA action:
    1. Create/activate a Free-plan preview
    2. Set up default preferences
    3. Redirect to dashboard
    """
    from app.models.subscription import FREE_PREVIEW_DAYS
    from app.services.billing import BillingService

    try:
        subscription = await BillingService(db).start_trial(account_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        "success": True,
        "message": f"Your {FREE_PREVIEW_DAYS}-day free preview has started.",
        "trial_ends_at": subscription.trial_end.isoformat() if subscription.trial_end else None,
        "redirect": "/dashboard",
        "next_steps": [
            "Review your audit and dashboard",
            "Connect only the channels you want to evaluate",
            "Choose a paid plan before using AI, SMS, publishing, or automation workflows",
        ],
    }


# ============ Public Endpoints (No Auth) ============

@router.post("/free-audit", response_model=OnboardingStartResponse)
async def request_free_audit(
    request: OnboardingStartRequest,
    email: EmailStr,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Request a free audit without signing up.
    
    Results will be sent to the provided email.
    This is for the landing page lead capture.
    """
    service = OnboardingAuditService(db)
    audit = await service.start_onboarding(
        account_id=None,
        contact_email=str(email),
        business_name=request.business_name,
        address=request.address,
        city=request.city,
        state=request.state,
        phone=request.phone,
        website_url=request.website_url,
    )

    # Start background search
    background_tasks.add_task(
        run_business_search,
        audit.id,
        db,
    )

    return OnboardingStartResponse(
        audit_id=str(audit.id),
        status="processing",
        message=f"Your free audit is being prepared. Results will be sent to {email}",
    )


@router.post("/free-audit/{audit_id}/select-business")
async def select_business_for_free_audit(
    audit_id: UUID,
    request: SelectBusinessRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Select a business candidate for a public free audit flow.

    This keeps the non-auth free-audit path usable when multiple Google Maps
    matches are found.
    """
    from app.models.onboarding import OnboardingAudit

    audit = db.query(OnboardingAudit).filter(
        OnboardingAudit.id == audit_id,
        OnboardingAudit.account_id.is_(None),
    ).first()

    if not audit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Free audit not found",
        )

    if audit.place_candidates:
        valid_ids = [candidate["place_id"] for candidate in audit.place_candidates]
        if request.place_id not in valid_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid place_id. Must be one of the candidates.",
            )

    audit.status = OnboardingStatus.ANALYZING
    db.commit()

    background_tasks.add_task(
        run_full_analysis,
        audit_id,
        request.place_id,
        db,
    )

    return {
        "audit_id": str(audit_id),
        "status": "analyzing",
        "message": "Analyzing your business...",
    }


@router.get("/free-audit/{audit_id}/status")
async def get_free_audit_status(
    audit_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get status of a free audit (no auth required).
    """
    service = OnboardingAuditService(db)

    try:
        status_data = await service.get_audit_status(audit_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return status_data
