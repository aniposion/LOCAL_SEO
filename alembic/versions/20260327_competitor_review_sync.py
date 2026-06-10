"""Add review sync freshness fields to competitors.

Revision ID: 20260327_competitor_review_sync
Revises: 20260327_website_seo_archive
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260327_competitor_review_sync"
down_revision = "20260327_website_seo_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "competitors",
        sa.Column("last_review_synced_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("competitors", "last_review_synced_at")
