"""Add soft archive fields to Website SEO drafts.

Revision ID: 20260327_website_seo_archive
Revises: 20260327_website_seo_approval
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260327_website_seo_archive"
down_revision = "20260327_website_seo_approval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "website_seo_drafts",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "website_seo_drafts",
        sa.Column("archived_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("website_seo_drafts", "archived_reason")
    op.drop_column("website_seo_drafts", "archived_at")
