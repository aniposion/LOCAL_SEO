"""Website board posts."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel, UUID

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.location import Location
    from app.models.upload import UploadAsset


class BoardPost(BaseModel):
    """Account-owned website board post with an optional uploaded image."""

    __tablename__ = "board_posts"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(),
        ForeignKey("locations.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    image_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(),
        ForeignKey("upload_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text(), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="published", index=True, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean(), default=False, nullable=False)

    account: Mapped["Account"] = relationship("Account", backref="board_posts")
    location: Mapped["Location | None"] = relationship("Location")
    image_asset: Mapped["UploadAsset | None"] = relationship("UploadAsset")

    def __repr__(self) -> str:
        return f"<BoardPost {self.title}>"
