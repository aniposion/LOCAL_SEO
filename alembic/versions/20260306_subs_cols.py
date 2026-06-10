"""Add missing subscription columns used by the current model.

Revision ID: 20260306_subs_cols
Revises: 20260306_acct_cols
Create Date: 2026-03-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260306_subs_cols"
down_revision = "20260306_acct_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dunning_status = postgresql.ENUM(
        "none",
        "retrying",
        "grace_period",
        "restricted",
        "suspended",
        name="dunningstatus",
        create_type=False,
    )
    dunning_status.create(op.get_bind(), checkfirst=True)

    op.add_column("subscriptions", sa.Column("active_addons", sa.JSON(), nullable=True))
    op.add_column(
        "subscriptions",
        sa.Column("agency_location_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("subscriptions", sa.Column("trial_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("cancellation_reason", sa.String(length=100), nullable=True))
    op.add_column("subscriptions", sa.Column("cancellation_feedback", sa.Text(), nullable=True))
    op.add_column(
        "subscriptions",
        sa.Column("dunning_status", dunning_status, nullable=False, server_default="none"),
    )
    op.add_column("subscriptions", sa.Column("dunning_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("last_payment_error", sa.Text(), nullable=True))
    op.add_column(
        "subscriptions",
        sa.Column("payment_retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("subscriptions", sa.Column("next_payment_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("grace_period_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "subscriptions",
        sa.Column("access_state", sa.String(length=20), nullable=False, server_default="active"),
    )
    op.add_column("subscriptions", sa.Column("billing_cycle_anchor", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("subscriptions", "billing_cycle_anchor")
    op.drop_column("subscriptions", "access_state")
    op.drop_column("subscriptions", "grace_period_ends_at")
    op.drop_column("subscriptions", "next_payment_retry_at")
    op.drop_column("subscriptions", "payment_retry_count")
    op.drop_column("subscriptions", "last_payment_error")
    op.drop_column("subscriptions", "dunning_started_at")
    op.drop_column("subscriptions", "dunning_status")
    op.drop_column("subscriptions", "cancellation_feedback")
    op.drop_column("subscriptions", "cancellation_reason")
    op.drop_column("subscriptions", "ended_at")
    op.drop_column("subscriptions", "canceled_at")
    op.drop_column("subscriptions", "trial_start")
    op.drop_column("subscriptions", "agency_location_count")
    op.drop_column("subscriptions", "active_addons")
