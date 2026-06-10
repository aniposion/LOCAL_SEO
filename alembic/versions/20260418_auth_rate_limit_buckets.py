"""Add auth_rate_limit_buckets table for persistent anonymous auth throttling.

Revision ID: 20260418_auth_rate_limit_buckets
Revises: 20260418_upload_assets
Create Date: 2026-04-18 00:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260418_auth_rate_limit_buckets"
down_revision = "20260418_upload_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_rate_limit_buckets",
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("bucket_key_hash", sa.String(length=64), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("last_hit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_auth_rate_limit_buckets_bucket_key_hash",
        "auth_rate_limit_buckets",
        ["bucket_key_hash"],
        unique=True,
    )
    op.create_index(
        "ix_auth_rate_limit_buckets_action_scope",
        "auth_rate_limit_buckets",
        ["action", "scope"],
    )


def downgrade() -> None:
    op.drop_index("ix_auth_rate_limit_buckets_action_scope", table_name="auth_rate_limit_buckets")
    op.drop_index("ix_auth_rate_limit_buckets_bucket_key_hash", table_name="auth_rate_limit_buckets")
    op.drop_table("auth_rate_limit_buckets")
