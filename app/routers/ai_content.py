"""P6: AI Content Generation API."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.time import utc_now_aware
from app.db.session import get_db
from app.routers.deps import get_current_account
from app.models.account import Account
from app.models.location import Location
from app.services.credits import CreditsService
from app.services.ai_content_service import (
    AIContentUnavailableError,
    get_ai_content_service,
)
from app.services.feature_access import FeatureAccessService
from app.schemas.ai_content import (
    ContentGenerateRequest,
    ContentGenerateResponse,
    ReviewReplyRequest,
    ReviewReplyResponse,
    ContentAnalyzeRequest,
    ContentAnalyzeResponse,
    BulkGenerateRequest,
    BulkGenerateResponse,
)

router = APIRouter(prefix="/ai", tags=["AI Content"])
logger = logging.getLogger(__name__)


def _require_owned_location(db: Session, location_id: UUID, account_id: UUID) -> Location:
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == account_id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return location


def _preview_ai_usage(db: Session, account_id: UUID, usage_type: str, count: int = 1) -> None:
    result = CreditsService(db).preview_usage(str(account_id), usage_type, count)
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


def _record_ai_usage(db: Session, account_id: UUID, usage_type: str, count: int = 1) -> None:
    result = CreditsService(db).use_credits(str(account_id), usage_type, count)
    if result.get("allowed"):
        return

    logger.warning(
        "AI usage record failed after successful response for account %s (%s x%s): %s",
        account_id,
        usage_type,
        count,
        result.get("reason"),
    )


# ====================
# Content Generation
# ====================

@router.post("/generate", response_model=ContentGenerateResponse)
async def generate_content(
    request: ContentGenerateRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Generate AI content for social media posts.
    
    Uses Entity Vault data for context including:
    - Business name, services, location
    - Brand tone and voice
    - Keywords and forbidden phrases
    
    Supports multiple platforms: Google, Instagram, Facebook
    """
    # Verify location ownership
    _require_owned_location(db, request.location_id, current_user.id)
    FeatureAccessService(db).check_feature_access(current_user, "google_posts")
    _preview_ai_usage(db, current_user.id, "ai_content", count=request.num_variations)

    service = get_ai_content_service(db)
    try:
        response = await service.generate_content(request)
    except AIContentUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    _record_ai_usage(db, current_user.id, "ai_content", count=len(response.variations))
    return response


@router.post("/generate/quick")
async def quick_generate(
    location_id: UUID,
    topic: str = None,
    platform: str = "google",
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Quick content generation with minimal parameters."""
    _require_owned_location(db, location_id, current_user.id)
    FeatureAccessService(db).check_feature_access(current_user, "google_posts")
    _preview_ai_usage(db, current_user.id, "ai_content", count=1)

    request = ContentGenerateRequest(
        location_id=location_id,
        topic=topic,
        platforms=[platform],
        num_variations=1,
    )
    
    service = get_ai_content_service(db)
    try:
        response = await service.generate_content(request)
    except AIContentUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    _record_ai_usage(db, current_user.id, "ai_content", count=len(response.variations))

    if response.variations:
        return {
            "content": response.variations[0].content,
            "seo_score": response.variations[0].seo_score,
            "platform": platform,
        }

    raise HTTPException(status_code=503, detail="AI content provider is unavailable.")


# ====================
# Review Reply
# ====================

@router.post("/review-reply", response_model=ReviewReplyResponse)
async def generate_review_reply(
    request: ReviewReplyRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Generate AI reply for a customer review.
    
    Analyzes review sentiment and generates appropriate response.
    For negative reviews, can offer resolution options.
    """
    _require_owned_location(db, request.location_id, current_user.id)
    FeatureAccessService(db).check_feature_access(current_user, "ai_review_response")
    _preview_ai_usage(db, current_user.id, "ai_response", count=1)
    service = get_ai_content_service(db)
    try:
        response = await service.generate_review_reply(request)
    except AIContentUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    _record_ai_usage(db, current_user.id, "ai_response", count=1)
    return response


@router.post("/review-reply/quick")
async def quick_review_reply(
    location_id: UUID,
    reviewer_name: str,
    star_rating: int,
    review_text: str,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Quick review reply generation."""
    _require_owned_location(db, location_id, current_user.id)
    FeatureAccessService(db).check_feature_access(current_user, "ai_review_response")
    _preview_ai_usage(db, current_user.id, "ai_response", count=1)

    request = ReviewReplyRequest(
        location_id=location_id,
        reviewer_name=reviewer_name,
        star_rating=star_rating,
        review_text=review_text,
    )
    
    service = get_ai_content_service(db)
    try:
        response = await service.generate_review_reply(request)
    except AIContentUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    _record_ai_usage(db, current_user.id, "ai_response", count=1)

    return {
        "reply": response.reply,
        "sentiment": response.sentiment_detected,
    }


# ====================
# Content Analysis
# ====================

@router.post("/analyze", response_model=ContentAnalyzeResponse)
async def analyze_content(
    request: ContentAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Analyze content for SEO, compliance, tone, and readability.
    
    Returns:
    - SEO score with keyword analysis
    - Compliance issues (forbidden phrases, exaggerations)
    - Tone match against brand voice
    - Readability score and grade level
    - Suggested revision if issues found
    """
    if request.location_id is not None:
        _require_owned_location(db, request.location_id, current_user.id)
    service = get_ai_content_service(db)
    try:
        response = await service.analyze_content(
            request,
            before_revision=lambda: _preview_ai_usage(db, current_user.id, "ai_content", count=1),
        )
    except AIContentUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    if response.suggested_revision is not None:
        _record_ai_usage(db, current_user.id, "ai_content", count=1)
    return response


@router.post("/analyze/quick")
async def quick_analyze(
    content: str,
    location_id: UUID = None,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Quick content analysis."""
    if location_id is not None:
        _require_owned_location(db, location_id, current_user.id)

    request = ContentAnalyzeRequest(
        content=content,
        location_id=location_id,
    )
    
    service = get_ai_content_service(db)
    try:
        response = await service.analyze_content(
            request,
            before_revision=lambda: _preview_ai_usage(db, current_user.id, "ai_content", count=1),
        )
    except AIContentUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    if response.suggested_revision is not None:
        _record_ai_usage(db, current_user.id, "ai_content", count=1)

    return {
        "score": response.overall_score,
        "is_safe": response.is_safe_to_publish,
        "issues_count": len(response.compliance),
        "seo_score": response.seo.score if response.seo else None,
    }


# ====================
# Bulk Generation
# ====================

@router.post("/bulk-generate", response_model=BulkGenerateResponse)
async def bulk_generate_content(
    request: BulkGenerateRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Generate content calendar for a date range.
    
    Creates multiple posts across platforms with varied content types.
    Can auto-schedule posts at preferred times.
    """
    from datetime import datetime, timedelta
    from app.schemas.ai_content import ScheduledPost
    
    _require_owned_location(db, request.location_id, current_user.id)
    FeatureAccessService(db).check_feature_access(current_user, "google_posts")

    # Parse dates
    start = datetime.strptime(request.start_date, "%Y-%m-%d")
    end = datetime.strptime(request.end_date, "%Y-%m-%d")
    
    # Calculate number of posts
    days = (end - start).days
    weeks = max(1, days // 7)
    total_posts = weeks * request.posts_per_week

    _preview_ai_usage(db, current_user.id, "ai_content", count=total_posts)

    service = get_ai_content_service(db)
    
    posts = []
    current_date = start
    content_type_index = 0
    platform_index = 0
    time_index = 0
    
    for i in range(total_posts):
        # Rotate through content types and platforms
        content_type = request.content_types[content_type_index % len(request.content_types)]
        platform = request.platforms[platform_index % len(request.platforms)]
        preferred_time = request.preferred_times[time_index % len(request.preferred_times)]
        
        # Generate content
        gen_request = ContentGenerateRequest(
            location_id=request.location_id,
            content_type="post",
            topic=content_type,
            platforms=[platform],
            num_variations=1,
        )
        
        try:
            gen_response = await service.generate_content(gen_request)
        except AIContentUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            )

        if gen_response.variations:
            variation = gen_response.variations[0]
            
            # Calculate scheduled time
            hour, minute = map(int, preferred_time.split(":"))
            scheduled_time = current_date.replace(hour=hour, minute=minute)
            
            posts.append(ScheduledPost(
                content=variation.content,
                platform=platform,
                scheduled_for=scheduled_time,
                content_type=content_type,
                seo_score=variation.seo_score,
                status="draft" if not request.auto_schedule else "scheduled",
            ))
        
        # Advance counters
        content_type_index += 1
        platform_index += 1
        time_index += 1
        
        # Advance date every posts_per_week posts
        if (i + 1) % request.posts_per_week == 0:
            current_date += timedelta(days=7)
    
    # Build summary
    by_platform = {}
    by_content_type = {}
    
    for post in posts:
        by_platform[post.platform] = by_platform.get(post.platform, 0) + 1
        by_content_type[post.content_type] = by_content_type.get(post.content_type, 0) + 1

    if posts:
        _record_ai_usage(db, current_user.id, "ai_content", count=len(posts))
    
    return BulkGenerateResponse(
        location_id=request.location_id,
        posts=posts,
        total_generated=len(posts),
        by_platform=by_platform,
        by_content_type=by_content_type,
        created_at=utc_now_aware(),
    )


# ====================
# Templates & Suggestions
# ====================

@router.get("/templates/{location_id}")
async def get_content_templates(
    location_id: UUID,
    content_type: str = "post",
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Get content templates for a location."""
    # Return predefined templates based on content type
    templates = {
        "post": [
            {"name": "Service Highlight", "prompt": "Highlight a specific service"},
            {"name": "Customer Appreciation", "prompt": "Thank customers"},
            {"name": "Behind the Scenes", "prompt": "Show your team or process"},
            {"name": "Tips & Advice", "prompt": "Share helpful tips"},
            {"name": "Seasonal/Holiday", "prompt": "Seasonal promotion or greeting"},
        ],
        "reply": [
            {"name": "Positive Review", "tone": "grateful"},
            {"name": "Negative Review", "tone": "apologetic"},
            {"name": "Neutral Review", "tone": "professional"},
        ],
    }
    
    return {
        "templates": templates.get(content_type, []),
        "content_type": content_type,
    }


@router.get("/suggestions/{location_id}")
async def get_topic_suggestions(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_account),
):
    """Get AI-suggested topics for content creation."""
    from app.models.vault import EntityVault
    from sqlalchemy import select
    
    # Get vault for context
    result = db.execute(
        select(EntityVault).where(EntityVault.location_id == location_id)
    )
    vault = result.scalar_one_or_none()
    
    suggestions = []
    
    if vault:
        # Service-based suggestions
        if vault.services:
            for service in vault.services[:3]:
                suggestions.append({
                    "topic": f"Highlight: {service.get('name', 'Service')}",
                    "type": "service",
                })
        
        # Keyword-based suggestions
        if vault.primary_keywords:
            for keyword in vault.primary_keywords[:3]:
                suggestions.append({
                    "topic": f"Tips about {keyword}",
                    "type": "educational",
                })
        
        # FAQ-based suggestions
        if vault.faq:
            for faq in vault.faq[:2]:
                suggestions.append({
                    "topic": f"FAQ: {faq.get('question', '')}",
                    "type": "faq",
                })
    
    # Add evergreen suggestions
    suggestions.extend([
        {"topic": "Customer testimonial spotlight", "type": "social_proof"},
        {"topic": "Team member introduction", "type": "behind_scenes"},
        {"topic": "Special offer or promotion", "type": "promotional"},
    ])
    
    return {
        "suggestions": suggestions[:10],
        "location_id": str(location_id),
    }
