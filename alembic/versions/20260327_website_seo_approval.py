"""Add Website SEO approval workflow columns.

Revision ID: 20260327_website_seo_approval
Revises: 20260306_website_seo_drafts
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260327_website_seo_approval"
down_revision = "20260306_website_seo_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "website_seo_drafts",
        sa.Column("approval_status", sa.String(length=32), nullable=False, server_default="not_requested"),
    )
    op.add_column(
        "website_seo_drafts",
        sa.Column("approval_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "website_seo_drafts",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "website_seo_drafts",
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "website_seo_drafts",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )
    op.alter_column("website_seo_drafts", "approval_status", server_default=None)


def downgrade() -> None:
    op.drop_column("website_seo_drafts", "rejection_reason")
    op.drop_column("website_seo_drafts", "rejected_at")
    op.drop_column("website_seo_drafts", "approved_at")
    op.drop_column("website_seo_drafts", "approval_requested_at")
    op.drop_column("website_seo_drafts", "approval_status")
