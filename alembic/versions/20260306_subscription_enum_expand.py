"""Expand subscription enums to match current application states.

Revision ID: 20260306_sub_enum
Revises: 20260306_dunning_fix
Create Date: 2026-03-06
"""

from alembic import op


revision = "20260306_sub_enum"
down_revision = "20260306_dunning_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE plantype ADD VALUE IF NOT EXISTS 'PREMIUM'")
    op.execute("ALTER TYPE subscriptionstatus ADD VALUE IF NOT EXISTS 'INCOMPLETE'")
    op.execute("ALTER TYPE subscriptionstatus ADD VALUE IF NOT EXISTS 'INCOMPLETE_EXPIRED'")
    op.execute("ALTER TYPE subscriptionstatus ADD VALUE IF NOT EXISTS 'UNPAID'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely without recreating the type.
    pass
