"""Content approval workflow service."""

import logging
import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.account import Account
from app.models.location import Location
from app.models.post import Platform, Post, PostStatus
from app.services.content import ContentService
from app.services.credits import CreditsService
from app.services.image_generation import ImageGenerationService, ImagePromptBuilder
from app.services.notification import NotificationChannel, NotificationService

logger = logging.getLogger(__name__)


class ApprovalUsageLimitError(RuntimeError):
    """Raised when approval workflow usage exceeds the account limit."""

    def __init__(self, detail: dict[str, Any]):
        super().__init__(detail.get("message") or "Approval usage limit exceeded")
        self.detail = detail


class ApprovalGenerationUnavailableError(RuntimeError):
    """Raised when approval draft generation returns no usable platform content."""


class ApprovalWorkflowService:
    """Service for managing content approval workflow."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.content_service = ContentService()
        self.image_service = ImageGenerationService(db)
        self.notification_service = NotificationService(db)

    def _preview_usage(self, account_id: UUID, usage_type: str, count: int = 1) -> None:
        result = CreditsService(self.db).preview_usage(str(account_id), usage_type, count)
        if result.get("allowed"):
            return

        raise ApprovalUsageLimitError(
            {
                "error": "Rate limit exceeded",
                "usage_type": usage_type,
                "message": result.get("reason"),
                "remaining_daily": result.get("remaining_daily", 0),
                "remaining_monthly": result.get("remaining_monthly", 0),
                "cooldown_seconds": result.get("cooldown_remaining_seconds", 0),
                "overage_available": result.get("overage_available", False),
                "overage_cost_cents": result.get("overage_cost_cents", 0),
            }
        )

    def _record_usage(self, account_id: UUID, usage_type: str, count: int = 1) -> None:
        result = CreditsService(self.db).use_credits(str(account_id), usage_type, count)
        if result.get("allowed"):
            return

        logger.warning(
            "Approval workflow usage record failed after successful %s generation for account %s: %s",
            usage_type,
            account_id,
            result.get("reason"),
        )

    def _collect_platform_posts(
        self,
        generated_content: Any,
        platform_targets: list[str],
    ) -> list[tuple[str, dict[str, Any]]]:
        """Return only platforms that produced usable content."""
        posts: list[tuple[str, dict[str, Any]]] = []
        for platform in platform_targets:
            post_data = self._extract_platform_content(generated_content, platform)
            if post_data:
                posts.append((platform, post_data))
        return posts

    async def create_draft_with_approval(
        self,
        location_id: UUID,
        account_id: UUID,
        theme: str,
        services: list[str],
        platform_targets: list[str] | None = None,
        tone: str = "expert yet friendly",
        language: str = "ko",
        audience: str | None = None,
        promo: str | None = None,
        notification_channel: NotificationChannel = NotificationChannel.SLACK,
        generate_image: bool = True,
        image_style: str = "local_business",
    ) -> dict[str, Any]:
        """
        Create draft content and send for approval.

        Workflow:
        1. AI generates content draft
        2. AI generates image (optional)
        3. Posts are created with PENDING_APPROVAL status
        4. Notification sent to owner/agency
        5. Owner approves/rejects via link
        6. If approved, post is queued for publishing
        """
        # Get location and account
        location = self.db.query(Location).filter(Location.id == location_id).first()
        if not location:
            raise ValueError("Location not found")

        account = self.db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise ValueError("Account not found")

        platform_targets = platform_targets or ["GBP", "INSTAGRAM", "WEBSITE"]

        self._preview_usage(account_id, "ai_content", 1)
        if generate_image:
            self._preview_usage(account_id, "ai_image", 1)

        # Step 1: Generate content using AI
        logger.info(f"Generating content for location {location.name}")
        generated_content = await self.content_service.generate(
            location=location,
            theme=theme,
            services=services,
            tone=tone,
            language=language,
            platform_targets=platform_targets,
            audience=audience,
            promo=promo,
        )

        generated_posts = self._collect_platform_posts(generated_content, platform_targets)
        if not generated_posts:
            raise ApprovalGenerationUnavailableError(
                "AI content provider is unavailable."
            )

        # Step 2: Generate image if requested
        image_url = None
        if generate_image and generated_content.image_prompt:
            logger.info("Generating AI image")
            try:
                # Derive a business type hint from the requested services.
                business_type = services[0] if services else "local business"

                # Build a richer prompt for local-business style images.
                enhanced_prompt = ImagePromptBuilder.build_local_business_prompt(
                    business_type=business_type,
                    service=theme,
                    location=location.city,
                    mood="welcoming",
                )

                # Combine the model-provided prompt with the local-business context.
                final_prompt = f"{generated_content.image_prompt}. {enhanced_prompt}"

                image_url = await self.image_service.generate_and_upload(
                    prompt=final_prompt,
                    image_size="1K",  # 1K resolution
                    style=image_style,
                )
                if image_url:
                    self._record_usage(account_id, "ai_image", 1)
                logger.info(f"Image generated: {image_url}")
            except Exception as e:
                logger.error(f"Image generation failed: {e}")
                # Continue without an image if generation fails.

        # Step 3: Create posts with PENDING_APPROVAL status
        created_posts = []

        for platform, post_data in generated_posts:
            # Generate a token for approve/reject actions.
            approval_token = secrets.token_urlsafe(32)

            post = Post(
                location_id=location_id,
                platform=Platform(platform),
                status=PostStatus.PENDING_APPROVAL,
                title=post_data.get("title"),
                body=post_data.get("body"),
                hashtags=post_data.get("hashtags"),
                image_prompt=generated_content.image_prompt,
                ai_image_url=image_url,
                ai_image_generated_at=datetime.now(timezone.utc) if image_url else None,
                generated_by=settings.llm_model,
                generation_params={
                    "theme": theme,
                    "services": services,
                    "tone": tone,
                    "language": language,
                },
                approval_token=approval_token,
                approval_requested_at=datetime.now(timezone.utc),
            )

            self.db.add(post)
            created_posts.append(post)

        self.db.commit()
        if created_posts:
            self._record_usage(account_id, "ai_content", 1)

        # Step 4: Send notification for each post
        notification_results = []
        for post in created_posts:
            self.db.refresh(post)  # Refresh to get relationships
            success = await self.notification_service.send_approval_request(
                post=post,
                account=account,
                channel=notification_channel,
            )
            notification_results.append({
                "post_id": str(post.id),
                "platform": post.platform.value,
                "notification_sent": success,
            })

        return {
            "posts": [
                {
                    "id": str(post.id),
                    "platform": post.platform.value,
                    "status": post.status.value,
                    "title": post.title,
                    "approval_token": post.approval_token,
                }
                for post in created_posts
            ],
            "image_url": image_url,
            "notifications": notification_results,
        }

    def _extract_platform_content(self, generated_content: Any, platform: str) -> dict | None:
        """Extract content for specific platform."""
        if platform == "GBP" and generated_content.gbp:
            return {
                "title": generated_content.gbp.title,
                "body": generated_content.gbp.body,
                "hashtags": generated_content.gbp.hashtags,
            }
        elif platform == "INSTAGRAM" and generated_content.instagram:
            return {
                "title": None,
                "body": generated_content.instagram.caption,
                "hashtags": generated_content.instagram.hashtags,
            }
        elif platform == "WEBSITE" and generated_content.web:
            return {
                "title": generated_content.web.title,
                "body": generated_content.web.markdown,
                "hashtags": None,
            }
        return None

    async def approve_post(
        self,
        post_id: UUID,
        approval_token: str,
        approver_id: UUID | None = None,
        schedule_at: datetime | None = None,
    ) -> Post:
        """Approve a post for publishing."""
        post = self.db.query(Post).filter(
            Post.id == post_id,
            Post.approval_token == approval_token,
        ).first()

        if not post:
            raise ValueError("Post not found or invalid token")

        if post.status != PostStatus.PENDING_APPROVAL:
            raise ValueError(f"Post is not pending approval (current status: {post.status.value})")

        # Update post status
        post.status = PostStatus.APPROVED if not schedule_at else PostStatus.QUEUED
        post.approved_at = datetime.now(timezone.utc)
        post.approved_by_id = approver_id
        post.approval_token = None  # Invalidate the token after approval.

        if schedule_at:
            post.scheduled_at = schedule_at

        self.db.commit()
        self.db.refresh(post)

        # Send approval result notification
        if post.location and post.location.account:
            await self.notification_service.send_approval_result(
                post=post,
                account=post.location.account,
                approved=True,
            )

        logger.info(f"Post {post_id} approved")
        return post

    async def reject_post(
        self,
        post_id: UUID,
        approval_token: str,
        reason: str | None = None,
        rejector_id: UUID | None = None,
    ) -> Post:
        """Reject a post."""
        post = self.db.query(Post).filter(
            Post.id == post_id,
            Post.approval_token == approval_token,
        ).first()

        if not post:
            raise ValueError("Post not found or invalid token")

        if post.status != PostStatus.PENDING_APPROVAL:
            raise ValueError(f"Post is not pending approval (current status: {post.status.value})")

        # Update post status
        post.status = PostStatus.REJECTED
        post.rejected_at = datetime.now(timezone.utc)
        post.rejection_reason = reason
        post.approval_token = None

        self.db.commit()
        self.db.refresh(post)

        # Send rejection notification
        if post.location and post.location.account:
            await self.notification_service.send_approval_result(
                post=post,
                account=post.location.account,
                approved=False,
            )

        logger.info(f"Post {post_id} rejected: {reason}")
        return post

    async def request_revision(
        self,
        post_id: UUID,
        approval_token: str,
        revision_notes: str,
    ) -> Post:
        """Request revision for a post."""
        post = self.db.query(Post).filter(
            Post.id == post_id,
            Post.approval_token == approval_token,
        ).first()

        if not post:
            raise ValueError("Post not found or invalid token")

        # Keep status as PENDING_APPROVAL but add revision notes
        if not post.generation_params:
            post.generation_params = {}

        post.generation_params["revision_notes"] = revision_notes
        post.generation_params["revision_requested_at"] = datetime.now(timezone.utc).isoformat()

        self.db.commit()
        self.db.refresh(post)

        logger.info(f"Revision requested for post {post_id}")
        return post

    def get_pending_approvals(
        self,
        account_id: UUID,
        limit: int = 50,
    ) -> list[Post]:
        """Get all posts pending approval for an account."""
        return (
            self.db.query(Post)
            .join(Location)
            .filter(
                Location.account_id == account_id,
                Post.status == PostStatus.PENDING_APPROVAL,
            )
            .order_by(Post.approval_requested_at.desc())
            .limit(limit)
            .all()
        )

    def get_approval_stats(self, account_id: UUID) -> dict[str, Any]:
        """Get approval workflow statistics."""
        from sqlalchemy import func

        base_query = (
            self.db.query(Post)
            .join(Location)
            .filter(Location.account_id == account_id)
        )

        pending = base_query.filter(Post.status == PostStatus.PENDING_APPROVAL).count()
        approved = base_query.filter(Post.status == PostStatus.APPROVED).count()
        rejected = base_query.filter(Post.status == PostStatus.REJECTED).count()
        posted = base_query.filter(Post.status == PostStatus.POSTED).count()

        # Average time from approval request to approval.
        avg_approval_time = (
            self.db.query(func.avg(Post.approved_at - Post.approval_requested_at))
            .join(Location)
            .filter(
                Location.account_id == account_id,
                Post.approved_at.isnot(None),
                Post.approval_requested_at.isnot(None),
            )
            .scalar()
        )

        return {
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "posted": posted,
            "total": pending + approved + rejected + posted,
            "approval_rate": approved / (approved + rejected) * 100 if (approved + rejected) > 0 else 0,
            "avg_approval_time_hours": avg_approval_time.total_seconds() / 3600 if avg_approval_time else None,
        }
