"""A/B Testing Router."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.location import Location
from app.routers.deps import get_current_account, get_db
from app.services.ab_testing import (
    ABTestingService,
    TEST_TEMPLATES,
    TestMetric,
    TestStatus,
    VariantType,
)

router = APIRouter(prefix="/ab-tests", tags=["A/B Testing"])

_ab_service = ABTestingService()


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
    test_type: str
    primary_metric: str
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


def _owned_location_ids(db: Session, account_id) -> set[str]:
    return {
        str(location_id)
        for (location_id,) in db.query(Location.id).filter(Location.account_id == account_id).all()
    }


def _require_owned_location(db: Session, location_id: str, account_id) -> None:
    if location_id not in _owned_location_ids(db, account_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")


def _require_owned_test(db: Session, test_id: str, account_id):
    test = _ab_service.get_test(test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    _require_owned_location(db, str(test.location_id), account_id)
    return test


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
    _require_owned_location(db, location_id, account.id)
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

    _require_owned_location(db, request.location_id, account.id)

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
    """List A/B tests owned by the current account."""
    status_enum = None
    if status_filter:
        try:
            status_enum = TestStatus(status_filter)
        except ValueError:
            status_enum = None

    owned_location_ids = _owned_location_ids(db, account.id)
    if location_id is not None:
        _require_owned_location(db, location_id, account.id)
        tests = _ab_service.list_tests(location_id=location_id, status=status_enum)
    else:
        tests = [
            test
            for test in _ab_service.list_tests(status=status_enum)
            if test.location_id in owned_location_ids
        ]

    return TestListResponse(
        tests=[_test_to_response(test) for test in tests],
        total=len(tests),
    )


@router.get("/{test_id}", response_model=TestResponse)
async def get_test(
    test_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get a specific A/B test."""
    test = _require_owned_test(db, test_id, account.id)
    return _test_to_response(test)


@router.post("/{test_id}/start", response_model=TestResponse)
async def start_test(
    test_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Start an A/B test."""
    try:
        _require_owned_test(db, test_id, account.id)
        test = _ab_service.start_test(test_id)
        return _test_to_response(test)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{test_id}/pause", response_model=TestResponse)
async def pause_test(
    test_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Pause an A/B test."""
    try:
        _require_owned_test(db, test_id, account.id)
        test = _ab_service.pause_test(test_id)
        return _test_to_response(test)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{test_id}/complete", response_model=TestResponse)
async def complete_test(
    test_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Complete an A/B test and determine winner."""
    try:
        _require_owned_test(db, test_id, account.id)
        test = _ab_service.complete_test(test_id)
        return _test_to_response(test)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{test_id}")
async def delete_test(
    test_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Delete an A/B test."""
    _require_owned_test(db, test_id, account.id)
    deleted = _ab_service.delete_test(test_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return {"success": True, "message": "Test deleted"}


@router.get("/{test_id}/results")
async def get_test_results(
    test_id: str,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Get detailed test results."""
    _require_owned_test(db, test_id, account.id)
    results = _ab_service.get_test_results(test_id)
    if not results:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
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
                id=variant["id"],
                name=variant["name"],
                is_control=variant["is_control"],
                impressions=variant["impressions"],
                clicks=variant["clicks"],
                conversions=variant["conversions"],
                click_rate=variant["click_rate"],
                conversion_rate=variant["conversion_rate"],
                engagement_score=variant["engagement_score"],
            )
            for variant in results.get("variants", [])
        ],
        winner_id=results.get("winner"),
        improvement_percent=results.get("improvement_percent"),
        start_date=test.start_date,
        end_date=test.end_date,
        created_at=test.created_at,
    )
