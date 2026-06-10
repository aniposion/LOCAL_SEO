"""Storage service wrapper with optional GCS or S3 support."""
from datetime import timedelta
from pathlib import PurePosixPath
from typing import Any, Optional

from app.core.config import settings


class CloudStorageService:
    """Manage file uploads through Google Cloud Storage or S3 when available."""

    def __init__(self):
        self.bucket_name = settings.gcs_bucket
        self._client: Optional[Any] = None
        self._bucket: Optional[Any] = None
        self._storage_module: Optional[Any] = None
        self._cloud_error_cls: Optional[type[Exception]] = None
        self._provider: Optional[str] = None

    def _ensure_sdk(self) -> None:
        """Import the available cloud SDK lazily so app import does not fail."""
        if self._storage_module is not None and self._provider is not None:
            return

        # Prefer GCS when configured.
        if settings.gcs_bucket:
            try:
                from google.cloud import storage
                from google.cloud.exceptions import GoogleCloudError

                self._storage_module = storage
                self._cloud_error_cls = GoogleCloudError
                self._provider = "gcs"
                return
            except ModuleNotFoundError:
                pass

        if settings.s3_bucket and settings.aws_region and settings.aws_access_key_id and settings.aws_secret_access_key:
            try:
                import boto3  # type: ignore
                from botocore.exceptions import BotoCoreError, ClientError  # type: ignore

                self._storage_module = boto3
                self._cloud_error_cls = (BotoCoreError, ClientError)
                self._provider = "s3"
                return
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "boto3 is required for S3 file storage features"
                ) from exc

        raise RuntimeError(
            "No supported cloud storage provider is configured. Configure GCS or S3 for file storage features."
        )

    def is_configured(self) -> bool:
        """Return whether any supported cloud storage provider is configured."""
        try:
            self._ensure_sdk()
            return True
        except RuntimeError:
            return False

    def _build_object_name(
        self,
        filename: str,
        folder: str = "uploads",
        object_name: str | None = None,
    ) -> str:
        """Build a deterministic cloud object key."""
        if object_name:
            return str(PurePosixPath(object_name))

        safe_filename = PurePosixPath(filename).name
        if folder:
            return str(PurePosixPath(folder) / safe_filename)
        return safe_filename

    def _build_public_url(self, object_name: str) -> str:
        """Build a public URL for the configured storage provider."""
        if self._provider == "gcs":
            return f"https://storage.googleapis.com/{self.bucket_name}/{object_name}"
        if self._provider == "s3":
            return f"https://{settings.s3_bucket}.s3.{settings.aws_region}.amazonaws.com/{object_name}"
        raise RuntimeError("No cloud storage provider is available.")

    @property
    def client(self) -> Any:
        """Create the SDK client only when storage is actually used."""
        if self._client is None:
            self._ensure_sdk()
            if self._provider == "gcs":
                self._client = self._storage_module.Client()
            elif self._provider == "s3":
                self._client = self._storage_module.client(
                    "s3",
                    region_name=settings.aws_region,
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                )
            else:
                raise RuntimeError("No cloud storage provider is available.")
        return self._client

    @property
    def bucket(self) -> Any:
        """Resolve the target bucket lazily for GCS."""
        if self._bucket is None:
            self._ensure_sdk()
            if self._provider != "gcs":
                raise RuntimeError("Bucket access is only available for GCS in this helper.")
            self._bucket = self.client.bucket(self.bucket_name)
        return self._bucket

    def upload_file(
        self,
        file_data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        folder: str = "uploads",
        object_name: str | None = None,
    ) -> str:
        """Upload raw bytes and return a public URL."""
        try:
            resolved_object_name = self._build_object_name(
                filename=filename,
                folder=folder,
                object_name=object_name,
            )

            self._ensure_sdk()
            if self._provider == "gcs":
                blob = self.bucket.blob(resolved_object_name)
                blob.upload_from_string(file_data, content_type=content_type)
                return self._build_public_url(resolved_object_name)
            if self._provider == "s3":
                self.client.put_object(
                    Bucket=settings.s3_bucket,
                    Key=resolved_object_name,
                    Body=file_data,
                    ContentType=content_type,
                )
                return self._build_public_url(resolved_object_name)
            raise RuntimeError("No cloud storage provider is available.")
        except Exception as exc:
            raise Exception(f"Failed to upload file: {exc}") from exc

    async def upload_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        folder: str = "uploads",
        object_name: str | None = None,
    ) -> str:
        """Async-friendly wrapper used by image generation services."""
        return self.upload_file(
            file_data=file_bytes,
            filename=filename,
            content_type=content_type,
            folder=folder,
            object_name=object_name,
        )

    def upload_from_file(
        self,
        file_path: str,
        destination_name: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a local file path and return a public URL."""
        try:
            with open(file_path, "rb") as handle:
                file_data = handle.read()
            return self.upload_file(
                file_data=file_data,
                filename=PurePosixPath(destination_name).name,
                content_type=content_type,
                object_name=destination_name,
            )
        except Exception as exc:
            raise Exception(f"Failed to upload file: {exc}") from exc

    def get_signed_url(self, blob_name: str, expiration_minutes: int = 60) -> str:
        """Generate a temporary signed URL."""
        try:
            self._ensure_sdk()
            if self._provider == "gcs":
                blob = self.bucket.blob(blob_name)
                return blob.generate_signed_url(
                    expiration=timedelta(minutes=expiration_minutes),
                    method="GET",
                )
            if self._provider == "s3":
                return self.client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": settings.s3_bucket, "Key": blob_name},
                    ExpiresIn=expiration_minutes * 60,
                )
            raise RuntimeError("No cloud storage provider is available.")
        except Exception as exc:
            raise Exception(f"Failed to generate signed URL: {exc}") from exc

    def delete_file(self, blob_name: str) -> bool:
        """Delete a file from the bucket."""
        try:
            self._ensure_sdk()
            if self._provider == "gcs":
                blob = self.bucket.blob(blob_name)
                blob.delete()
                return True
            if self._provider == "s3":
                self.client.delete_object(Bucket=settings.s3_bucket, Key=blob_name)
                return True
            return False
        except Exception:
            return False

    def file_exists(self, blob_name: str) -> bool:
        """Check whether a file exists."""
        try:
            self._ensure_sdk()
            if self._provider == "gcs":
                blob = self.bucket.blob(blob_name)
                return blob.exists()
            if self._provider == "s3":
                self.client.head_object(Bucket=settings.s3_bucket, Key=blob_name)
                return True
            return False
        except Exception:
            return False

    def list_files(self, prefix: str = "") -> list[str]:
        """List files under a prefix."""
        self._ensure_sdk()
        if self._provider == "gcs":
            blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)
            return [blob.name for blob in blobs]
        if self._provider == "s3":
            response = self.client.list_objects_v2(
                Bucket=settings.s3_bucket,
                Prefix=prefix,
            )
            return [
                item["Key"]
                for item in response.get("Contents", [])
                if "Key" in item
            ]
        return []


_storage_service: Optional[CloudStorageService] = None


def get_storage_service() -> CloudStorageService:
    """Return a singleton storage service."""
    global _storage_service
    if _storage_service is None:
        _storage_service = CloudStorageService()
    return _storage_service


StorageService = CloudStorageService
