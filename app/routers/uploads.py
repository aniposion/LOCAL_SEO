"""
File Upload Router
Handle image and media uploads
"""
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.location import Location
from app.models.post import Platform, Post, PostStatus
from app.models.upload import UploadAsset
from app.routers.deps import get_current_account, get_db
from app.models.account import Account
from app.services.file_upload import file_upload_service, FileType, UploadedFile

router = APIRouter(prefix="/uploads", tags=["Uploads"])
UPLOAD_ROOT = Path("uploads")


# ============ Schemas ============

class UploadResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    file_type: str
    mime_type: str
    size_bytes: int
    url: str
    thumbnail_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: Optional[datetime] = None


class UploadedFilesList(BaseModel):
    files: list[UploadResponse]
    total: int


class CreatePostRequest(BaseModel):
    title: str
    body: str
    location_id: str
    image_ids: Optional[list[str]] = None
    scheduled_at: Optional[datetime] = None
    platforms: list[str] = ["google"]  # google, instagram, facebook


class CreatePostResponse(BaseModel):
    id: str
    created_post_ids: list[str]
    title: str
    body: str
    status: str
    image_urls: list[str]
    attached_image_url: Optional[str] = None
    image_attachment_mode: str = "none"
    platforms: list[str]
    scheduled_at: Optional[datetime] = None
    created_at: datetime
    legacy_endpoint: str
    canonical_dashboard_path: str
    canonical_primary_post_path: str
    canonical_post_paths: list[str]
    legacy_notice: str


LEGACY_UPLOAD_DASHBOARD_PATH = "/dashboard/content"


def _persist_uploaded_asset(
    db: Session,
    uploaded: UploadedFile,
    account: Account,
) -> None:
    """Persist upload metadata so assets remain account-scoped and auditable."""
    asset = UploadAsset(
        id=uuid.UUID(uploaded.id),
        account_id=account.id,
        filename=uploaded.filename,
        original_filename=uploaded.original_filename,
        file_type=uploaded.file_type.value,
        mime_type=uploaded.mime_type,
        size_bytes=uploaded.size_bytes,
        url=uploaded.url,
        storage_key=uploaded.storage_key,
        width=uploaded.width,
        height=uploaded.height,
        duration_seconds=uploaded.duration_seconds,
    )
    db.add(asset)
    try:
        db.commit()
    except Exception:
        db.rollback()
        file_upload_service.delete_file(
            uploaded.id,
            uploaded.file_type,
            filename=uploaded.filename,
            storage_key=uploaded.storage_key,
        )
        raise


def _serialize_upload_asset(asset: UploadAsset) -> UploadResponse:
    return UploadResponse(
        id=str(asset.id),
        filename=asset.filename,
        original_filename=asset.original_filename,
        file_type=asset.file_type,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        url=asset.url,
        thumbnail_url=asset.url if asset.file_type == FileType.IMAGE.value else None,
        width=asset.width,
        height=asset.height,
        created_at=asset.created_at,
    )


def _require_owned_location(db: Session, location_id: str, account: Account) -> Location:
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == account.id)
        .first()
    )
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )
    return location


def _parse_platforms(platforms: str) -> list[Platform]:
    tokens = [token.strip().lower() for token in platforms.split(",") if token.strip()]
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one platform is required.",
        )

    mapping = {
        "google": Platform.GBP,
        "gbp": Platform.GBP,
        "instagram": Platform.INSTAGRAM,
        "website": Platform.WEBSITE,
    }
    resolved: list[Platform] = []
    for token in tokens:
        platform = mapping.get(token)
        if platform is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported platform. Use google, instagram, or website.",
            )
        if platform not in resolved:
            resolved.append(platform)
    return resolved


def _parse_scheduled_at(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    candidate = value.strip()
    if not candidate:
        return None

    try:
        return datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scheduled_at must be a valid ISO datetime string.",
        ) from exc


async def _upload_legacy_images(
    *,
    files: list[UploadFile],
    db: Session,
    account: Account,
) -> list[UploadResponse]:
    uploaded_images: list[UploadResponse] = []
    for file in files:
        uploaded = await file_upload_service.upload_image(
            file=file,
            account_id=str(account.id),
        )
        _persist_uploaded_asset(db, uploaded, account)
        uploaded_images.append(
            UploadResponse(
                id=uploaded.id,
                filename=uploaded.filename,
                original_filename=uploaded.original_filename,
                file_type=uploaded.file_type.value,
                mime_type=uploaded.mime_type,
                size_bytes=uploaded.size_bytes,
                url=uploaded.url,
                thumbnail_url=uploaded.thumbnail_url,
                width=uploaded.width,
                height=uploaded.height,
                created_at=uploaded.created_at,
            )
        )
    return uploaded_images


def _build_legacy_post_response(
    *,
    posts: list[Post],
    title: str,
    body: str,
    uploaded_image_urls: list[str],
    attached_image_url: Optional[str],
    scheduled_at: Optional[datetime],
    legacy_endpoint: str,
) -> CreatePostResponse:
    first_post = posts[0]
    canonical_post_paths = [
        f"{LEGACY_UPLOAD_DASHBOARD_PATH}/{post.id}"
        for post in posts
    ]
    attachment_mode = "none"
    if attached_image_url and len(uploaded_image_urls) > 1:
        attachment_mode = "first_image_attached"
    elif attached_image_url:
        attachment_mode = "single_image_attached"

    return CreatePostResponse(
        id=str(first_post.id),
        created_post_ids=[str(post.id) for post in posts],
        title=title,
        body=body,
        status=first_post.status.value,
        image_urls=uploaded_image_urls,
        attached_image_url=attached_image_url,
        image_attachment_mode=attachment_mode,
        platforms=[post.platform.value for post in posts],
        scheduled_at=scheduled_at,
        created_at=first_post.created_at,
        legacy_endpoint=legacy_endpoint,
        canonical_dashboard_path=LEGACY_UPLOAD_DASHBOARD_PATH,
        canonical_primary_post_path=canonical_post_paths[0],
        canonical_post_paths=canonical_post_paths,
        legacy_notice=(
            "Legacy upload endpoint created real draft posts. "
            "Continue editing in the Content workspace."
        ),
    )


def _create_legacy_draft_posts(
    *,
    db: Session,
    location: Location,
    title: str,
    body: str,
    platforms: list[Platform],
    scheduled_at: Optional[datetime],
    uploaded_image_urls: list[str],
    legacy_endpoint: str,
) -> CreatePostResponse:
    attached_image_url = uploaded_image_urls[0] if uploaded_image_urls else None
    posts: list[Post] = []
    for platform in platforms:
        post = Post(
            location_id=location.id,
            platform=platform,
            status=PostStatus.DRAFT,
            title=title,
            body=body,
            image_url=attached_image_url,
            scheduled_at=scheduled_at,
            generated_by="legacy_upload_endpoint",
            generation_params=(
                {
                    "legacy_uploaded_image_urls": uploaded_image_urls,
                    "image_attachment_mode": (
                        "first_image_attached" if len(uploaded_image_urls) > 1 else "single_image_attached"
                    ),
                }
                if uploaded_image_urls
                else None
            ),
        )
        db.add(post)
        posts.append(post)

    db.commit()
    for post in posts:
        db.refresh(post)

    return _build_legacy_post_response(
        posts=posts,
        title=title,
        body=body,
        uploaded_image_urls=uploaded_image_urls,
        attached_image_url=attached_image_url,
        scheduled_at=scheduled_at,
        legacy_endpoint=legacy_endpoint,
    )


def _annotate_legacy_upload_response(
    response: Response,
    *,
    legacy_endpoint: str,
    canonical_primary_post_path: str,
) -> None:
    response.headers["Deprecation"] = "true"
    response.headers["X-Legacy-Endpoint"] = legacy_endpoint
    response.headers["X-Canonical-Dashboard-Path"] = LEGACY_UPLOAD_DASHBOARD_PATH
    response.headers["X-Canonical-Primary-Post-Path"] = canonical_primary_post_path
    response.headers["Link"] = f'<{canonical_primary_post_path}>; rel="alternate"'


# ============ Endpoints ============

@router.get("", response_model=UploadedFilesList)
async def list_uploaded_files(
    file_type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """List persisted uploaded assets for the current account."""
    query = db.query(UploadAsset).filter(UploadAsset.account_id == account.id)

    if file_type:
        normalized = file_type.strip().lower()
        allowed = {FileType.IMAGE.value, FileType.VIDEO.value, FileType.DOCUMENT.value}
        if normalized not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file_type. Allowed values: image, video, document",
            )
        query = query.filter(UploadAsset.file_type == normalized)

    total = query.count()
    assets = (
        query.order_by(UploadAsset.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return UploadedFilesList(
        files=[_serialize_upload_asset(asset) for asset in assets],
        total=total,
    )

@router.post("/image", response_model=UploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Upload an image file."""
    # Check usage limits (count as 0 since upload itself is free, generation costs credits)
    
    uploaded = await file_upload_service.upload_image(
        file=file,
        account_id=str(account.id),
    )
    _persist_uploaded_asset(db, uploaded, account)
    
    return UploadResponse(
        id=uploaded.id,
        filename=uploaded.filename,
        original_filename=uploaded.original_filename,
        file_type=uploaded.file_type.value,
        mime_type=uploaded.mime_type,
        size_bytes=uploaded.size_bytes,
        url=uploaded.url,
        thumbnail_url=uploaded.thumbnail_url,
        width=uploaded.width,
        height=uploaded.height,
        created_at=uploaded.created_at,
    )


@router.get("/images/{filename}")
async def get_uploaded_image(filename: str):
    """Serve uploaded image files from the local uploads directory."""
    safe_name = Path(filename).name
    file_path = UPLOAD_ROOT / "images" / safe_name

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    return FileResponse(file_path)


@router.post("/images", response_model=UploadedFilesList)
async def upload_multiple_images(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Upload multiple image files."""
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 images per upload",
        )
    
    uploaded_files = []
    for file in files:
        uploaded = await file_upload_service.upload_image(
            file=file,
            account_id=str(account.id),
        )
        _persist_uploaded_asset(db, uploaded, account)
        uploaded_files.append(UploadResponse(
            id=uploaded.id,
            filename=uploaded.filename,
            original_filename=uploaded.original_filename,
            file_type=uploaded.file_type.value,
            mime_type=uploaded.mime_type,
            size_bytes=uploaded.size_bytes,
            url=uploaded.url,
            thumbnail_url=uploaded.thumbnail_url,
            width=uploaded.width,
            height=uploaded.height,
            created_at=uploaded.created_at,
        ))
    
    return UploadedFilesList(
        files=uploaded_files,
        total=len(uploaded_files),
    )


@router.post("/video", response_model=UploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Upload a video file."""
    uploaded = await file_upload_service.upload_video(
        file=file,
        account_id=str(account.id),
    )
    _persist_uploaded_asset(db, uploaded, account)
    
    return UploadResponse(
        id=uploaded.id,
        filename=uploaded.filename,
        original_filename=uploaded.original_filename,
        file_type=uploaded.file_type.value,
        mime_type=uploaded.mime_type,
        size_bytes=uploaded.size_bytes,
        url=uploaded.url,
        created_at=uploaded.created_at,
    )


@router.post("/document", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Upload a document file."""
    uploaded = await file_upload_service.upload_document(
        file=file,
        account_id=str(account.id),
    )
    _persist_uploaded_asset(db, uploaded, account)

    return UploadResponse(
        id=uploaded.id,
        filename=uploaded.filename,
        original_filename=uploaded.original_filename,
        file_type=uploaded.file_type.value,
        mime_type=uploaded.mime_type,
        size_bytes=uploaded.size_bytes,
        url=uploaded.url,
        created_at=uploaded.created_at,
    )


@router.get("/videos/{filename}")
async def get_uploaded_video(filename: str):
    """Serve uploaded video files from the local uploads directory."""
    safe_name = Path(filename).name
    file_path = UPLOAD_ROOT / "videos" / safe_name

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )

    return FileResponse(file_path)


@router.get("/documents/{filename}")
async def get_uploaded_document(filename: str):
    """Serve uploaded document files from the local uploads directory."""
    safe_name = Path(filename).name
    file_path = UPLOAD_ROOT / "documents" / safe_name

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return FileResponse(file_path)


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    file_type: str = "image",
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Delete an uploaded file."""
    if file_type == "image":
        ft = FileType.IMAGE
    elif file_type == "video":
        ft = FileType.VIDEO
    else:
        ft = FileType.DOCUMENT

    asset = (
        db.query(UploadAsset)
        .filter(
            UploadAsset.id == file_id,
            UploadAsset.account_id == account.id,
            UploadAsset.file_type == ft.value,
        )
        .first()
    )

    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    deleted = file_upload_service.delete_file(
        file_id,
        ft,
        filename=asset.filename,
        storage_key=asset.storage_key,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    db.delete(asset)
    db.commit()

    return {"success": True, "message": "File deleted"}


# ============ Direct Post Creation ============

@router.post("/post", response_model=CreatePostResponse, deprecated=True)
async def create_post_with_upload(
    response: Response,
    title: str = Form(...),
    body: str = Form(...),
    location_id: str = Form(...),
    platforms: str = Form("google"),  # comma-separated
    scheduled_at: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Legacy compatibility wrapper for one-shot upload + draft post creation."""
    location = _require_owned_location(db, location_id, account)
    target_platforms = _parse_platforms(platforms)
    parsed_scheduled_at = _parse_scheduled_at(scheduled_at)

    uploaded_image_urls: list[str] = []
    if image is not None:
        uploaded_images = await _upload_legacy_images(files=[image], db=db, account=account)
        uploaded_image_urls = [item.url for item in uploaded_images]

    payload = _create_legacy_draft_posts(
        db=db,
        location=location,
        title=title,
        body=body,
        platforms=target_platforms,
        scheduled_at=parsed_scheduled_at,
        uploaded_image_urls=uploaded_image_urls,
        legacy_endpoint="/uploads/post",
    )
    _annotate_legacy_upload_response(
        response,
        legacy_endpoint=payload.legacy_endpoint,
        canonical_primary_post_path=payload.canonical_primary_post_path,
    )
    return payload


@router.post("/post/with-images", response_model=CreatePostResponse, deprecated=True)
async def create_post_with_multiple_images(
    response: Response,
    title: str = Form(...),
    body: str = Form(...),
    location_id: str = Form(...),
    platforms: str = Form("google"),
    scheduled_at: Optional[str] = Form(None),
    images: list[UploadFile] = File(None),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Legacy compatibility wrapper for multi-upload + draft post creation."""
    location = _require_owned_location(db, location_id, account)
    target_platforms = _parse_platforms(platforms)
    parsed_scheduled_at = _parse_scheduled_at(scheduled_at)
    normalized_images = [item for item in (images or []) if item is not None]

    if not normalized_images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one image is required for /uploads/post/with-images.",
        )

    uploaded_images = await _upload_legacy_images(files=normalized_images, db=db, account=account)
    uploaded_image_urls = [item.url for item in uploaded_images]

    payload = _create_legacy_draft_posts(
        db=db,
        location=location,
        title=title,
        body=body,
        platforms=target_platforms,
        scheduled_at=parsed_scheduled_at,
        uploaded_image_urls=uploaded_image_urls,
        legacy_endpoint="/uploads/post/with-images",
    )
    _annotate_legacy_upload_response(
        response,
        legacy_endpoint=payload.legacy_endpoint,
        canonical_primary_post_path=payload.canonical_primary_post_path,
    )
    return payload
