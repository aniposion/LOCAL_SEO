"""
File Upload Router
Handle image and media uploads
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.routers.deps import get_current_account, get_db
from app.models.account import Account
from app.services.file_upload import file_upload_service, FileType, UploadedFile
from app.services.usage_limiter import usage_limiter, UsageType

router = APIRouter(prefix="/uploads", tags=["Uploads"])


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
    title: str
    body: str
    status: str
    image_urls: list[str]
    platforms: list[str]
    scheduled_at: Optional[datetime] = None
    created_at: datetime


# ============ Endpoints ============

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
    )


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
    
    return UploadResponse(
        id=uploaded.id,
        filename=uploaded.filename,
        original_filename=uploaded.original_filename,
        file_type=uploaded.file_type.value,
        mime_type=uploaded.mime_type,
        size_bytes=uploaded.size_bytes,
        url=uploaded.url,
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    file_type: str = "image",
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Delete an uploaded file."""
    ft = FileType.IMAGE if file_type == "image" else FileType.VIDEO
    
    deleted = file_upload_service.delete_file(file_id, ft)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )
    
    return {"success": True, "message": "File deleted"}


# ============ Direct Post Creation ============

@router.post("/post", response_model=CreatePostResponse)
async def create_post_with_upload(
    title: str = Form(...),
    body: str = Form(...),
    location_id: str = Form(...),
    platforms: str = Form("google"),  # comma-separated
    scheduled_at: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Create a post with optional image upload."""
    image_urls = []
    
    # Upload image if provided
    if image:
        uploaded = await file_upload_service.upload_image(
            file=image,
            account_id=str(account.id),
        )
        image_urls.append(uploaded.url)
    
    # Parse platforms
    platform_list = [p.strip() for p in platforms.split(",")]
    
    # Parse scheduled time
    scheduled = None
    if scheduled_at:
        try:
            scheduled = datetime.fromisoformat(scheduled_at)
        except ValueError:
            pass
    
    # Create post (in production, save to database)
    post_id = f"post_{datetime.now().timestamp()}"
    
    return CreatePostResponse(
        id=post_id,
        title=title,
        body=body,
        status="draft" if not scheduled else "scheduled",
        image_urls=image_urls,
        platforms=platform_list,
        scheduled_at=scheduled,
        created_at=datetime.now(),
    )


@router.post("/post/with-images", response_model=CreatePostResponse)
async def create_post_with_multiple_images(
    title: str = Form(...),
    body: str = Form(...),
    location_id: str = Form(...),
    platforms: str = Form("google"),
    scheduled_at: Optional[str] = Form(None),
    images: list[UploadFile] = File(None),
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Create a post with multiple image uploads."""
    image_urls = []
    
    if images:
        if len(images) > 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 5 images per post",
            )
        
        for img in images:
            uploaded = await file_upload_service.upload_image(
                file=img,
                account_id=str(account.id),
            )
            image_urls.append(uploaded.url)
    
    platform_list = [p.strip() for p in platforms.split(",")]
    
    scheduled = None
    if scheduled_at:
        try:
            scheduled = datetime.fromisoformat(scheduled_at)
        except ValueError:
            pass
    
    post_id = f"post_{datetime.now().timestamp()}"
    
    return CreatePostResponse(
        id=post_id,
        title=title,
        body=body,
        status="draft" if not scheduled else "scheduled",
        image_urls=image_urls,
        platforms=platform_list,
        scheduled_at=scheduled,
        created_at=datetime.now(),
    )
