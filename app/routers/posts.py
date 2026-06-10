"""Posts router."""

import csv
import io
import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account
from app.models.location import Location
from app.models.post import Platform, Post, PostStatus
from app.models.publish_job import PublishJob, PublishJobStatus
from app.routers.deps import get_current_user
from app.schemas.post import (
    PostCreate,
    PublishIssueItem,
    PublishIssueSummaryResponse,
    PostResponse,
    PostUpdate,
    PublishJobListResponse,
    PublishJobResponse,
)
from app.services.feature_access import FeatureAccessService
from app.services.notification import NotificationChannel, NotificationService
from app.services.publisher import PublisherService

router = APIRouter(prefix="/posts", tags=["posts"])


def _required_publish_feature(platform: Platform) -> str:
    if platform == Platform.INSTAGRAM:
        return "instagram_upload"
    if platform == Platform.WEBSITE:
        return "website_seo_basic"
    return "google_posts"


class RequestApprovalPayload(BaseModel):
    """Optional overrides for approval request notifications."""

    notification_channel: str | None = Field(default=None)
    phone_number: str | None = Field(default=None)


def _with_publish_job(post: Post, db: Session) -> Post:
    latest_publish_job = (
        db.query(PublishJob)
        .filter(PublishJob.post_id == post.id)
        .order_by(PublishJob.created_at.desc())
        .first()
    )
    post.latest_publish_job = latest_publish_job
    return post


def _build_publish_job_query(
    db: Session,
    post_id: UUID,
    job_status: PublishJobStatus | None = None,
    search: str | None = None,
):
    """Build a publish job query with optional operational filters."""
    query = db.query(PublishJob).filter(PublishJob.post_id == post_id)

    if job_status:
        query = query.filter(PublishJob.status == job_status)

    if search:
        like_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                PublishJob.platform.ilike(like_term),
                PublishJob.last_error.ilike(like_term),
                PublishJob.error_code.ilike(like_term),
                PublishJob.platform_post_id.ilike(like_term),
            )
        )

    return query


def _collect_publish_issue_rows(
    db: Session,
    *,
    account_id: UUID,
    location_id: UUID | None = None,
    platform: Platform | None = None,
    search: str | None = None,
):
    """Collect latest actionable publish issues for one account."""
    locations = (
        db.query(Location)
        .filter(Location.account_id == account_id)
        .all()
    )
    if location_id:
        locations = [location for location in locations if str(location.id) == str(location_id)]

    location_map = {str(location.id): location for location in locations}
    if not location_map:
        return []

    posts = db.query(Post).order_by(Post.created_at.desc()).all()
    filtered_posts = [
        post
        for post in posts
        if str(post.location_id) in location_map and (platform is None or post.platform == platform)
    ]
    if not filtered_posts:
        return []

    post_map = {str(post.id): post for post in filtered_posts}
    post_id_set = set(post_map.keys())
    jobs = (
        db.query(PublishJob)
        .order_by(PublishJob.post_id, PublishJob.created_at.desc(), PublishJob.updated_at.desc())
        .all()
    )
    latest_jobs_by_post: dict[str, PublishJob] = {}
    for job in jobs:
        post_key = str(job.post_id)
        if post_key not in post_id_set:
            continue
        latest_jobs_by_post.setdefault(post_key, job)

    normalized_search = search.strip().lower() if search else None
    items: list[tuple[PublishJob, Post, Location]] = []
    for post in filtered_posts:
        latest_job = latest_jobs_by_post.get(str(post.id))
        if not latest_job:
            continue
        location = location_map.get(str(post.location_id))
        if not location:
            continue

        actionable = (
            latest_job.status == PublishJobStatus.FAILED
            or (
                latest_job.status == PublishJobStatus.PENDING
                and latest_job.tries > 0
                and bool(latest_job.last_error or latest_job.error_code)
            )
        )
        if not actionable:
            continue

        if normalized_search:
            haystack = " ".join(
                value
                for value in [
                    location.name,
                    post.title or "",
                    latest_job.last_error or "",
                    latest_job.error_code or "",
                    latest_job.platform,
                ]
                if value
            ).lower()
            if normalized_search not in haystack:
                continue

        items.append((latest_job, post, location))

    items.sort(key=lambda row: row[0].created_at, reverse=True)
    return items


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    request: PostCreate,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> Post:
    """Create a new post."""
    location = (
        db.query(Location)
        .filter(Location.id == request.location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    post = Post(**request.model_dump())
    db.add(post)
    db.commit()
    db.refresh(post)
    return _with_publish_job(post, db)


@router.get("/publish-issues", response_model=PublishIssueSummaryResponse)
def list_publish_issues(
    location_id: UUID | None = Query(None),
    platform: Platform | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """Return latest actionable publish issues across the current account."""
    if location_id:
        location = (
            db.query(Location)
            .filter(Location.id == location_id, Location.account_id == current_user.id)
            .first()
        )
        if not location:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    rows = _collect_publish_issue_rows(
        db,
        account_id=current_user.id,
        location_id=location_id,
        platform=platform,
        search=search,
    )

    items = [
        PublishIssueItem(
            job_id=job.id,
            post_id=post.id,
            location_id=location.id,
            location_name=location.name,
            title=post.title,
            platform=job.platform,
            job_status=job.status,
            post_status=post.status,
            tries=job.tries,
            max_tries=job.max_tries,
            can_retry=job.can_retry,
            last_error=job.last_error,
            error_code=job.error_code,
            created_at=job.created_at,
            next_run_at=job.next_run_at,
            completed_at=job.completed_at,
        )
        for job, post, location in rows[:limit]
    ]

    failed = sum(1 for job, _, _ in rows if job.status == PublishJobStatus.FAILED)
    retrying = sum(
        1
        for job, _, _ in rows
        if job.status == PublishJobStatus.PENDING and job.tries > 0
    )

    return {
        "items": items,
        "total": len(rows),
        "failed": failed,
        "retrying": retrying,
        "limit": limit,
    }


@router.get("", response_model=list[PostResponse])
def list_posts(
    location_id: UUID | None = Query(None),
    platform: Platform | None = Query(None),
    post_status: PostStatus | None = Query(None, alias="status"),
    search: str | None = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> list[Post]:
    """List posts with optional filters."""
    user_location_ids = [
        loc.id for loc in db.query(Location).filter(Location.account_id == current_user.id).all()
    ]

    query = db.query(Post).filter(Post.location_id.in_(user_location_ids))

    if location_id:
        if location_id not in user_location_ids:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
        query = query.filter(Post.location_id == location_id)

    if platform:
        query = query.filter(Post.platform == platform)

    if post_status:
        query = query.filter(Post.status == post_status)

    if search:
        like_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Post.title.ilike(like_term),
                Post.body.ilike(like_term),
                Post.error_message.ilike(like_term),
            )
        )

    posts = query.order_by(Post.created_at.desc()).offset(offset).limit(limit).all()
    return [_with_publish_job(post, db) for post in posts]


@router.get("/{post_id}", response_model=PostResponse)
def get_post(
    post_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> Post:
    """Get a specific post."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    location = db.query(Location).filter(Location.id == post.location_id).first()
    if not location or location.account_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    return _with_publish_job(post, db)


@router.get("/{post_id}/publish-jobs", response_model=PublishJobListResponse)
def list_publish_jobs(
    post_id: UUID,
    job_status: PublishJobStatus | None = Query(None, alias="status"),
    search: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> dict:
    """List publish job history for a post."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    location = db.query(Location).filter(Location.id == post.location_id).first()
    if not location or location.account_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    query = _build_publish_job_query(db, post.id, job_status=job_status, search=search)
    total = query.count()
    items = query.order_by(PublishJob.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{post_id}/publish-jobs/export")
def export_publish_jobs(
    post_id: UUID,
    job_status: PublishJobStatus | None = Query(None, alias="status"),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
):
    """Export publish job history for a post as CSV."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    location = db.query(Location).filter(Location.id == post.location_id).first()
    if not location or location.account_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    items = (
        _build_publish_job_query(db, post.id, job_status=job_status, search=search)
        .order_by(PublishJob.created_at.desc())
        .all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "created_at",
            "status",
            "platform",
            "tries",
            "max_tries",
            "error_code",
            "last_error",
            "platform_post_id",
            "started_at",
            "completed_at",
            "next_run_at",
        ]
    )
    for item in items:
        writer.writerow(
            [
                item.created_at.isoformat() if item.created_at else "",
                item.status.value,
                item.platform,
                item.tries,
                item.max_tries,
                item.error_code or "",
                item.last_error or "",
                item.platform_post_id or "",
                item.started_at.isoformat() if item.started_at else "",
                item.completed_at.isoformat() if item.completed_at else "",
                item.next_run_at.isoformat() if item.next_run_at else "",
            ]
        )

    filename = f"publish-jobs-{post.id}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/{post_id}", response_model=PostResponse)
def update_post(
    post_id: UUID,
    request: PostUpdate,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> Post:
    """Update a post."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    location = db.query(Location).filter(Location.id == post.location_id).first()
    if not location or location.account_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(post, field, value)

    db.commit()
    db.refresh(post)
    return _with_publish_job(post, db)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> None:
    """Delete a post."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    location = db.query(Location).filter(Location.id == post.location_id).first()
    if not location or location.account_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    db.delete(post)
    db.commit()


@router.post("/{post_id}/publish", response_model=PostResponse)
async def publish_post(
    post_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> Post:
    """Immediately publish a post to its platform."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    location = db.query(Location).filter(Location.id == post.location_id).first()
    if not location or location.account_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if post.status == PostStatus.POSTED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Post already published")

    FeatureAccessService(db).check_feature_access(current_user, _required_publish_feature(post.platform))

    publisher = PublisherService(db)
    try:
        await publisher.publish_post(post)
        db.refresh(post)
    except Exception as e:
        post.status = PostStatus.FAILED
        post.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return _with_publish_job(post, db)


@router.post("/{post_id}/retry-publish", response_model=PostResponse)
async def retry_publish_post(
    post_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> Post:
    """Retry publishing a failed, approved, or queued post."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    location = db.query(Location).filter(Location.id == post.location_id).first()
    if not location or location.account_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if post.status not in {PostStatus.FAILED, PostStatus.APPROVED, PostStatus.QUEUED}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed, approved, or queued posts can be retried",
        )

    FeatureAccessService(db).check_feature_access(current_user, _required_publish_feature(post.platform))

    publisher = PublisherService(db)
    try:
        await publisher.publish_post(post)
        db.refresh(post)
    except Exception as e:
        post.status = PostStatus.FAILED
        post.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return _with_publish_job(post, db)


@router.post("/{post_id}/request-approval", response_model=PostResponse)
async def request_post_approval(
    post_id: UUID,
    payload: RequestApprovalPayload,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> Post:
    """Move a draft/rejected post into the approval queue and send notification."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    location = db.query(Location).filter(Location.id == post.location_id).first()
    if not location or location.account_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if post.status not in {PostStatus.DRAFT, PostStatus.REJECTED}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft or rejected posts can be submitted for approval",
        )

    post.status = PostStatus.PENDING_APPROVAL
    post.approval_token = secrets.token_urlsafe(32)
    post.approval_requested_at = datetime.now(timezone.utc)
    post.rejected_at = None
    post.rejection_reason = None
    post.approved_at = None
    post.approved_by_id = None
    post.error_message = None

    requested_channel = (payload.notification_channel or current_user.notification_channel or "email").lower()
    try:
        channel = NotificationChannel(requested_channel)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="notification_channel must be one of: kakao, slack, email, sms",
        )

    if payload.phone_number:
        current_user.phone = payload.phone_number

    if channel == NotificationChannel.SMS:
        FeatureAccessService(db).check_feature_access(current_user, "missed_call_text_back")

    db.commit()
    db.refresh(post)

    notification_service = NotificationService(db)
    notification_sent = await notification_service.send_approval_request(
        post=post,
        account=current_user,
        channel=channel,
    )

    if not notification_sent:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Post moved to approval queue, but notification delivery failed",
        )

    db.refresh(post)
    return _with_publish_job(post, db)
