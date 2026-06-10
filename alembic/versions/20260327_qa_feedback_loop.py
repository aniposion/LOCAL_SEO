"""add qa draft feedback loop fields

Revision ID: 20260327_qa_feedback
Revises: 20260327_social_alert_settings
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260327_qa_feedback"
down_revision = "20260327_social_alert_settings"
branch_labels = None
depends_on = None


qa_feedback_rating = sa.Enum("GOOD", "NEEDS_EDIT", "WRONG", name="qafeedbackrating")


def upgrade() -> None:
    bind = op.get_bind()
    qa_feedback_rating.create(bind, checkfirst=True)
    op.add_column("qa_drafts", sa.Column("feedback_rating", qa_feedback_rating, nullable=True))
    op.add_column("qa_drafts", sa.Column("feedback_notes", sa.Text(), nullable=True))
    op.add_column("qa_drafts", sa.Column("feedback_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("qa_drafts", "feedback_at")
    op.drop_column("qa_drafts", "feedback_notes")
    op.drop_column("qa_drafts", "feedback_rating")
    bind = op.get_bind()
    qa_feedback_rating.drop(bind, checkfirst=True)
