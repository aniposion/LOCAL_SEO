"""Cloud storage integration (S3/GCS)."""

from typing import Any

from app.core.config import settings


class StorageClientUnavailableError(RuntimeError):
    """Raised when report storage is not configured."""


class StorageClientUploadError(RuntimeError):
    """Raised when report storage upload fails."""


class StorageClient:
    """Client for cloud storage (S3)."""

    def __init__(self) -> None:
        self.bucket = settings.s3_bucket
        self.region = settings.aws_region

    async def upload(
        self,
        key: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload content to S3 and return URL."""
        if not self.bucket or not self.region:
            raise StorageClientUnavailableError("S3 storage is not configured for report uploads.")

        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise StorageClientUnavailableError("boto3 is required for S3 report uploads.")

        try:
            config = Config(
                region_name=self.region,
                signature_version="s3v4",
            )

            s3_client = boto3.client(
                "s3",
                config=config,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )

            s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )

            return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"
        except Exception as exc:
            raise StorageClientUploadError(str(exc)) from exc

    async def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate a presigned URL for downloading."""
        if not self.bucket or not self.region:
            raise StorageClientUnavailableError("S3 storage is not configured for report downloads.")

        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise StorageClientUnavailableError("boto3 is required for S3 report downloads.")

        try:
            config = Config(
                region_name=self.region,
                signature_version="s3v4",
            )

            s3_client = boto3.client(
                "s3",
                config=config,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )

            return s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except Exception as exc:
            raise StorageClientUploadError(str(exc)) from exc

    async def delete(self, key: str) -> None:
        """Delete an object from S3."""
        if not self.bucket or not self.region:
            raise StorageClientUnavailableError("S3 storage is not configured for report cleanup.")

        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise StorageClientUnavailableError("boto3 is required for S3 report cleanup.")

        try:
            config = Config(region_name=self.region)

            s3_client = boto3.client(
                "s3",
                config=config,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )

            s3_client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            raise StorageClientUploadError(str(exc)) from exc

    async def list_objects(self, prefix: str) -> list[dict]:
        """List objects with a given prefix."""
        if not self.bucket or not self.region:
            raise StorageClientUnavailableError("S3 storage is not configured for report listing.")

        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise StorageClientUnavailableError("boto3 is required for S3 report listing.")

        try:
            config = Config(region_name=self.region)

            s3_client = boto3.client(
                "s3",
                config=config,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )

            response = s3_client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)

            return [
                {"key": obj["Key"], "size": obj["Size"], "modified": obj["LastModified"]}
                for obj in response.get("Contents", [])
            ]
        except Exception as exc:
            raise StorageClientUploadError(str(exc)) from exc
