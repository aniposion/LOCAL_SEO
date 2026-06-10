"""Add notification_delivery_logs table for delivery audit.

Revision ID: 20260329_notification_delivery_audit
Revises: 20260329_notification_history
Create Date: 2026-03-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260329_notification_delivery_audit"
down_revision = "20260329_notification_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_delivery_logs",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "notification_event_id",
            sa.String(36),
            sa.ForeignKey("notification_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # channel: inbox, push, email, sms, slack
        sa.Column("channel", sa.String(50), nullable=False),
        # delivery_status: delivered, failed, unavailable, skipped
        sa.Column("delivery_status", sa.String(50), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
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
        "ix_ndl_account_status",
        "notification_delivery_logs",
        ["account_id", "delivery_status"],
    )
    op.create_index(
        "ix_ndl_event_id",
        "notification_delivery_logs",
        ["notification_event_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ndl_event_id", table_name="notification_delivery_logs")
    op.drop_index("ix_ndl_account_status", table_name="notification_delivery_logs")
    op.drop_table("notification_delivery_logs")
