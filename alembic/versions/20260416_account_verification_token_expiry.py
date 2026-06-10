"""Add verification_token_expires to accounts for email verification hardening.

Revision ID: 20260416_account_verification_token_expiry
Revises: 20260331_review_bulk_retry_log
Create Date: 2026-04-16 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260416_account_verification_token_expiry"
down_revision = "20260331_review_bulk_retry_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("verification_token_expires", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounts", "verification_token_expires")
