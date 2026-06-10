"""Locations router."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account
from app.models.channel import Channel, ChannelStatus, ChannelType
from app.models.location import Location
from app.models.post import Post
from app.models.publish_job import PublishJob, PublishJobStatus
from app.models.qa import QADraft, QADraftStatus, QAFeedbackRating
from app.routers.deps import get_current_user
from app.schemas.channel import ChannelCreate, ChannelResponse
from app.schemas.location import (
    LocationCreate,
    LocationHealth,
    LocationResponse,
    LocationUpdate,
)

router = APIRouter(prefix="/locations", tags=["locations"])


def _credentials_present(channel: Channel) -> bool:
    credentials = channel.get_credentials() if channel.credentials_encrypted else {}
    return bool(credentials)


def _apply_channel_health(location: Location, channels: list[Channel]) -> Location:
    location.gbp_connected = False
    location.gbp_status = "not configured"
    location.instagram_connected = False
    location.instagram_status = "not configured"
    location.website_connected = False
    location.website_status = "not configured"

    for channel in channels:
        is_connected = channel.is_active and _credentials_present(channel)
        status_value = channel.status.value if isinstance(channel.status, ChannelStatus) else str(channel.status)
        status_message = channel.error_message or status_value

        if channel.type == ChannelType.GBP:
            location.gbp_connected = is_connected
            location.gbp_status = status_message
        elif channel.type == ChannelType.INSTAGRAM:
            location.instagram_connected = is_connected and not channel.is_token_expired
            if channel.is_token_expired:
                location.instagram_status = "reconnect required"
            elif channel.needs_refresh:
                location.instagram_status = "token refresh needed"
            else:
                location.instagram_status = status_message
        elif channel.type == ChannelType.WEBSITE:
            location.website_connected = is_connected
            location.website_status = status_message

    return location


def _to_channel_response(channel: Channel, db: Session) -> ChannelResponse:
    platform_value = channel.type.value if isinstance(channel.type, ChannelType) else str(channel.type)

    latest_failed_job = None
    latest_success_job = None
    if platform_value:
        post_ids = [
            post_id
            for (post_id,) in db.query(Post.id).filter(Post.location_id == channel.location_id).all()
        ]
        recent_jobs = (
            db.query(PublishJob)
            .filter(PublishJob.post_id.in_(post_ids), PublishJob.platform == platform_value)
            .order_by(PublishJob.created_at.desc())
            .limit(20)
            .all()
        ) if post_ids else []
        latest_failed_job = next(
            (job for job in recent_jobs if job.status == PublishJobStatus.FAILED),
            None,
        )
        latest_success_job = next(
            (job for job in recent_jobs if job.status == PublishJobStatus.COMPLETED),
            None,
        )

    reconnect_required = channel.is_token_expired
    recent_publish_failures = sum(1 for job in recent_jobs if job.status == PublishJobStatus.FAILED)
    recent_publish_successes = sum(
        1 for job in recent_jobs if job.status == PublishJobStatus.COMPLETED
    )
    last_publish_failed_at = latest_failed_job.created_at if latest_failed_job else None
    last_publish_failed_error = latest_failed_job.last_error if latest_failed_job else None
    last_publish_succeeded_at = (
        (latest_success_job.completed_at or latest_success_job.created_at)
        if latest_success_job
        else None
    )
    meta = channel.meta or {}
    if not last_publish_failed_at and meta.get("last_publish_failed_at"):
        last_publish_failed_at = meta.get("last_publish_failed_at")
    if not last_publish_failed_error and meta.get("last_publish_failed_error"):
        last_publish_failed_error = meta.get("last_publish_failed_error")
    if not last_publish_succeeded_at and meta.get("last_publish_succeeded_at"):
        last_publish_succeeded_at = meta.get("last_publish_succeeded_at")

    qa_pending_count = 0
    qa_failed_count = 0
    qa_posted_count = 0
    qa_last_failed_at = None
    qa_last_posted_at = None
    qa_feedback_good_count = 0
    qa_feedback_needs_edit_count = 0
    qa_feedback_wrong_count = 0
    if channel.type == ChannelType.GBP:
        qa_drafts = (
            db.query(QADraft)
            .filter(QADraft.location_id == channel.location_id)
            .order_by(QADraft.updated_at.desc())
            .all()
        )
        qa_pending_count = sum(1 for draft in qa_drafts if draft.draft_status in {QADraftStatus.PENDING, QADraftStatus.DRAFT})
        qa_failed_count = sum(1 for draft in qa_drafts if draft.draft_status == QADraftStatus.FAILED)
        qa_posted_count = sum(1 for draft in qa_drafts if draft.draft_status == QADraftStatus.POSTED)
        qa_last_failed = next((draft for draft in qa_drafts if draft.draft_status == QADraftStatus.FAILED), None)
        qa_last_posted = next((draft for draft in qa_drafts if draft.draft_status == QADraftStatus.POSTED), None)
        qa_feedback_good_count = sum(
            1 for draft in qa_drafts if draft.feedback_rating == QAFeedbackRating.GOOD
        )
        qa_feedback_needs_edit_count = sum(
            1 for draft in qa_drafts if draft.feedback_rating == QAFeedbackRating.NEEDS_EDIT
        )
        qa_feedback_wrong_count = sum(
            1 for draft in qa_drafts if draft.feedback_rating == QAFeedbackRating.WRONG
        )
        qa_last_failed_at = qa_last_failed.updated_at if qa_last_failed else None
        qa_last_posted_at = (qa_last_posted.answered_at or qa_last_posted.updated_at) if qa_last_posted else None
        qa_last_sync_at = channel.last_sync_at
        qa_last_sync_error = meta.get("qa_last_sync_error")
        qa_last_sync_question_count = meta.get("qa_last_sync_question_count") or 0
    else:
        qa_last_sync_at = None
        qa_last_sync_error = None
        qa_last_sync_question_count = 0

    return ChannelResponse(
        id=channel.id,
        location_id=channel.location_id,
        type=channel.type,
        is_active=channel.is_active,
        meta=channel.meta,
        status=channel.status.value if isinstance(channel.status, ChannelStatus) else str(channel.status),
        platform_account_id=channel.platform_account_id,
        platform_account_name=channel.platform_account_name,
        access_token_expires_at=channel.access_token_expires_at,
        refresh_token_expires_at=channel.refresh_token_expires_at,
        is_token_expired=channel.is_token_expired,
        needs_refresh=channel.needs_refresh,
        reconnect_required=reconnect_required,
        last_sync_at=channel.last_sync_at,
        error_message=channel.error_message,
        error_count=channel.error_count,
        last_publish_failed_at=last_publish_failed_at,
        last_publish_failed_error=last_publish_failed_error,
        last_publish_succeeded_at=last_publish_succeeded_at,
        recent_publish_failures=recent_publish_failures,
        recent_publish_successes=recent_publish_successes,
        qa_pending_count=qa_pending_count,
        qa_failed_count=qa_failed_count,
        qa_posted_count=qa_posted_count,
        qa_last_failed_at=qa_last_failed_at,
        qa_last_posted_at=qa_last_posted_at,
        qa_last_sync_at=qa_last_sync_at,
        qa_last_sync_error=qa_last_sync_error,
        qa_last_sync_question_count=qa_last_sync_question_count,
        qa_feedback_good_count=qa_feedback_good_count,
        qa_feedback_needs_edit_count=qa_feedback_needs_edit_count,
        qa_feedback_wrong_count=qa_feedback_wrong_count,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )


@router.post("", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
def create_location(
    request: LocationCreate,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> Location:
    """Create a new business location."""
    location = Location(
        account_id=current_user.id,
        **request.model_dump(),
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.get("", response_model=list[LocationResponse])
def list_locations(
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> list[Location]:
    """List all locations for current user."""
    locations = (
        db.query(Location)
        .filter(Location.account_id == current_user.id)
        .order_by(Location.created_at.desc())
        .all()
    )
    location_ids = [location.id for location in locations]
    channels = (
        db.query(Channel).filter(Channel.location_id.in_(location_ids)).all() if location_ids else []
    )
    channels_by_location: dict[UUID, list[Channel]] = {}
    for channel in channels:
        channels_by_location.setdefault(channel.location_id, []).append(channel)

    return [
        _apply_channel_health(location, channels_by_location.get(location.id, []))
        for location in locations
    ]


@router.get("/{location_id}", response_model=LocationResponse)
def get_location(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> Location:
    """Get a specific location."""
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    channels = db.query(Channel).filter(Channel.location_id == location.id).all()
    return _apply_channel_health(location, channels)


@router.patch("/{location_id}", response_model=LocationResponse)
def update_location(
    location_id: UUID,
    request: LocationUpdate,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> Location:
    """Update a location."""
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(location, field, value)

    db.commit()
    db.refresh(location)
    return location


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_location(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> None:
    """Delete a location."""
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    db.delete(location)
    db.commit()


@router.post("/{location_id}/channels", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
def create_channel(
    location_id: UUID,
    request: ChannelCreate,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> Channel:
    """Add a channel to a location."""
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    # Check if channel type already exists
    existing = (
        db.query(Channel)
        .filter(Channel.location_id == location_id, Channel.type == request.type)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Channel {request.type.value} already exists for this location",
        )

    channel = Channel(
        location_id=location_id,
        **request.model_dump(),
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


@router.get("/{location_id}/channels", response_model=list[ChannelResponse])
def list_channels(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> list[ChannelResponse]:
    """List all channels for a location."""
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    channels = db.query(Channel).filter(Channel.location_id == location_id).all()
    return [_to_channel_response(channel, db) for channel in channels]


@router.get("/{location_id}/health", response_model=LocationHealth)
def check_location_health(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> LocationHealth:
    """Check connection health for all channels."""
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    channels = db.query(Channel).filter(Channel.location_id == location_id).all()

    health = LocationHealth(location_id=location_id)

    for channel in channels:
        if channel.type == ChannelType.GBP:
            health.gbp_connected = channel.is_active and _credentials_present(channel)
            health.gbp_status = channel.error_message or ("connected" if health.gbp_connected else "not configured")
        elif channel.type == ChannelType.INSTAGRAM:
            health.instagram_connected = channel.is_active and _credentials_present(channel) and not channel.is_token_expired
            if channel.is_token_expired:
                health.instagram_status = "reconnect required"
            elif channel.needs_refresh:
                health.instagram_status = "token refresh needed"
            else:
                health.instagram_status = channel.error_message or ("connected" if health.instagram_connected else "not configured")
        elif channel.type == ChannelType.WEBSITE:
            health.website_connected = channel.is_active and _credentials_present(channel)
            health.website_status = channel.error_message or ("connected" if health.website_connected else "not configured")

    return health
