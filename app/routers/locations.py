"""Locations router."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account
from app.models.channel import Channel, ChannelType
from app.models.location import Location
from app.routers.deps import get_current_user
from app.schemas.channel import ChannelCreate, ChannelResponse
from app.schemas.location import (
    LocationCreate,
    LocationHealth,
    LocationResponse,
    LocationUpdate,
)

router = APIRouter(prefix="/locations", tags=["locations"])


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
    return (
        db.query(Location)
        .filter(Location.account_id == current_user.id)
        .order_by(Location.created_at.desc())
        .all()
    )


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
    return location


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
) -> list[Channel]:
    """List all channels for a location."""
    location = (
        db.query(Location)
        .filter(Location.id == location_id, Location.account_id == current_user.id)
        .first()
    )
    if not location:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    return db.query(Channel).filter(Channel.location_id == location_id).all()


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
            health.gbp_connected = channel.is_active and channel.credentials is not None
            health.gbp_status = channel.error_message or ("connected" if health.gbp_connected else "not configured")
        elif channel.type == ChannelType.INSTAGRAM:
            health.instagram_connected = channel.is_active and channel.credentials is not None
            health.instagram_status = channel.error_message or ("connected" if health.instagram_connected else "not configured")
        elif channel.type == ChannelType.WEBSITE:
            health.website_connected = channel.is_active and channel.credentials is not None
            health.website_status = channel.error_message or ("connected" if health.website_connected else "not configured")

    return health
