"""Website SEO router."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account
from app.models.location import Location
from app.routers.deps import get_current_user
from app.services.feature_access import FeatureAccessService
from app.services.website_seo import (
    WebsiteSEOGenerationUnavailableError,
    WebsiteSEOService,
    WebsiteSEOUsageLimitError,
)

router = APIRouter(prefix="/website-seo", tags=["website-seo"])


class MetaTagsRequest(BaseModel):
    location_id: UUID
    page_type: str = Field(default="home", description="home, service, about, contact")
    service_name: str | None = None


class ServicePageRequest(BaseModel):
    location_id: UUID
    service_name: str = Field(..., min_length=1)
    service_description: str | None = None


class BlogPostRequest(BaseModel):
    location_id: UUID
    topic: str = Field(..., min_length=5)
    keywords: list[str] | None = None


class OptimizePageRequest(BaseModel):
    location_id: UUID
    page_url: str
    current_content: str = Field(..., min_length=50)


class PublishRequest(BaseModel):
    location_id: UUID
    content_type: str = Field(..., description="blog or service_page")
    content: dict
    draft_id: UUID | None = None


class RejectDraftRequest(BaseModel):
    reason: str | None = None


class ArchiveDraftsRequest(BaseModel):
    draft_ids: list[UUID] = Field(..., min_length=1)
    reason: str | None = None


def _get_owned_location(db: Session, current_user: Account, location_id: UUID) -> Location:
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return location


def _get_owned_draft(db: Session, current_user: Account, draft_id: UUID):
    """Fetch a Website SEO draft owned by the current user."""
    from app.models.website_seo import WebsiteSEODraft

    draft = (
        db.query(WebsiteSEODraft)
        .join(Location, Location.id == WebsiteSEODraft.location_id)
        .filter(WebsiteSEODraft.id == draft_id, Location.account_id == current_user.id)
        .first()
    )
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return draft


@router.post("/meta-tags")
async def generate_meta_tags(
    request: MetaTagsRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _get_owned_location(db, current_user, request.location_id)
    FeatureAccessService(db).check_feature_access(current_user, "website_seo_basic")
    service = WebsiteSEOService(db)
    result = await service.generate_meta_tags(
        location_id=request.location_id,
        page_type=request.page_type,
        service_name=request.service_name,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return result


@router.get("/keywords/{location_id}")
async def analyze_local_keywords(
    location_id: UUID,
    limit: int = 20,
    current_user: Annotated[Account, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _get_owned_location(db, current_user, location_id)
    service = WebsiteSEOService(db)
    keywords = await service.analyze_local_keywords(location_id=location_id, limit=limit)
    return {"location_id": str(location_id), "keywords": keywords, "count": len(keywords)}


@router.post("/service-page")
async def generate_service_page(
    request: ServicePageRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _get_owned_location(db, current_user, request.location_id)
    FeatureAccessService(db).check_feature_access(current_user, "website_seo_basic")
    service = WebsiteSEOService(db)
    try:
        result = await service.generate_service_page(
            location_id=request.location_id,
            service_name=request.service_name,
            service_description=request.service_description,
        )
    except WebsiteSEOUsageLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=exc.detail) from exc
    except WebsiteSEOGenerationUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["error"])
    return result


@router.post("/blog-post")
async def generate_blog_post(
    request: BlogPostRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _get_owned_location(db, current_user, request.location_id)
    FeatureAccessService(db).check_feature_access(current_user, "website_seo_basic")
    service = WebsiteSEOService(db)
    try:
        result = await service.generate_blog_post(
            location_id=request.location_id,
            topic=request.topic,
            keywords=request.keywords,
        )
    except WebsiteSEOUsageLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=exc.detail) from exc
    except WebsiteSEOGenerationUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["error"])
    return result


@router.post("/optimize")
async def optimize_existing_page(
    request: OptimizePageRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _get_owned_location(db, current_user, request.location_id)
    FeatureAccessService(db).check_feature_access(current_user, "website_seo_basic")
    service = WebsiteSEOService(db)
    return await service.optimize_existing_page(
        location_id=request.location_id,
        page_url=request.page_url,
        current_content=request.current_content,
    )


@router.post("/publish")
async def publish_to_website(
    request: PublishRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _get_owned_location(db, current_user, request.location_id)
    FeatureAccessService(db).check_feature_access(current_user, "website_seo_full")
    service = WebsiteSEOService(db)
    result = await service.publish_to_website(
        location_id=request.location_id,
        content_type=request.content_type,
        content=request.content,
        draft_id=request.draft_id,
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to publish"),
        )
    return result


@router.get("/history/{location_id}")
def get_history(
    location_id: UUID,
    limit: int = 20,
    offset: int = 0,
    content_type: str | None = None,
    status: str | None = None,
    approval_status: str | None = None,
    search: str | None = None,
    current_user: Annotated[Account, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
):
    _get_owned_location(db, current_user, location_id)
    service = WebsiteSEOService(db)
    drafts, total = service.list_history(
        location_id=location_id,
        content_type=content_type,
        status=status,
        approval_status=approval_status,
        search=search,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [
            {
                "id": str(draft.id),
                "content_type": draft.content_type.value,
                "status": "archived" if draft.archived_at else draft.status.value,
                "title": draft.title,
                "slug": draft.slug,
                "page_type": draft.page_type,
                "source_topic": draft.source_topic,
                "published_url": draft.published_url,
                "provider_reference": draft.provider_reference,
                "last_error": draft.last_error,
                "approval_status": draft.approval_status,
                "approval_requested_at": draft.approval_requested_at,
                "approved_at": draft.approved_at,
                "rejected_at": draft.rejected_at,
                "rejection_reason": draft.rejection_reason,
                "published_at": draft.published_at,
                "archived_at": draft.archived_at,
                "archived_reason": draft.archived_reason,
                "created_at": draft.created_at,
            }
            for draft in drafts
        ],
        "count": len(drafts),
        "total": total,
        "limit": min(max(limit, 1), 100),
        "offset": max(offset, 0),
    }


@router.post("/history/{location_id}/archive")
def archive_history(
    location_id: UUID,
    request: ArchiveDraftsRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    _get_owned_location(db, current_user, location_id)
    service = WebsiteSEOService(db)
    result = service.archive_drafts(
        location_id=location_id,
        draft_ids=request.draft_ids,
        reason=request.reason,
    )
    return {
        "location_id": str(location_id),
        "archived_count": result["archived_count"],
        "archived_ids": result["archived_ids"],
    }


@router.get("/drafts/{draft_id}")
def get_draft(
    draft_id: UUID,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    draft = _get_owned_draft(db, current_user, draft_id)

    return {
        "id": str(draft.id),
        "location_id": str(draft.location_id),
        "content_type": draft.content_type.value,
        "status": "archived" if draft.archived_at else draft.status.value,
        "title": draft.title,
        "slug": draft.slug,
        "page_type": draft.page_type,
        "source_topic": draft.source_topic,
        "payload": draft.payload,
        "published_url": draft.published_url,
        "provider_reference": draft.provider_reference,
        "last_error": draft.last_error,
        "approval_status": draft.approval_status,
        "approval_requested_at": draft.approval_requested_at,
        "approved_at": draft.approved_at,
        "rejected_at": draft.rejected_at,
        "rejection_reason": draft.rejection_reason,
        "published_at": draft.published_at,
        "archived_at": draft.archived_at,
        "archived_reason": draft.archived_reason,
        "created_at": draft.created_at,
    }


@router.post("/drafts/{draft_id}/request-approval")
def request_draft_approval(
    draft_id: UUID,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    owned_draft = _get_owned_draft(db, current_user, draft_id)
    service = WebsiteSEOService(db)
    updated = service.request_approval(draft_id=draft_id, location_id=owned_draft.location_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Draft is archived or unavailable")
    return {"draft_id": str(updated.id), "approval_status": updated.approval_status}


@router.post("/drafts/{draft_id}/approve")
def approve_draft(
    draft_id: UUID,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    owned_draft = _get_owned_draft(db, current_user, draft_id)
    service = WebsiteSEOService(db)
    updated = service.approve_draft(draft_id=draft_id, location_id=owned_draft.location_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Draft is archived or unavailable")
    return {"draft_id": str(updated.id), "approval_status": updated.approval_status}


@router.post("/drafts/{draft_id}/reject")
def reject_draft(
    draft_id: UUID,
    request: RejectDraftRequest,
    current_user: Annotated[Account, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    owned_draft = _get_owned_draft(db, current_user, draft_id)
    service = WebsiteSEOService(db)
    updated = service.reject_draft(
        draft_id=draft_id,
        location_id=owned_draft.location_id,
        reason=request.reason,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Draft is archived or unavailable")
    return {
        "draft_id": str(updated.id),
        "approval_status": updated.approval_status,
        "rejection_reason": updated.rejection_reason,
    }


@router.get("/schema-types")
async def get_schema_types():
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
