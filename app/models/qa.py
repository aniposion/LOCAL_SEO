"""Models for Google Business Profile Q&A drafts and answer history."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.location import Location


class QADraftStatus(str, enum.Enum):
    """Lifecycle status for a Q&A answer draft."""

    PENDING = "pending"
    DRAFT = "draft"
    POSTED = "posted"
    FAILED = "failed"


class QAFeedbackRating(str, enum.Enum):
    """Operator feedback on draft quality."""

    GOOD = "good"
    NEEDS_EDIT = "needs_edit"
    WRONG = "wrong"


class QADraft(BaseModel):
    """Stored Q&A question and answer draft state."""

    __tablename__ = "qa_drafts"
    __table_args__ = (UniqueConstraint("location_id", "question_id", name="uq_qa_drafts_location_question"),)

    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    question_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    draft_status: Mapped[QADraftStatus] = mapped_column(
        Enum(QADraftStatus),
        nullable=False,
        default=QADraftStatus.PENDING,
    )
    suggested_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_rating: Mapped[QAFeedbackRating | None] = mapped_column(Enum(QAFeedbackRating), nullable=True)
    feedback_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    question_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    location: Mapped["Location"] = relationship("Location", back_populates="qa_drafts")
