"""
Reliable Publisher Service - Job queue with retry logic and idempotency.
P0 Priority Feature
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.location import Location
from app.models.post import Post
from app.models.publish_job import PlatformToken, PublishJob, PublishJobStatus, RateLimitTracker
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)


# Retry backoff delays in seconds
RETRY_BACKOFF = [60, 300, 1800, 3600, 86400]  # 1min, 5min, 30min, 1hr, 24hr


class TokenExpiredError(Exception):
    """Token expired and needs re-authentication."""
    pass


class RateLimitError(Exception):
    """Rate limit exceeded."""
    def __init__(self, message: str, retry_after: datetime):
        super().__init__(message)
        self.retry_after = retry_after


class PublishError(Exception):
    """Generic publish error."""
    pass


class PublishUnavailableError(PublishError):
    """Raised when a platform integration is not available."""

    def __init__(self, platform: str, reason: str):
        super().__init__(f"{platform.upper()} publishing unavailable: {reason}")
        self.platform = platform
        self.reason = reason


class ReliablePublisherService:
    """Reliable publishing service with retry and idempotency."""

    def __init__(self, db: Session):
        self.db = db

    async def enqueue_publish(
        self,
        post_id: UUID,
        platform: str,
        scheduled_at: datetime | None = None,
    ) -> PublishJob:
        """
        Add a publish job to the queue.
        
        Args:
            post_id: Post UUID
            platform: Target platform ('gbp', 'instagram', etc.)
            scheduled_at: Optional scheduled time
            
        Returns:
            PublishJob instance
        """
        # Generate idempotency key
        idempotency_key = f"{post_id}:{platform}:{date.today().isoformat()}"

        # Check for existing job with same key
        existing = await self.get_job_by_idempotency_key(idempotency_key)
        if existing:
            logger.info(f"Job already exists: {idempotency_key}")
            return existing

        # Get post for payload snapshot
        post = self.db.get(Post, post_id)
        if not post:
            raise ValueError(f"Post {post_id} not found")

        # Create job
        job = PublishJob(
            post_id=post_id,
            platform=platform,
            idempotency_key=idempotency_key,
            status=PublishJobStatus.PENDING,
            next_run_at=scheduled_at or datetime.now(),
            request_payload=self._build_request_payload(post, platform),
        )

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        logger.info(f"Enqueued publish job: {job.id} for {platform}")
        return job

    async def process_pending_jobs(self, limit: int = 10) -> list[PublishJob]:
        """
        Process pending jobs that are due.
        
        Args:
            limit: Maximum jobs to process
            
        Returns:
            List of processed jobs
        """
        now = datetime.now()

        # Get pending jobs due for processing
        stmt = (
            select(PublishJob)
            .where(
                PublishJob.status == PublishJobStatus.PENDING,
                PublishJob.next_run_at <= now,
            )
            .order_by(PublishJob.next_run_at)
            .limit(limit)
        )
        result = self.db.execute(stmt)
        jobs = list(result.scalars().all())

        processed = []
        for job in jobs:
            try:
                processed_job = await self.process_job(job)
                processed.append(processed_job)
            except Exception as e:
                logger.error(f"Error processing job {job.id}: {e}")

        return processed

    async def process_job(self, job: PublishJob) -> PublishJob:
        """
        Process a single publish job with retry logic.
        
        Args:
            job: PublishJob to process
            
        Returns:
            Updated PublishJob
        """
        job.status = PublishJobStatus.PROCESSING
        job.started_at = datetime.now()
        job.tries += 1

        try:
            # Check rate limit
            if await self.is_rate_limited(job.platform):
                raise RateLimitError(
                    f"Rate limit exceeded for {job.platform}",
                    await self.get_rate_limit_reset(job.platform)
                )

            # Get valid token
            post = self.db.get(Post, job.post_id)
            if not post:
                raise PublishError(f"Post {job.post_id} not found")

            token = await self.get_valid_token(post.location_id, job.platform)
            if not token:
                raise TokenExpiredError(f"No valid token for {job.platform}")

            # Execute publish
            result = await self._execute_publish(job, post, token)

            # Success
            job.status = PublishJobStatus.COMPLETED
            job.platform_post_id = result.get("post_id")
            job.platform_url = result.get("url")
            job.response_payload = result
            job.completed_at = datetime.now()
            job.last_error = None

            # Update rate limit counter
            await self.increment_rate_limit(job.platform)

            logger.info(f"Successfully published job {job.id}")

        except RateLimitError as e:
            job.status = PublishJobStatus.PENDING
            job.next_run_at = e.retry_after
            job.last_error = str(e)
            job.error_code = "RATE_LIMITED"
            logger.warning(f"Rate limited job {job.id}, retry at {e.retry_after}")

        except TokenExpiredError as e:
            job.status = PublishJobStatus.FAILED
            job.last_error = str(e)
            job.error_code = "TOKEN_EXPIRED"
            job.completed_at = datetime.now()
            job.response_payload = {
                "success": False,
                "available": False,
                "platform": job.platform,
                "error": str(e),
                "error_code": "TOKEN_EXPIRED",
            }
            self.db.flush()
            await self._safe_notify(self._notify_reauth_required, job)
            logger.error(f"Token expired for job {job.id}")

        except PublishUnavailableError as e:
            job.status = PublishJobStatus.FAILED
            job.last_error = str(e)
            job.error_code = "UNAVAILABLE"
            job.platform_post_id = None
            job.platform_url = None
            job.response_payload = {
                "success": False,
                "available": False,
                "platform": job.platform,
                "error": str(e),
                "error_code": "UNAVAILABLE",
            }
            job.completed_at = datetime.now()
            self.db.flush()
            await self._safe_notify(self._notify_failure, job)
            logger.warning(f"Job {job.id} unavailable: {e}")

        except Exception as e:
            if job.tries >= job.max_tries:
                job.status = PublishJobStatus.FAILED
                job.last_error = str(e)
                job.error_code = "MAX_RETRIES"
                job.completed_at = datetime.now()
                job.response_payload = {
                    "success": False,
                    "available": False,
                    "platform": job.platform,
                    "error": str(e),
                    "error_code": "MAX_RETRIES",
                }
                self.db.flush()
                await self._safe_notify(self._notify_failure, job)
                logger.error(f"Job {job.id} failed after {job.tries} tries")
            else:
                # Schedule retry with backoff
                delay = self._calculate_retry_delay(job.tries)
                job.status = PublishJobStatus.PENDING
                job.next_run_at = datetime.now() + timedelta(seconds=delay)
                job.last_error = str(e)
                logger.warning(f"Job {job.id} failed, retry in {delay}s: {e}")

        self.db.commit()
        self.db.refresh(job)
        return job

    async def _execute_publish(
        self,
        job: PublishJob,
        post: Post,
        token: PlatformToken,
    ) -> dict[str, Any]:
        """
        Execute the actual publish to platform.
        """
        platform = job.platform.lower()

        if platform == "gbp":
            return await self._publish_to_gbp(post, token)
        elif platform == "instagram":
            return await self._publish_to_instagram(post, token)
        elif platform == "facebook":
            return await self._publish_to_facebook(post, token)
        else:
            raise PublishError(f"Unknown platform: {platform}")

    async def _publish_to_gbp(
        self, post: Post, token: PlatformToken
    ) -> dict[str, Any]:
        """Publish to Google Business Profile."""
        raise PublishUnavailableError("GBP", self._unavailable_reason("gbp", token))

    async def _publish_to_instagram(
        self, post: Post, token: PlatformToken
    ) -> dict[str, Any]:
        """Publish to Instagram."""
        raise PublishUnavailableError("Instagram", self._unavailable_reason("instagram", token))

    async def _publish_to_facebook(
        self, post: Post, token: PlatformToken
    ) -> dict[str, Any]:
        """Publish to Facebook."""
        raise PublishUnavailableError("Facebook", self._unavailable_reason("facebook", token))

    def _build_request_payload(self, post: Post, platform: str) -> dict:
        """Build request payload for audit trail."""
        return {
            "post_id": str(post.id),
            "platform": platform,
            "title": post.title,
            "body": post.body,
            "image_url": post.image_url,
            "created_at": datetime.now().isoformat(),
        }

    def _calculate_retry_delay(self, tries: int) -> int:
        """Calculate retry delay with exponential backoff."""
        index = min(tries - 1, len(RETRY_BACKOFF) - 1)
        return RETRY_BACKOFF[index]

    def _normalize_datetime(self, value: datetime | None) -> datetime | None:
        """Normalize datetimes so SQLite naive timestamps do not crash aware comparisons."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def _is_token_expired(self, token: PlatformToken) -> bool:
        """Check expiration using timezone-safe comparisons."""
        expires_at = self._normalize_datetime(token.expires_at)
        if not expires_at:
            return False
        return datetime.now(timezone.utc) > expires_at

    def _is_token_expiring_soon(self, token: PlatformToken) -> bool:
        """Check whether the token expires within 7 days."""
        expires_at = self._normalize_datetime(token.expires_at)
        if not expires_at:
            return False
        return datetime.now(timezone.utc) + timedelta(days=7) > expires_at

    async def get_job_by_idempotency_key(self, key: str) -> PublishJob | None:
        """Get job by idempotency key."""
        stmt = select(PublishJob).where(PublishJob.idempotency_key == key)
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_valid_token(
        self, location_id: UUID, platform: str
    ) -> PlatformToken | None:
        """Get valid token for platform, refreshing if needed."""
        stmt = select(PlatformToken).where(
            PlatformToken.location_id == location_id,
            PlatformToken.platform == platform.lower(),
        )
        result = self.db.execute(stmt)
        token = result.scalar_one_or_none()

        if not token:
            return None

        # Check if expired
        if self._is_token_expired(token):
            # Try to refresh
            refreshed = await self._refresh_token(token)
            if not refreshed:
                token.status = "reauth_required"
                self.db.commit()
                return None
            return token

        # Check if expiring soon and proactively refresh
        if self._is_token_expiring_soon(token):
            await self._refresh_token(token)

        # Update last used
        token.last_used_at = datetime.now()
        self.db.commit()

        return token

    async def _refresh_token(self, token: PlatformToken) -> bool:
        """Attempt to refresh an OAuth token."""
        if not token.refresh_token:
            return False

        logger.warning(
            "Token refresh for %s is unavailable in ReliablePublisherService; "
            "returning False instead of fabricating refresh success",
            token.platform,
        )
        return False

    async def is_rate_limited(self, platform: str) -> bool:
        """Check if platform is rate limited."""
        tracker = await self._get_rate_tracker(platform)
        if not tracker:
            return False

        # Reset if window expired
        tracker.reset_if_window_expired()
        self.db.commit()

        return tracker.is_limited

    async def get_rate_limit_reset(self, platform: str) -> datetime:
        """Get when rate limit resets."""
        tracker = await self._get_rate_tracker(platform)
        if not tracker or not tracker.window_start:
            return datetime.now() + timedelta(hours=1)

        return tracker.window_start + timedelta(seconds=tracker.window_seconds)

    async def increment_rate_limit(self, platform: str):
        """Increment rate limit counter."""
        tracker = await self._get_rate_tracker(platform)
        if not tracker:
            tracker = RateLimitTracker(
                platform=platform.lower(),
                requests_count=0,
                window_start=datetime.now(),
                window_seconds=3600,
                max_requests=100,
            )
            self.db.add(tracker)

        tracker.reset_if_window_expired()
        tracker.requests_count += 1
        self.db.commit()

    async def _get_rate_tracker(self, platform: str) -> RateLimitTracker | None:
        """Get rate limit tracker for platform."""
        stmt = select(RateLimitTracker).where(
            RateLimitTracker.platform == platform.lower()
        )
        result = self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _notify_failure(self, job: PublishJob):
        """Notify about job failure."""
        post = self.db.get(Post, job.post_id)
        location = self.db.get(Location, post.location_id) if post else None
        account_id = getattr(location, "account_id", None)
        if not account_id or not post or not location:
            logger.error("Publishing failed permanently for job %s", job.id)
            return

        location_name = location.name or "this location"
        error_detail = (job.last_error or "Unknown publish failure").strip()
        await NotificationService(self.db).send_notification(
            account_id=account_id,
            title=f"{job.platform.upper()} publish failed",
            message=(
                f"Publishing for {location_name} could not be completed on {job.platform.upper()}."
                f"\n\nReason: {error_detail}"
            ),
            notification_type="publish_job_failed",
            data={
                "url": f"/dashboard/content/{post.id}",
                "job_id": str(job.id),
                "post_id": str(post.id),
                "location_id": str(location.id),
                "platform": job.platform,
                "error_code": job.error_code,
            },
        )
        logger.error("Publishing failed permanently for job %s", job.id)

    async def _safe_notify(self, notify_func, job: PublishJob) -> None:
        """Keep publish job state durable even if operator notification fails."""
        try:
            await notify_func(job)
        except Exception as exc:
            logger.warning(
                "Publish job %s reached %s but notification failed: %s",
                job.id,
                job.error_code or job.status,
                exc,
            )

    async def _notify_reauth_required(self, job: PublishJob):
        """Notify that re-authentication is required."""
        post = self.db.get(Post, job.post_id)
        location = self.db.get(Location, post.location_id) if post else None
        account_id = getattr(location, "account_id", None)
        if not account_id or not post or not location:
            logger.warning("Re-authentication required for job %s", job.id)
            return

        location_name = location.name or "this location"
        await NotificationService(self.db).send_notification(
            account_id=account_id,
            title=f"Reconnect {job.platform.upper()} publishing",
            message=(
                f"{location_name} can no longer publish to {job.platform.upper()} until the integration is reconnected."
                "\n\nReconnect the channel in Integrations, then retry the failed publish job."
            ),
            notification_type="publish_reauth_required",
            data={
                "url": "/dashboard/integrations",
                "job_id": str(job.id),
                "post_id": str(post.id),
                "location_id": str(location.id),
                "platform": job.platform,
                "error_code": job.error_code,
            },
        )
        logger.warning("Re-authentication required for job %s", job.id)

    def _unavailable_reason(self, platform: str, token: PlatformToken) -> str:
        """Explain why a platform publish cannot run."""
        platform = platform.lower()

        if not getattr(token, "access_token", None):
            return "access token is missing"

        credential_requirements = {
            "gbp": (settings.gbp_client_id, settings.gbp_client_secret),
            "instagram": (settings.instagram_client_id, settings.instagram_client_secret),
            "facebook": (settings.facebook_app_id, settings.facebook_app_secret),
        }
        client_id, client_secret = credential_requirements.get(platform, (None, None))

        if not client_id or not client_secret:
            return f"{platform.upper()} credentials are not configured"

        return "no provider adapter is implemented in ReliablePublisherService"

    async def cancel_job(self, job_id: UUID) -> PublishJob | None:
        """Cancel a pending job."""
        job = self.db.get(PublishJob, job_id)
        if not job:
            return None

        if job.status == PublishJobStatus.PENDING:
            job.status = PublishJobStatus.CANCELLED
            self.db.commit()
            self.db.refresh(job)

        return job

    async def retry_failed_job(self, job_id: UUID) -> PublishJob | None:
        """Manually retry a failed job."""
        job = self.db.get(PublishJob, job_id)
        if not job:
            return None

        if job.status == PublishJobStatus.FAILED:
            job.status = PublishJobStatus.PENDING
            job.tries = 0
            job.next_run_at = datetime.now()
            job.last_error = None
            job.error_code = None
            self.db.commit()
            self.db.refresh(job)

        return job

    async def get_job_stats(self, location_id: UUID) -> dict[str, int]:
        """Get job statistics for a location."""
        post_ids = list(
            self.db.execute(select(Post.id).where(Post.location_id == location_id))
            .scalars()
            .all()
        )

        if not post_ids:
            return {
                "pending": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0,
            }

        stmt = (
            select(PublishJob.status)
            .where(PublishJob.post_id.in_(post_ids))
        )
        result = self.db.execute(stmt)
        statuses = [
            str(getattr(status, "value", status)).lower()
            for status in result.scalars().all()
        ]

        return {
            "pending": statuses.count(PublishJobStatus.PENDING.value),
            "processing": statuses.count(PublishJobStatus.PROCESSING.value),
            "completed": statuses.count(PublishJobStatus.COMPLETED.value),
            "failed": statuses.count(PublishJobStatus.FAILED.value),
        }
