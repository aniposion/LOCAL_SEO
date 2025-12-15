"""
File Upload Service
Handle image and media uploads with validation
"""
import os
import uuid
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import hashlib

from fastapi import UploadFile, HTTPException, status


class FileType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"


@dataclass
class UploadedFile:
    """Uploaded file metadata."""
    id: str
    filename: str
    original_filename: str
    file_type: FileType
    mime_type: str
    size_bytes: int
    url: str
    thumbnail_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    account_id: Optional[str] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


# Allowed file types and size limits
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
}

MAX_IMAGE_SIZE_MB = 10
MAX_VIDEO_SIZE_MB = 100


class FileUploadService:
    """Service for handling file uploads."""
    
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.upload_dir / "images").mkdir(exist_ok=True)
        (self.upload_dir / "videos").mkdir(exist_ok=True)
        (self.upload_dir / "thumbnails").mkdir(exist_ok=True)
    
    def validate_image(self, file: UploadFile) -> None:
        """Validate image file."""
        if file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid image type: {file.content_type}. Allowed: {list(ALLOWED_IMAGE_TYPES.keys())}",
            )
        
        # Check file size (need to read to get size)
        file.file.seek(0, 2)  # Seek to end
        size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Image too large. Maximum size: {MAX_IMAGE_SIZE_MB}MB",
            )
    
    def validate_video(self, file: UploadFile) -> None:
        """Validate video file."""
        if file.content_type not in ALLOWED_VIDEO_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid video type: {file.content_type}. Allowed: {list(ALLOWED_VIDEO_TYPES.keys())}",
            )
        
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)
        
        if size > MAX_VIDEO_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Video too large. Maximum size: {MAX_VIDEO_SIZE_MB}MB",
            )
    
    async def upload_image(
        self,
        file: UploadFile,
        account_id: str,
    ) -> UploadedFile:
        """Upload an image file."""
        self.validate_image(file)
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        ext = ALLOWED_IMAGE_TYPES[file.content_type]
        filename = f"{file_id}{ext}"
        
        # Save file
        file_path = self.upload_dir / "images" / filename
        content = await file.read()
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Get image dimensions (optional, requires PIL)
        width, height = None, None
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                width, height = img.size
        except ImportError:
            pass
        
        # Generate URL (in production, use CDN/S3)
        base_url = os.getenv("UPLOAD_BASE_URL", "http://localhost:8000/uploads")
        url = f"{base_url}/images/{filename}"
        
        return UploadedFile(
            id=file_id,
            filename=filename,
            original_filename=file.filename or "unknown",
            file_type=FileType.IMAGE,
            mime_type=file.content_type,
            size_bytes=len(content),
            url=url,
            width=width,
            height=height,
            account_id=account_id,
        )
    
    async def upload_video(
        self,
        file: UploadFile,
        account_id: str,
    ) -> UploadedFile:
        """Upload a video file."""
        self.validate_video(file)
        
        file_id = str(uuid.uuid4())
        ext = ALLOWED_VIDEO_TYPES[file.content_type]
        filename = f"{file_id}{ext}"
        
        file_path = self.upload_dir / "videos" / filename
        content = await file.read()
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        base_url = os.getenv("UPLOAD_BASE_URL", "http://localhost:8000/uploads")
        url = f"{base_url}/videos/{filename}"
        
        return UploadedFile(
            id=file_id,
            filename=filename,
            original_filename=file.filename or "unknown",
            file_type=FileType.VIDEO,
            mime_type=file.content_type,
            size_bytes=len(content),
            url=url,
            account_id=account_id,
        )
    
    def delete_file(self, file_id: str, file_type: FileType) -> bool:
        """Delete an uploaded file."""
        subdir = "images" if file_type == FileType.IMAGE else "videos"
        
        # Find file with any extension
        for file_path in (self.upload_dir / subdir).glob(f"{file_id}.*"):
            file_path.unlink()
            return True
        
        return False
    
    def get_file_path(self, file_id: str, file_type: FileType) -> Optional[Path]:
        """Get the path to an uploaded file."""
        subdir = "images" if file_type == FileType.IMAGE else "videos"
        
        for file_path in (self.upload_dir / subdir).glob(f"{file_id}.*"):
            return file_path
        
        return None


# Global instance
file_upload_service = FileUploadService()
