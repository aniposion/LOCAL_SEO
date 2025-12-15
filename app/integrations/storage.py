"""Cloud storage integration (S3/GCS)."""

from typing import Any

import httpx

from app.core.config import settings


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
        try:
            import boto3
            from botocore.config import Config

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

            # Return public URL (assumes bucket is configured for public access or use presigned)
            return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"

        except ImportError:
            # Fallback for development without boto3
            return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"

    async def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate a presigned URL for downloading."""
        try:
            import boto3
            from botocore.config import Config

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

            url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )

            return url

        except ImportError:
            return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"

    async def delete(self, key: str) -> None:
        """Delete an object from S3."""
        try:
            import boto3
            from botocore.config import Config

            config = Config(region_name=self.region)

            s3_client = boto3.client(
                "s3",
                config=config,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )

            s3_client.delete_object(Bucket=self.bucket, Key=key)

        except ImportError:
            pass

    async def list_objects(self, prefix: str) -> list[dict]:
        """List objects with a given prefix."""
        try:
            import boto3
            from botocore.config import Config

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

        except ImportError:
            return []
