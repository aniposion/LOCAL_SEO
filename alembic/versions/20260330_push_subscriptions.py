"""Add push_subscriptions table for real subscription storage.

Revision ID: 20260330_push_subscriptions
Revises: 20260329_notification_delivery_audit
Create Date: 2026-03-30 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260330_push_subscriptions"
down_revision = "20260329_notification_delivery_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "account_id",
            sa.String(36),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(2048), nullable=False),
        sa.Column("p256dh_key", sa.String(512), nullable=False),
        sa.Column("auth_key", sa.String(512), nullable=False),
        sa.Column("device_type", sa.String(50), nullable=False, server_default="web"),
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
        sa.UniqueConstraint("account_id", "endpoint", name="uq_push_sub_account_endpoint"),
    )
    op.create_index(
        "ix_push_subs_account_id",
        "push_subscriptions",
        ["account_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_push_subs_account_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
