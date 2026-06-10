"""Website board API."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.account import Account
from app.models.board import BoardPost
from app.models.location import Location
from app.models.upload import UploadAsset
from app.routers.deps import get_current_user

router = APIRouter(prefix="/board", tags=["board"])

BoardStatus = Literal["draft", "published", "archived"]


class BoardPostCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=160)
    body: str = Field(..., min_length=1, max_length=5000)
    location_id: UUID | None = None
    image_asset_id: UUID | None = None
    status: BoardStatus = "published"
    is_pinned: bool = False


class BoardPostUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=160)
    body: str | None = Field(None, min_length=1, max_length=5000)
    location_id: UUID | None = None
    image_asset_id: UUID | None = None
    status: BoardStatus | None = None
    is_pinned: bool | None = None


class BoardPostResponse(BaseModel):
    id: str
    title: str
    body: str
    location_id: str | None
    location_name: str | None
    image_asset_id: str | None
    image_url: str | None
    status: str
    is_pinned: bool
    created_at: datetime
    updated_at: datetime


class BoardPostListResponse(BaseModel):
    posts: list[BoardPostResponse]
    total: int


class PublicBoardLocationResponse(BaseModel):
    id: str
    name: str
    address: str | None
    city: str | None
    state: str | None
    phone: str | None
    website_url: str | None


class PublicBoardResponse(BaseModel):
    location: PublicBoardLocationResponse
    posts: list[BoardPostResponse]


def _serialize(post: BoardPost) -> BoardPostResponse:
    return BoardPostResponse(
        id=str(post.id),
        title=post.title,
        body=post.body,
        location_id=str(post.location_id) if post.location_id else None,
        location_name=post.location.name if post.location else None,
        image_asset_id=str(post.image_asset_id) if post.image_asset_id else None,
        image_url=post.image_url,
        status=post.status,
        is_pinned=post.is_pinned,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


def _serialize_public_location(location: Location) -> PublicBoardLocationResponse:
    return PublicBoardLocationResponse(
        id=str(location.id),
        name=location.name,
        address=location.address,
        city=location.city,
        state=location.state,
        phone=location.phone,
        website_url=location.website_url,
    )


def _require_owned_location(db: Session, account: Account, location_id: UUID | None) -> Location | None:
    if not location_id:
        return None

    location = db.query(Location).filter(Location.id == location_id, Location.account_id == account.id).first()
    if location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return location


def _require_owned_image(db: Session, account: Account, image_asset_id: UUID | None) -> UploadAsset | None:
    if not image_asset_id:
        return None

    asset = (
        db.query(UploadAsset)
        .filter(
            UploadAsset.id == image_asset_id,
            UploadAsset.account_id == account.id,
            UploadAsset.file_type == "image",
        )
        .first()
    )
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image upload not found")
    return asset


@router.get("/public/{location_id}", response_model=PublicBoardResponse)
def get_public_board(
    location_id: UUID,
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PublicBoardResponse:
    location = db.query(Location).filter(Location.id == location_id).first()
    if location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    posts = (
        db.query(BoardPost)
        .filter(
            BoardPost.account_id == location.account_id,
            BoardPost.status == "published",
            or_(BoardPost.location_id == location.id, BoardPost.location_id.is_(None)),
        )
        .order_by(desc(BoardPost.is_pinned), desc(BoardPost.created_at))
        .limit(limit)
        .all()
    )
    return PublicBoardResponse(location=_serialize_public_location(location), posts=[_serialize(post) for post in posts])


@router.get("", response_model=BoardPostListResponse)
def list_board_posts(
    status_filter: BoardStatus | Literal["all"] = Query("all", alias="status"),
    location_id: UUID | None = None,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> BoardPostListResponse:
    query = db.query(BoardPost).filter(BoardPost.account_id == current_user.id)
    if status_filter != "all":
        query = query.filter(BoardPost.status == status_filter)
    if location_id:
        _require_owned_location(db, current_user, location_id)
        query = query.filter(BoardPost.location_id == location_id)

    total = query.count()
    posts = (
        query.order_by(desc(BoardPost.is_pinned), desc(BoardPost.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return BoardPostListResponse(posts=[_serialize(post) for post in posts], total=total)


@router.post("", response_model=BoardPostResponse, status_code=status.HTTP_201_CREATED)
def create_board_post(
    payload: BoardPostCreate,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> BoardPostResponse:
    _require_owned_location(db, current_user, payload.location_id)
    image_asset = _require_owned_image(db, current_user, payload.image_asset_id)

    post = BoardPost(
        account_id=current_user.id,
        location_id=payload.location_id,
        image_asset_id=payload.image_asset_id,
        image_url=image_asset.url if image_asset else None,
        title=payload.title.strip(),
        body=payload.body.strip(),
        status=payload.status,
        is_pinned=payload.is_pinned,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return _serialize(post)


@router.patch("/{post_id}", response_model=BoardPostResponse)
def update_board_post(
    post_id: UUID,
    payload: BoardPostUpdate,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> BoardPostResponse:
    post = db.query(BoardPost).filter(BoardPost.id == post_id, BoardPost.account_id == current_user.id).first()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board post not found")

    if payload.location_id is not None:
        _require_owned_location(db, current_user, payload.location_id)
        post.location_id = payload.location_id
    if payload.image_asset_id is not None:
        image_asset = _require_owned_image(db, current_user, payload.image_asset_id)
        post.image_asset_id = payload.image_asset_id
        post.image_url = image_asset.url if image_asset else None
    if payload.title is not None:
        post.title = payload.title.strip()
    if payload.body is not None:
        post.body = payload.body.strip()
    if payload.status is not None:
        post.status = payload.status
    if payload.is_pinned is not None:
        post.is_pinned = payload.is_pinned

    db.commit()
    db.refresh(post)
    return _serialize(post)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board_post(
    post_id: UUID,
    db: Session = Depends(get_db),
    current_user: Account = Depends(get_current_user),
) -> None:
    post = db.query(BoardPost).filter(BoardPost.id == post_id, BoardPost.account_id == current_user.id).first()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board post not found")

    db.delete(post)
    db.commit()
