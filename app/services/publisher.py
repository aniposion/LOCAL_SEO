"""Publisher service for posting content to platforms."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.integrations.gbp import GBPClient
from app.integrations.instagram import InstagramClient
from app.integrations.website import WebsiteClient
from app.models.channel import Channel, ChannelStatus, ChannelType
from app.models.location import Location
from app.models.post import Platform, Post, PostStatus
from app.models.publish_job import PublishJob, PublishJobStatus
from app.services.notification import NotificationService


logger = logging.getLogger(__name__)


class PublisherService:
    """Service for publishing posts to various platforms."""

    def __init__(self, db: Session) -> None:
        self.db = db

    async def publish_post(self, post: Post) -> None:
        """Publish a single post to its platform."""
        job = self._create_publish_job(post)
        channel: Channel | None = None

        try:
            channel = self._get_active_channel(post)
            credentials = self._get_channel_credentials(post, channel)
            self._validate_publish_request(post, channel, credentials)
            provider_post_id = await self._publish_to_platform(post, channel)
            post.status = PostStatus.POSTED
            post.posted_at = datetime.now(timezone.utc)
            post.provider_post_id = provider_post_id
            post.error_message = None
            channel.status = ChannelStatus.CONNECTED
            channel.error_message = None
            channel.last_sync_at = datetime.now(timezone.utc)
            self._complete_publish_job(job, provider_post_id)
            self.db.commit()
        except Exception as e:
            post.status = PostStatus.FAILED
            post.error_message = str(e)
            if channel is not None:
                channel.status = (
                    ChannelStatus.EXPIRED if self._is_reauth_failure(channel, str(e)) else ChannelStatus.ERROR
                )
                channel.error_count = (channel.error_count or 0) + 1
                channel.error_message = str(e)[:500]
            self._fail_publish_job(job, e)
            self.db.commit()
            await self._safe_notify_publish_failure(
                post=post,
                channel=channel,
                job=job,
                error_message=str(e),
            )
            raise

    async def publish_queued_posts(self) -> dict:
        """Publish all queued/approved posts that are due."""
        now = datetime.now(timezone.utc)

        # Get posts that are either:
        # 1. QUEUED with scheduled_at <= now
        # 2. APPROVED (ready for immediate publish)
        from sqlalchemy import or_, and_

        posts = (
            self.db.query(Post)
            .filter(
                or_(
                    and_(
                        Post.status == PostStatus.QUEUED,
                        Post.scheduled_at <= now,
                    ),
                    and_(
                        Post.status == PostStatus.APPROVED,
                        or_(
                            Post.scheduled_at.is_(None),
                            Post.scheduled_at <= now,
                        ),
                    ),
                )
            )
            .all()
        )

        results = {"success": 0, "failed": 0, "errors": []}

        for post in posts:
            try:
                await self.publish_post(post)
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"post_id": str(post.id), "error": str(e)})

        return results

    def _is_reauth_failure(self, channel: Channel | None, error_message: str) -> bool:
        """Identify failures that require reconnecting the publish channel."""
        lowered = error_message.lower()
        if channel is not None and channel.is_token_expired:
            return True
        return any(token in lowered for token in ("expired", "reconnect", "reauth"))

    async def _notify_publish_failure(
        self,
        *,
        post: Post,
        channel: Channel | None,
        job: PublishJob,
        error_message: str,
    ) -> None:
        """Persist an inbox/audit alert for a failed publish attempt."""
        location = self.db.query(Location).filter(Location.id == post.location_id).first()
        if not location:
            logger.warning("Could not resolve location for failed publish post %s", post.id)
            return

        account_id = location.account_id
        location_name = location.name or "this location"
        platform_name = post.platform.value
        notification_service = NotificationService(self.db)

        if self._is_reauth_failure(channel, error_message):
            await notification_service.send_notification(
                account_id=account_id,
                title=f"Reconnect {platform_name} publishing",
                message=(
                    f"{location_name} can no longer publish to {platform_name} until the integration is reconnected."
                    f"\n\nReason: {error_message}"
                    "\n\nReconnect the channel in Integrations, then retry the failed publish job."
                ),
                notification_type="publish_reauth_required",
                data={
                    "url": "/dashboard/integrations",
                    "job_id": str(job.id),
                    "post_id": str(post.id),
                    "location_id": str(location.id),
                    "platform": platform_name.lower(),
                    "error_code": job.error_code,
                },
            )
            return

        await notification_service.send_notification(
            account_id=account_id,
            title=f"{platform_name} publish failed",
            message=(
                f"Publishing for {location_name} could not be completed on {platform_name}."
                f"\n\nReason: {error_message}"
            ),
            notification_type="publish_job_failed",
            data={
                "url": f"/dashboard/content/{post.id}",
                "job_id": str(job.id),
                "post_id": str(post.id),
                "location_id": str(location.id),
                "platform": platform_name.lower(),
                "error_code": job.error_code,
            },
        )

    async def _safe_notify_publish_failure(
        self,
        *,
        post: Post,
        channel: Channel | None,
        job: PublishJob,
        error_message: str,
    ) -> None:
        """Do not let alert delivery failures mask the original publish failure."""
        try:
            await self._notify_publish_failure(
                post=post,
                channel=channel,
                job=job,
                error_message=error_message,
            )
        except Exception as exc:
            logger.warning(
                "Failed to notify account about publish job %s failure: %s",
                job.id,
                exc,
            )

    async def _publish_to_platform(self, post: Post, channel: Channel) -> str:
        """Publish to specific platform and return provider post ID."""
        # Get decrypted credentials
        credentials = channel.get_credentials() if hasattr(channel, 'get_credentials') else channel.credentials

        # Use AI-generated image if available, otherwise use provided image_url
        image_url = post.ai_image_url or post.image_url

        if post.platform == Platform.GBP:
            client = GBPClient(credentials)
            return await client.create_post(
                title=post.title,
                body=post.body,
                image_url=image_url,
            )

        elif post.platform == Platform.INSTAGRAM:
            client = InstagramClient(credentials)
            return await client.publish_image(
                image_url=image_url,
                caption=post.body,
                hashtags=post.hashtags or [],
            )

        elif post.platform == Platform.WEBSITE:
            client = WebsiteClient(credentials)
            return await client.publish_markdown(
                title=post.title,
                content=post.body,
            )

        raise ValueError(f"Unsupported platform: {post.platform}")

    def _get_active_channel(self, post: Post) -> Channel:
        channel = (
            self.db.query(Channel)
            .filter(
                Channel.location_id == post.location_id,
                Channel.type == self._platform_to_channel_type(post.platform),
                Channel.is_active == True,
            )
            .first()
        )

        if not channel:
            raise ValueError(f"No active channel found for {post.platform.value}")

        return channel

    def _get_channel_credentials(self, post: Post, channel: Channel) -> dict:
        credentials = (
            channel.get_credentials() if hasattr(channel, "get_credentials") else channel.credentials
        )
        if not credentials:
            raise ValueError(f"No credentials found for {post.platform.value}")
        return credentials

    def _validate_publish_request(self, post: Post, channel: Channel, credentials: dict) -> None:
        if post.platform == Platform.INSTAGRAM:
            if not (post.ai_image_url or post.image_url):
                raise ValueError("Instagram publishing requires an image")
            if not credentials.get("access_token"):
                raise ValueError("Instagram access token is missing")
            if not credentials.get("ig_user_id"):
                raise ValueError("Instagram business account is not connected")
            if channel.is_token_expired:
                raise ValueError("Instagram connection has expired and must be reconnected")

    def _create_publish_job(self, post: Post) -> PublishJob:
        job = PublishJob(
            post_id=post.id,
            platform=post.platform.value.lower(),
            status=PublishJobStatus.PROCESSING,
            tries=1,
            request_payload={
                "post_id": str(post.id),
                "platform": post.platform.value,
                "title": post.title,
                "body": post.body,
                "image_url": post.ai_image_url or post.image_url,
                "hashtags": post.hashtags or [],
            },
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(job)
        self.db.flush()
        return job

    def _complete_publish_job(self, job: PublishJob, provider_post_id: str) -> None:
        job.status = PublishJobStatus.COMPLETED
        job.platform_post_id = provider_post_id
        job.response_payload = {"provider_post_id": provider_post_id}
        job.completed_at = datetime.now(timezone.utc)
        job.last_error = None
        job.error_code = None

    def _fail_publish_job(self, job: PublishJob, error: Exception) -> None:
        job.status = PublishJobStatus.FAILED
        job.last_error = str(error)
        job.error_code = "PUBLISH_FAILED"
        job.completed_at = datetime.now(timezone.utc)
        job.response_payload = {"error": str(error)}

    def _platform_to_channel_type(self, platform: Platform) -> ChannelType:
        """Convert Platform enum to ChannelType enum."""
        mapping = {
            Platform.GBP: ChannelType.GBP,
            Platform.INSTAGRAM: ChannelType.INSTAGRAM,
            Platform.WEBSITE: ChannelType.WEBSITE,
        }
        return mapping[platform]
