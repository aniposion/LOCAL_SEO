"""Posts router."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account
from app.models.location import Location
from app.models.post import Platform, Post, PostStatus
from app.routers.deps import get_current_user
from app.schemas.post import PostCreate, PostResponse, PostUpdate
from app.services.publisher import PublisherService

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(
    request: PostCreate,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> Post:
    """Create a new post."""
    # Verify location ownership
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
    return post


@router.get("", response_model=list[PostResponse])
def list_posts(
    location_id: UUID | None = Query(None),
    platform: Platform | None = Query(None),
    post_status: PostStatus | None = Query(None, alias="status"),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> list[Post]:
    """List posts with optional filters."""
    # Get user's location IDs
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

    return query.order_by(Post.created_at.desc()).offset(offset).limit(limit).all()


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

    # Verify ownership
    location = db.query(Location).filter(Location.id == post.location_id).first()
    if not location or location.account_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    return post


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

    # Verify ownership
    location = db.query(Location).filter(Location.id == post.location_id).first()
    if not location or location.account_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(post, field, value)

    db.commit()
    db.refresh(post)
    return post


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

    # Verify ownership
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

    # Verify ownership
    location = db.query(Location).filter(Location.id == post.location_id).first()
    if not location or location.account_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if post.status == PostStatus.POSTED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Post already published")

    # Publish using publisher service
    publisher = PublisherService(db)
    try:
        await publisher.publish_post(post)
        db.refresh(post)
    except Exception as e:
        post.status = PostStatus.FAILED
        post.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return post
