"""Add review_bulk_retry_logs table to persist bulk retry outcomes.

Revision ID: 20260331_review_bulk_retry_log
Revises: 20260330_push_subscriptions
Create Date: 2026-03-31 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260331_review_bulk_retry_log"
down_revision = "20260330_push_subscriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_bulk_retry_logs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("succeeded", sa.Integer(), nullable=False),
        sa.Column("still_failed", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_review_bulk_retry_logs_account_id",
        "review_bulk_retry_logs",
        ["account_id"],
    )
    op.create_index(
        "ix_review_bulk_retry_logs_created_at",
        "review_bulk_retry_logs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_review_bulk_retry_logs_created_at", table_name="review_bulk_retry_logs")
    op.drop_index("ix_review_bulk_retry_logs_account_id", table_name="review_bulk_retry_logs")
    op.drop_table("review_bulk_retry_logs")
