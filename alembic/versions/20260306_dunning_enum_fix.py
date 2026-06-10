"""Align dunning status enum values with SQLAlchemy enum names.

Revision ID: 20260306_dunning_fix
Revises: 20260306_subs_cols
Create Date: 2026-03-06
"""

from alembic import op


revision = "20260306_dunning_fix"
down_revision = "20260306_subs_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE subscriptions DROP COLUMN dunning_status")
    op.execute("DROP TYPE IF EXISTS dunningstatus")
    op.execute(
        "CREATE TYPE dunningstatus AS ENUM "
        "('NONE', 'RETRYING', 'GRACE_PERIOD', 'RESTRICTED', 'SUSPENDED')"
    )
    op.execute(
        "ALTER TABLE subscriptions ADD COLUMN dunning_status dunningstatus "
        "NOT NULL DEFAULT 'NONE'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE subscriptions DROP COLUMN dunning_status")
    op.execute("DROP TYPE IF EXISTS dunningstatus")
    op.execute(
        "CREATE TYPE dunningstatus AS ENUM "
        "('none', 'retrying', 'grace_period', 'restricted', 'suspended')"
    )
    op.execute(
        "ALTER TABLE subscriptions ADD COLUMN dunning_status dunningstatus "
        "NOT NULL DEFAULT 'none'"
    )
