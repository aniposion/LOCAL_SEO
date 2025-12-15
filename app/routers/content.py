"""Content generation router."""

from datetime import date
from typing import Any
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
from app.services.content import ContentService
from app.services.content_suggestions import ContentSuggestionService

router = APIRouter(prefix="/content", tags=["content"])


# ============ Schemas for Suggestions ============

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


# ============ Suggestion Endpoints (Multiple Choice UX) ============

@router.get("/suggestions", response_model=ContentSuggestionsResponse)
async def get_content_suggestions(
    location_id: UUID | None = None,
    weather: str | None = Query(None, description="Current weather: rainy, hot, cold, snowy"),
    limit: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """
    Get content topic suggestions for multiple-choice selection.
    
    사장님들은 프롬프트를 입력할 줄 모릅니다.
    UX는 무조건 객관식(Multiple Choice)이어야 합니다.
    
    Returns a list of suggested topics based on:
    - Current weather
    - Seasonal events (Halloween, Christmas, etc.)
    - Day of week
    - Business category
    """
    category = None
    
    # Get category from location if provided
    if location_id:
        location = db.query(Location).filter(
            Location.id == location_id,
            Location.account_id == current_user.id,
        ).first()
        if location:
            category = location.category
    
    suggestion_service = ContentSuggestionService()
    suggestions = suggestion_service.get_suggestions(
        category=category,
        weather=weather,
        target_date=date.today(),
        limit=limit,
    )
    
    return ContentSuggestionsResponse(
        suggestions=[ContentSuggestion(**s) for s in suggestions],
        message="이번 주 프로모션 주제를 골라주세요:",
    )


@router.post("/generate-from-suggestion")
async def generate_from_suggestion(
    suggestion_id: str,
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """
    Generate content from a selected suggestion.
    
    This is the "원클릭 생성" endpoint.
    User selects a suggestion, we generate the content automatically.
    """
    # Verify location ownership
    location = db.query(Location).filter(
        Location.id == location_id,
        Location.account_id == current_user.id,
    ).first()
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )
    
    # Get the suggestion
    suggestion_service = ContentSuggestionService()
    suggestion = suggestion_service.get_suggestion_by_id(suggestion_id)
    
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid suggestion ID",
        )
    
    # Build prompt from suggestion
    prompt_theme = suggestion.get("title_en", "weekly update")
    
    # Generate content
    content_service = ContentService()
    generated = await content_service.generate(
        location=location,
        theme=prompt_theme,
        services=location.services or [],
        tone="friendly and professional",
        language="en",
        platform_targets=["GBP"],  # Default to GBP
    )
    
    # Create draft post
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
        
        return {
            "success": True,
            "post_id": str(post.id),
            "suggestion": suggestion,
            "content": {
                "title": generated.gbp.title,
                "body": generated.gbp.body,
                "cta": generated.gbp.cta,
            },
            "message": "콘텐츠가 생성되었습니다! 승인 후 자동으로 업로드됩니다.",
        }
    
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to generate content",
    )


@router.post("/generate", response_model=ContentGenerateResponse)
async def generate_content(
    request: ContentGenerateRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> ContentGenerateResponse:
    """Generate content for all target platforms."""
    # Verify location ownership
    location = (
        db.query(Location)
        .filter(Location.id == request.location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    # Generate content using LLM
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

    # Create draft posts
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
                    body=getattr(content, "body", None) or getattr(content, "caption", None) or getattr(content, "markdown", None),
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

    return ContentGenerateResponse(
        location_id=location.id,
        theme=request.theme,
        content=generated,
        posts_created=posts_created,
    )
