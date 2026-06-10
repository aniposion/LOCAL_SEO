"""Add retry tracking columns to review booster requests.

Revision ID: 20260306_review_retry
Revises: 20260306_poststatus
Create Date: 2026-03-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260306_review_retry"
down_revision = "20260306_poststatus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("booster_requests", sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("booster_requests", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("booster_requests", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("booster_requests", sa.Column("last_error", sa.Text(), nullable=True))
    op.alter_column("booster_requests", "retry_count", server_default=None)


def downgrade() -> None:
    op.drop_column("booster_requests", "last_error")
    op.drop_column("booster_requests", "retry_count")
    op.drop_column("booster_requests", "next_retry_at")
    op.drop_column("booster_requests", "last_attempt_at")
