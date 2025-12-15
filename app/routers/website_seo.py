"""Website SEO Auto-Optimizer router."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.routers.deps import get_current_user
from app.models.account import Account
from app.services.website_seo import WebsiteSEOService

router = APIRouter(prefix="/website-seo", tags=["website-seo"])


# ============ Schemas ============

class MetaTagsRequest(BaseModel):
    """Request to generate meta tags."""
    location_id: UUID
    page_type: str = Field(default="home", description="home, service, about, contact")
    service_name: str | None = None


class ServicePageRequest(BaseModel):
    """Request to generate a service page."""
    location_id: UUID
    service_name: str = Field(..., min_length=1)
    service_description: str | None = None


class BlogPostRequest(BaseModel):
    """Request to generate a blog post."""
    location_id: UUID
    topic: str = Field(..., min_length=5)
    keywords: list[str] | None = None


class OptimizePageRequest(BaseModel):
    """Request to analyze and optimize an existing page."""
    location_id: UUID
    page_url: str
    current_content: str = Field(..., min_length=50)


class PublishRequest(BaseModel):
    """Request to publish content to website."""
    location_id: UUID
    content_type: str = Field(..., description="blog or service_page")
    content: dict


# ============ Endpoints ============

@router.post("/meta-tags")
async def generate_meta_tags(
    request: MetaTagsRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Generate SEO-optimized meta tags for a page.
    
    Returns:
    - title (60 chars max)
    - description (160 chars max)
    - keywords
    - Open Graph tags
    - Schema.org JSON-LD
    """
    service = WebsiteSEOService(db)
    result = await service.generate_meta_tags(
        location_id=request.location_id,
        page_type=request.page_type,
        service_name=request.service_name,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )

    return result


@router.get("/keywords/{location_id}")
async def analyze_local_keywords(
    location_id: UUID,
    limit: int = 20,
    current_user: Annotated[Account, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    """
    Analyze and generate local SEO keywords for a business.
    
    Returns keywords optimized for:
    - Local search ("near me", city-based)
    - Service-specific searches
    - Business name variations
    """
    service = WebsiteSEOService(db)
    keywords = await service.analyze_local_keywords(
        location_id=location_id,
        limit=limit,
    )

    return {
        "location_id": str(location_id),
        "keywords": keywords,
        "count": len(keywords),
    }


@router.post("/service-page")
async def generate_service_page(
    request: ServicePageRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Generate an SEO-optimized service page.
    
    Returns:
    - Meta tags
    - HTML content
    - Target keywords
    """
    service = WebsiteSEOService(db)
    result = await service.generate_service_page(
        location_id=request.location_id,
        service_name=request.service_name,
        service_description=request.service_description,
    )

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["error"],
        )

    return result


@router.post("/blog-post")
async def generate_blog_post(
    request: BlogPostRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Generate an SEO-optimized blog post.
    
    Returns:
    - Title
    - Slug
    - Meta description
    - Markdown content
    - Target keywords
    - Word count
    """
    service = WebsiteSEOService(db)
    result = await service.generate_blog_post(
        location_id=request.location_id,
        topic=request.topic,
        keywords=request.keywords,
    )

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["error"],
        )

    return result


@router.post("/optimize")
async def optimize_existing_page(
    request: OptimizePageRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Analyze an existing page and suggest SEO optimizations.
    
    Returns:
    - Content analysis (word count, headings, etc.)
    - Recommendations with priority
    - Suggested meta tags
    - Target keywords
    """
    service = WebsiteSEOService(db)
    result = await service.optimize_existing_page(
        location_id=request.location_id,
        page_url=request.page_url,
        current_content=request.current_content,
    )

    return result


@router.post("/publish")
async def publish_to_website(
    request: PublishRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Publish generated content to the website.
    
    Supports:
    - GitHub Pages
    - GitLab Pages
    - WordPress
    """
    service = WebsiteSEOService(db)
    result = await service.publish_to_website(
        location_id=request.location_id,
        content_type=request.content_type,
        content=request.content,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to publish"),
        )

    return result


@router.get("/schema-types")
async def get_schema_types():
    """
    Get available Schema.org types for local businesses.
    """
    return {
        "types": [
            {"category": "restaurant", "schema_type": "Restaurant"},
            {"category": "spa", "schema_type": "HealthAndBeautyBusiness"},
            {"category": "dentist", "schema_type": "Dentist"},
            {"category": "gym", "schema_type": "HealthClub"},
            {"category": "salon", "schema_type": "BeautySalon"},
            {"category": "default", "schema_type": "LocalBusiness"},
        ],
    }
