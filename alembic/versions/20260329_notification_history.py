"""Add notification_events table for inbox persistence.

Revision ID: 20260329_notification_history
Revises: 20260328_review_response_publish_error
Create Date: 2026-03-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260329_notification_history"
down_revision = "20260328_review_response_publish_error"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_events",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_notification_events_account_id",
        "notification_events",
        ["account_id"],
    )
    op.create_index(
        "ix_notification_events_account_read",
        "notification_events",
        ["account_id", "read"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_events_account_read", table_name="notification_events")
    op.drop_index("ix_notification_events_account_id", table_name="notification_events")
    op.drop_table("notification_events")
