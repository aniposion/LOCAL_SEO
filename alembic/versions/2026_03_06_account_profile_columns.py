"""Add missing account profile columns used by the current model.

Revision ID: 20260306_acct_cols
Revises: 2026_03_06_ai_feature_uuid_fk
Create Date: 2026-03-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260306_acct_cols"
down_revision = "2026_03_06_ai_feature_uuid_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column(
            "notification_channel",
            sa.String(length=20),
            nullable=False,
            server_default="email",
        ),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "settings",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("accounts", "settings")
    op.drop_column("accounts", "notification_channel")
