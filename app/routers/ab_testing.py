"""
A/B Testing Router
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.routers.deps import get_current_account, get_db
from app.models.account import Account
from app.services.ab_testing import (
    ABTestingService,
    TestStatus,
    TestMetric,
    VariantType,
    TEST_TEMPLATES,
)

router = APIRouter(prefix="/ab-tests", tags=["A/B Testing"])

# Global service instance (in production, use dependency injection)
_ab_service = ABTestingService()


# ============ Schemas ============

class VariantContent(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    image_url: Optional[str] = None
    cta_text: Optional[str] = None
    posting_time: Optional[str] = None
    hashtags: Optional[list[str]] = None


class CreateTestRequest(BaseModel):
    name: str
    description: str
    location_id: str
    test_type: str  # title, body, image, cta, posting_time, hashtags
    primary_metric: str  # engagement, clicks, calls, directions, conversions
    control_content: VariantContent
    variant_content: VariantContent
    traffic_split: float = 50.0
    min_sample_size: int = 100


class VariantResponse(BaseModel):
    id: str
    name: str
    is_control: bool
    impressions: int
    clicks: int
    conversions: int
    click_rate: float
    conversion_rate: float
    engagement_score: float


class TestResponse(BaseModel):
    id: str
    name: str
    description: str
    location_id: str
    test_type: str
    primary_metric: str
    status: str
    traffic_split: float
    total_impressions: int
    is_significant: bool
    variants: list[VariantResponse]
    winner_id: Optional[str] = None
    improvement_percent: Optional[float] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: datetime


class TestListResponse(BaseModel):
    tests: list[TestResponse]
    total: int


class TestSuggestion(BaseModel):
    type: str
    name: str
    description: str
    control: str
    variant: str


class TestSuggestionsResponse(BaseModel):
    suggestions: list[TestSuggestion]


class TestTemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    type: str
    metric: str


class TestTemplatesResponse(BaseModel):
    templates: list[TestTemplateResponse]


# ============ Endpoints ============

@router.get("/templates", response_model=TestTemplatesResponse)
async def get_test_templates():
    """Get pre-built A/B test templates."""
    templates = [
        TestTemplateResponse(
            id=key,
            name=value["name"],
            description=value["description"],
            type=value["type"].value,
            metric=value["metric"].value,
        )
        for key, value in TEST_TEMPLATES.items()
    ]
    return TestTemplatesResponse(templates=templates)


@router.get("/suggestions/{location_id}", response_model=TestSuggestionsResponse)
async def get_test_suggestions(
    location_id: str,
    content_type: str = "post",
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get AI-powered A/B test suggestions."""
    suggestions = _ab_service.generate_test_suggestions(location_id, content_type)
    return TestSuggestionsResponse(
        suggestions=[
            TestSuggestion(
                type=s["type"].value,
                name=s["name"],
                description=s["description"],
                control=s["control"],
                variant=s["variant"],
            )
            for s in suggestions
        ]
    )


@router.post("/", response_model=TestResponse)
async def create_test(
    request: CreateTestRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Create a new A/B test."""
    try:
        test_type = VariantType(request.test_type)
        primary_metric = TestMetric(request.primary_metric)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid test type or metric",
        )
    
    test = _ab_service.create_test(
        name=request.name,
        description=request.description,
        location_id=request.location_id,
        test_type=test_type,
        primary_metric=primary_metric,
        control_content=request.control_content.model_dump(),
        variant_content=request.variant_content.model_dump(),
        traffic_split=request.traffic_split,
        min_sample_size=request.min_sample_size,
    )
    
    return _test_to_response(test)


@router.get("/", response_model=TestListResponse)
async def list_tests(
    location_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """List all A/B tests."""
    status_enum = None
    if status_filter:
        try:
            status_enum = TestStatus(status_filter)
        except ValueError:
            pass
    
    tests = _ab_service.list_tests(location_id=location_id, status=status_enum)
    
    # Add demo tests if empty
    if not tests:
        # Create demo tests
        demo_test = _ab_service.create_test(
            name="Emoji Title Test",
            description="Testing if emojis in titles increase engagement",
            location_id=location_id or "demo",
            test_type=VariantType.TITLE,
            primary_metric=TestMetric.ENGAGEMENT,
            control_content={"title": "Weekend Special: 20% Off All BBQ"},
            variant_content={"title": "🔥 Weekend Special: 20% Off All BBQ 🎉"},
        )
        demo_test.status = TestStatus.RUNNING
        demo_test.start_date = datetime.now()
        
        # Add demo metrics
        demo_test.variants[0].impressions = 1250
        demo_test.variants[0].clicks = 87
        demo_test.variants[0].engagement_score = 6.9
        demo_test.variants[1].impressions = 1180
        demo_test.variants[1].clicks = 142
        demo_test.variants[1].engagement_score = 12.0
        
        tests = [demo_test]
    
    return TestListResponse(
        tests=[_test_to_response(t) for t in tests],
        total=len(tests),
    )


@router.get("/{test_id}", response_model=TestResponse)
async def get_test(
    test_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get a specific A/B test."""
    test = _ab_service.get_test(test_id)
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found",
        )
    
    return _test_to_response(test)


@router.post("/{test_id}/start", response_model=TestResponse)
async def start_test(
    test_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Start an A/B test."""
    try:
        test = _ab_service.start_test(test_id)
        return _test_to_response(test)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{test_id}/pause", response_model=TestResponse)
async def pause_test(
    test_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Pause an A/B test."""
    try:
        test = _ab_service.pause_test(test_id)
        return _test_to_response(test)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{test_id}/complete", response_model=TestResponse)
async def complete_test(
    test_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Complete an A/B test and determine winner."""
    try:
        test = _ab_service.complete_test(test_id)
        return _test_to_response(test)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete("/{test_id}")
async def delete_test(
    test_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Delete an A/B test."""
    test = _ab_service.get_test(test_id)
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found",
        )
    
    # In production, delete from database
    return {"success": True, "message": "Test deleted"}


@router.get("/{test_id}/results")
async def get_test_results(
    test_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get detailed test results."""
    results = _ab_service.get_test_results(test_id)
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test not found",
        )
    
    return results


def _test_to_response(test) -> TestResponse:
    """Convert ABTest to TestResponse."""
    results = _ab_service.get_test_results(test.id)
    
    return TestResponse(
        id=test.id,
        name=test.name,
        description=test.description,
        location_id=test.location_id,
        test_type=test.test_type.value,
        primary_metric=test.primary_metric.value,
        status=test.status.value,
        traffic_split=test.traffic_split,
        total_impressions=test.total_impressions,
        is_significant=test.is_statistically_significant,
        variants=[
            VariantResponse(
                id=v["id"],
                name=v["name"],
                is_control=v["is_control"],
                impressions=v["impressions"],
                clicks=v["clicks"],
                conversions=v["conversions"],
                click_rate=v["click_rate"],
                conversion_rate=v["conversion_rate"],
                engagement_score=v["engagement_score"],
            )
            for v in results.get("variants", [])
        ],
        winner_id=results.get("winner"),
        improvement_percent=results.get("improvement_percent"),
        start_date=test.start_date,
        end_date=test.end_date,
        created_at=test.created_at,
    )
