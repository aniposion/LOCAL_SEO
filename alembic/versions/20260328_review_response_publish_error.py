"""Add publish_error to review_responses.

Revision ID: 20260328_review_response_publish_error
Revises: 20260327_website_seo_archive
Create Date: 2026-03-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260328_review_response_publish_error"
down_revision = "20260327_website_seo_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "review_responses",
        sa.Column("publish_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("review_responses", "publish_error")
