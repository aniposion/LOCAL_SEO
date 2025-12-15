"""Content approval workflow service."""

import secrets
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.account import Account
from app.models.location import Location
from app.models.post import Platform, Post, PostStatus
from app.services.content import ContentService
from app.services.image_generation import ImageGenerationService, ImagePromptBuilder
from app.services.notification import NotificationChannel, NotificationService

logger = logging.getLogger(__name__)


class ApprovalWorkflowService:
    """Service for managing content approval workflow."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.content_service = ContentService()
        self.image_service = ImageGenerationService(db)
        self.notification_service = NotificationService(db)

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

        # Step 2: Generate image if requested
        image_url = None
        if generate_image and generated_content.image_prompt:
            logger.info("Generating AI image")
            try:
                # 비즈니스 타입 추출 (location 카테고리 또는 서비스에서)
                business_type = services[0] if services else "local business"

                # 이미지 프롬프트 향상
                enhanced_prompt = ImagePromptBuilder.build_local_business_prompt(
                    business_type=business_type,
                    service=theme,
                    location=location.city,
                    mood="welcoming",
                )

                # 원본 프롬프트와 결합
                final_prompt = f"{generated_content.image_prompt}. {enhanced_prompt}"

                image_url = await self.image_service.generate_and_upload(
                    prompt=final_prompt,
                    image_size="1K",  # 1K resolution
                    style=image_style,
                )
                logger.info(f"Image generated: {image_url}")
            except Exception as e:
                logger.error(f"Image generation failed: {e}")
                # 이미지 생성 실패해도 계속 진행

        # Step 3: Create posts with PENDING_APPROVAL status
        created_posts = []

        for platform in platform_targets:
            post_data = self._extract_platform_content(generated_content, platform)
            if not post_data:
                continue

            # 승인 토큰 생성
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
        post.approval_token = None  # 토큰 무효화

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

        # 평균 승인 시간 계산
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
