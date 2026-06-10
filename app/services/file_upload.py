"""
File Upload Service
Handle image and media uploads with validation
"""
import os
import uuid
from io import BytesIO
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from fastapi import UploadFile, HTTPException, status

from app.core.config import settings
from app.services.storage import get_storage_service


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
    storage_key: Optional[str] = None
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

ALLOWED_DOCUMENT_TYPES = {
    "application/pdf": ".pdf",
    "text/csv": ".csv",
    "text/plain": ".txt",
    "application/json": ".json",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}

MAX_IMAGE_SIZE_MB = 10
MAX_VIDEO_SIZE_MB = 100
MAX_DOCUMENT_SIZE_MB = 20


class FileUploadService:
    """Service for handling file uploads."""
    
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.upload_dir / "images").mkdir(exist_ok=True)
        (self.upload_dir / "videos").mkdir(exist_ok=True)
        (self.upload_dir / "documents").mkdir(exist_ok=True)
        (self.upload_dir / "thumbnails").mkdir(exist_ok=True)

    def _require_supported_upload_backend(self) -> None:
        """Avoid silent local-file uploads in production."""
        if settings.app_env != "prod":
            return

        storage = get_storage_service()
        if not storage.is_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cloud storage must be configured for uploads in production.",
            )

    def _subdir_for_file_type(self, file_type: FileType) -> str:
        """Return the storage subdirectory for a file type."""
        if file_type == FileType.IMAGE:
            return "images"
        if file_type == FileType.VIDEO:
            return "videos"
        return "documents"

    def _local_url_for(self, subdir: str, filename: str) -> str:
        """Build the local development URL for a stored file."""
        base_url = os.getenv("UPLOAD_BASE_URL", "http://localhost:8000/uploads")
        return f"{base_url}/{subdir}/{filename}"

    def _storage_key_for(self, file_type: FileType, filename: str) -> str:
        """Build the canonical storage key for a file."""
        subdir = self._subdir_for_file_type(file_type)
        return f"uploads/{subdir}/{filename}"

    def _store_file_bytes(
        self,
        *,
        file_type: FileType,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> tuple[str, str]:
        """Store bytes in cloud storage when configured, otherwise locally for non-prod."""
        subdir = self._subdir_for_file_type(file_type)
        storage_key = self._storage_key_for(file_type, filename)
        storage = get_storage_service()

        if storage.is_configured():
            return (
                storage.upload_file(
                file_data=content,
                filename=filename,
                content_type=content_type,
                folder=f"uploads/{subdir}",
                ),
                storage_key,
            )

        file_path = self.upload_dir / subdir / filename
        with open(file_path, "wb") as handle:
            handle.write(content)
        return self._local_url_for(subdir, filename), storage_key

    def _image_dimensions_from_bytes(self, content: bytes) -> tuple[Optional[int], Optional[int]]:
        """Get image dimensions without requiring a local file path."""
        try:
            from PIL import Image

            with Image.open(BytesIO(content)) as img:
                return img.size
        except ImportError:
            return None, None
        except Exception:
            return None, None

    def _delete_cloud_file(
        self,
        file_id: str,
        file_type: FileType,
        *,
        filename: str | None = None,
        storage_key: str | None = None,
    ) -> bool:
        """Delete a cloud-backed file by exact key when possible, prefix as fallback."""
        storage = get_storage_service()
        if not storage.is_configured():
            return False

        if storage_key and storage.delete_file(storage_key):
            return True

        if filename:
            exact_key = self._storage_key_for(file_type, filename)
            if storage.delete_file(exact_key):
                return True

        subdir = self._subdir_for_file_type(file_type)
        prefix = f"uploads/{subdir}/{file_id}."
        deleted = False
        for object_name in storage.list_files(prefix=prefix):
            deleted = storage.delete_file(object_name) or deleted
        return deleted
    
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

    def validate_document(self, file: UploadFile) -> None:
        """Validate document file."""
        if file.content_type not in ALLOWED_DOCUMENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid document type: {file.content_type}. Allowed: {list(ALLOWED_DOCUMENT_TYPES.keys())}",
            )

        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)

        if size > MAX_DOCUMENT_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Document too large. Maximum size: {MAX_DOCUMENT_SIZE_MB}MB",
            )
    
    async def upload_image(
        self,
        file: UploadFile,
        account_id: str,
    ) -> UploadedFile:
        """Upload an image file."""
        self._require_supported_upload_backend()
        self.validate_image(file)
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        ext = ALLOWED_IMAGE_TYPES[file.content_type]
        filename = f"{file_id}{ext}"
        
        content = await file.read()
        url, storage_key = self._store_file_bytes(
            file_type=FileType.IMAGE,
            filename=filename,
            content=content,
            content_type=file.content_type,
        )
        width, height = self._image_dimensions_from_bytes(content)
        
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
            storage_key=storage_key,
        )
    
    async def upload_video(
        self,
        file: UploadFile,
        account_id: str,
    ) -> UploadedFile:
        """Upload a video file."""
        self._require_supported_upload_backend()
        self.validate_video(file)
        
        file_id = str(uuid.uuid4())
        ext = ALLOWED_VIDEO_TYPES[file.content_type]
        filename = f"{file_id}{ext}"
        
        content = await file.read()
        url, storage_key = self._store_file_bytes(
            file_type=FileType.VIDEO,
            filename=filename,
            content=content,
            content_type=file.content_type,
        )
        
        return UploadedFile(
            id=file_id,
            filename=filename,
            original_filename=file.filename or "unknown",
            file_type=FileType.VIDEO,
            mime_type=file.content_type,
            size_bytes=len(content),
            url=url,
            account_id=account_id,
            storage_key=storage_key,
        )

    async def upload_document(
        self,
        file: UploadFile,
        account_id: str,
    ) -> UploadedFile:
        """Upload a document file."""
        self._require_supported_upload_backend()
        self.validate_document(file)

        file_id = str(uuid.uuid4())
        ext = ALLOWED_DOCUMENT_TYPES[file.content_type]
        filename = f"{file_id}{ext}"

        content = await file.read()
        url, storage_key = self._store_file_bytes(
            file_type=FileType.DOCUMENT,
            filename=filename,
            content=content,
            content_type=file.content_type,
        )

        return UploadedFile(
            id=file_id,
            filename=filename,
            original_filename=file.filename or "unknown",
            file_type=FileType.DOCUMENT,
            mime_type=file.content_type,
            size_bytes=len(content),
            url=url,
            account_id=account_id,
            storage_key=storage_key,
        )
    
    def delete_file(
        self,
        file_id: str,
        file_type: FileType,
        *,
        filename: str | None = None,
        storage_key: str | None = None,
    ) -> bool:
        """Delete an uploaded file."""
        if self._delete_cloud_file(
            file_id,
            file_type,
            filename=filename,
            storage_key=storage_key,
        ):
            return True

        subdir = self._subdir_for_file_type(file_type)

        if filename:
            file_path = self.upload_dir / subdir / filename
            if file_path.exists() and file_path.is_file():
                file_path.unlink()
                return True

        for file_path in (self.upload_dir / subdir).glob(f"{file_id}.*"):
            file_path.unlink()
            return True

        return False
    
    def get_file_path(self, file_id: str, file_type: FileType) -> Optional[Path]:
        """Get the path to an uploaded file."""
        subdir = self._subdir_for_file_type(file_type)
        
        for file_path in (self.upload_dir / subdir).glob(f"{file_id}.*"):
            return file_path
        
        return None


# Global instance
file_upload_service = FileUploadService()
