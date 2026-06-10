"""Add managed pilot plans and contact funnel fields.

Revision ID: 20260518_managed_funnel
Revises: 20260502_contact_requests
Create Date: 2026-05-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260518_managed_funnel"
down_revision: Union[str, Sequence[str], None] = "20260502_contact_requests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE plantype ADD VALUE IF NOT EXISTS 'MAPS_STARTER'")
        op.execute("ALTER TYPE plantype ADD VALUE IF NOT EXISTS 'CALLS_GROWTH'")
        op.execute("ALTER TYPE plantype ADD VALUE IF NOT EXISTS 'COMPETITIVE_MARKET'")

    op.add_column("contact_requests", sa.Column("audit_id", sa.String(length=36), nullable=True))
    op.add_column("contact_requests", sa.Column("close_reason", sa.String(length=500), nullable=True))
    op.add_column("contact_requests", sa.Column("booked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contact_requests", sa.Column("won_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("contact_requests", sa.Column("lost_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_contact_requests_audit_id", "contact_requests", ["audit_id"])


def downgrade() -> None:
    op.drop_index("ix_contact_requests_audit_id", table_name="contact_requests")
    op.drop_column("contact_requests", "lost_at")
    op.drop_column("contact_requests", "won_at")
    op.drop_column("contact_requests", "booked_at")
    op.drop_column("contact_requests", "close_reason")
    op.drop_column("contact_requests", "audit_id")
    # PostgreSQL enum values cannot be safely removed without recreating the type.
