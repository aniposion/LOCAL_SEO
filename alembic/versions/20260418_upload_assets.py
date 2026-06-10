"""Add upload_assets table for persisted upload metadata.

Revision ID: 20260418_upload_assets
Revises: 20260416_account_verification_token_expiry
Create Date: 2026-04-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260418_upload_assets"
down_revision = "20260416_account_verification_token_expiry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "upload_assets",
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=50), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_upload_assets_account_id", "upload_assets", ["account_id"])
    op.create_index("ix_upload_assets_file_type", "upload_assets", ["file_type"])
    op.create_index("ix_upload_assets_created_at", "upload_assets", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_upload_assets_created_at", table_name="upload_assets")
    op.drop_index("ix_upload_assets_file_type", table_name="upload_assets")
    op.drop_index("ix_upload_assets_account_id", table_name="upload_assets")
    op.drop_table("upload_assets")
