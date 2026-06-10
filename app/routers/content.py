"""Content generation router."""

import logging
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account
from app.models.location import Location
from app.models.post import Platform, Post, PostStatus
from app.routers.deps import get_current_user
from app.schemas.content import ContentGenerateRequest, ContentGenerateResponse
from app.services.credits import CreditsService
from app.services.content import ContentService
from app.services.content_suggestions import ContentSuggestionService

router = APIRouter(prefix="/content", tags=["content"])
logger = logging.getLogger(__name__)


class ContentSuggestion(BaseModel):
    """A content topic suggestion."""

    id: str
    type: str
    emoji: str
    title_ko: str
    title_en: str
    priority: int


class ContentSuggestionsResponse(BaseModel):
    """Response with content suggestions."""

    suggestions: list[ContentSuggestion]
    message: str


def _require_owned_location(db: Session, location_id: UUID, account_id: UUID) -> Location:
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == account_id)
        .first()
    )
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )
    return location


def _preview_content_usage(db: Session, account_id: UUID) -> None:
    result = CreditsService(db).preview_usage(str(account_id), "ai_content", 1)
    if result.get("allowed"):
        return

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "error": "Rate limit exceeded",
            "message": result.get("reason"),
            "remaining_daily": result.get("remaining_daily", 0),
            "remaining_monthly": result.get("remaining_monthly", 0),
            "cooldown_seconds": result.get("cooldown_remaining_seconds", 0),
            "overage_available": result.get("overage_available", False),
            "overage_cost_cents": result.get("overage_cost_cents", 0),
        },
    )


def _record_content_usage(db: Session, account_id: UUID) -> None:
    result = CreditsService(db).use_credits(str(account_id), "ai_content", 1)
    if result.get("allowed"):
        return

    logger.warning(
        "Content usage record failed after successful response for account %s: %s",
        account_id,
        result.get("reason"),
    )


@router.get("/suggestions", response_model=ContentSuggestionsResponse)
async def get_content_suggestions(
    location_id: UUID | None = None,
    weather: str | None = Query(None, description="Current weather: rainy, hot, cold, snowy"),
    limit: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Get multiple-choice content suggestions for the current user."""
    category = None

    if location_id:
        location = db.query(Location).filter(
            Location.id == location_id,
            Location.account_id == current_user.id,
        ).first()
        if location:
            category = getattr(location, "category", None)

    suggestion_service = ContentSuggestionService()
    suggestions = suggestion_service.get_suggestions(
        category=category,
        weather=weather,
        target_date=date.today(),
        limit=limit,
    )

    return ContentSuggestionsResponse(
        suggestions=[ContentSuggestion(**suggestion) for suggestion in suggestions],
        message="Select a suggested topic to generate content faster.",
    )


@router.post("/generate-from-suggestion")
async def generate_from_suggestion(
    suggestion_id: str,
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Generate a draft post from a selected suggestion."""
    location = _require_owned_location(db, location_id, current_user.id)

    suggestion_service = ContentSuggestionService()
    suggestion = suggestion_service.get_suggestion_by_id(suggestion_id)

    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid suggestion ID",
        )

    prompt_theme = suggestion.get("title_en", "weekly update")
    _preview_content_usage(db, current_user.id)

    content_service = ContentService()
    generated = await content_service.generate(
        location=location,
        theme=prompt_theme,
        services=location.services or [],
        tone="friendly and professional",
        language="en",
        platform_targets=["GBP"],
    )

    if generated.gbp:
        post = Post(
            location_id=location.id,
            platform=Platform.GBP,
            status=PostStatus.DRAFT,
            title=generated.gbp.title,
            body=generated.gbp.body,
            image_prompt=generated.image_prompt,
            generated_by=content_service.model_name,
            generation_params={
                "suggestion_id": suggestion_id,
                "suggestion_title": prompt_theme,
            },
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        _record_content_usage(db, current_user.id)

        return {
            "success": True,
            "post_id": str(post.id),
            "suggestion": suggestion,
            "content": {
                "title": generated.gbp.title,
                "body": generated.gbp.body,
                "cta": generated.gbp.cta,
            },
            "message": "Draft created from the selected suggestion.",
        }

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="AI content provider is unavailable.",
    )


@router.post("/generate", response_model=ContentGenerateResponse)
async def generate_content(
    request: ContentGenerateRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> ContentGenerateResponse:
    """Generate content for the requested platforms."""
    location = _require_owned_location(db, request.location_id, current_user.id)
    _preview_content_usage(db, current_user.id)

    content_service = ContentService()
    generated = await content_service.generate(
        location=location,
        theme=request.theme,
        services=request.services or location.services or [],
        tone=request.tone,
        language=request.language,
        platform_targets=request.platform_targets,
        audience=request.audience,
        promo=request.promo,
    )

    posts_created = 0
    platform_map = {
        "GBP": (Platform.GBP, generated.gbp),
        "INSTAGRAM": (Platform.INSTAGRAM, generated.instagram),
        "WEBSITE": (Platform.WEBSITE, generated.web),
    }

    for target in request.platform_targets:
        if target in platform_map:
            platform, content = platform_map[target]
            if content:
                post = Post(
                    location_id=location.id,
                    platform=platform,
                    status=PostStatus.DRAFT,
                    title=getattr(content, "title", None),
                    body=getattr(content, "body", None)
                    or getattr(content, "caption", None)
                    or getattr(content, "markdown", None),
                    hashtags=getattr(content, "hashtags", None),
                    image_prompt=generated.image_prompt,
                    generated_by=content_service.model_name,
                    generation_params={
                        "theme": request.theme,
                        "tone": request.tone,
                        "language": request.language,
                    },
                )
                db.add(post)
                posts_created += 1

    db.commit()
    if posts_created == 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI content provider is unavailable.",
        )

    _record_content_usage(db, current_user.id)

    return ContentGenerateResponse(
        location_id=location.id,
        theme=request.theme,
        content=generated,
        posts_created=posts_created,
    )
