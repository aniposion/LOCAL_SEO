"""Add Q&A draft storage table.

Revision ID: 20260306_qa_drafts
Revises: 20260306_website_seo_drafts
Create Date: 2026-03-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260306_qa_drafts"
down_revision = "20260306_website_seo_drafts"
branch_labels = None
depends_on = None


qa_draft_status = sa.Enum("pending", "draft", "posted", "failed", name="qadraftstatus")


def upgrade() -> None:
    bind = op.get_bind()
    qa_draft_status.create(bind, checkfirst=True)

    op.create_table(
        "qa_drafts",
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.String(length=255), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("author_name", sa.String(length=255), nullable=True),
        sa.Column("draft_status", qa_draft_status, nullable=False),
        sa.Column("suggested_answer", sa.Text(), nullable=True),
        sa.Column("posted_answer", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("question_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("location_id", "question_id", name="uq_qa_drafts_location_question"),
    )
    op.create_index("ix_qa_drafts_location_id", "qa_drafts", ["location_id"])
    op.create_index("ix_qa_drafts_question_id", "qa_drafts", ["question_id"])


def downgrade() -> None:
    op.drop_index("ix_qa_drafts_question_id", table_name="qa_drafts")
    op.drop_index("ix_qa_drafts_location_id", table_name="qa_drafts")
    op.drop_table("qa_drafts")
    qa_draft_status.drop(op.get_bind(), checkfirst=True)
