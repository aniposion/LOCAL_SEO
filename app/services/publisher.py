"""Publisher service for posting content to platforms."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.integrations.gbp import GBPClient
from app.integrations.instagram import InstagramClient
from app.integrations.website import WebsiteClient
from app.models.channel import Channel, ChannelType
from app.models.post import Platform, Post, PostStatus


class PublisherService:
    """Service for publishing posts to various platforms."""

    def __init__(self, db: Session) -> None:
        self.db = db

    async def publish_post(self, post: Post) -> None:
        """Publish a single post to its platform."""
        # Get channel credentials
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

        # Get credentials (decrypted if encrypted)
        credentials = channel.get_credentials() if hasattr(channel, 'get_credentials') else channel.credentials
        if not credentials:
            raise ValueError(f"No credentials found for {post.platform.value}")

        try:
            provider_post_id = await self._publish_to_platform(post, channel)
            post.status = PostStatus.POSTED
            post.posted_at = datetime.now(timezone.utc)
            post.provider_post_id = provider_post_id
            post.error_message = None
        except Exception as e:
            post.status = PostStatus.FAILED
            post.error_message = str(e)
            raise

        self.db.commit()

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

    def _platform_to_channel_type(self, platform: Platform) -> ChannelType:
        """Convert Platform enum to ChannelType enum."""
        mapping = {
            Platform.GBP: ChannelType.GBP,
            Platform.INSTAGRAM: ChannelType.INSTAGRAM,
            Platform.WEBSITE: ChannelType.WEBSITE,
        }
        return mapping[platform]
