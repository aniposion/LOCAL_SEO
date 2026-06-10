"""Allow guest onboarding audits and persist free-audit contact emails.

Revision ID: 20260423_free_audit_contact_email
Revises: 20260418_auth_rate_limit_buckets
Create Date: 2026-04-23 18:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260423_free_audit_contact_email"
down_revision = "20260418_auth_rate_limit_buckets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("onboarding_audits", "account_id", existing_type=sa.UUID(), nullable=True)
    op.add_column(
        "onboarding_audits",
        sa.Column("contact_email", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("onboarding_audits", "contact_email")
    op.alter_column("onboarding_audits", "account_id", existing_type=sa.UUID(), nullable=False)
