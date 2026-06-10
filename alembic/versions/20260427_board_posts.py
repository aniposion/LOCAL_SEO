"""add website board posts

Revision ID: 20260427_board_posts
Revises: 20260426_merge_public_launch_heads
Create Date: 2026-04-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260427_board_posts"
down_revision: Union[str, Sequence[str], None] = "20260426_merge_public_launch_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "board_posts",
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_id", sa.String(length=36), sa.ForeignKey("locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("image_asset_id", sa.String(length=36), sa.ForeignKey("upload_assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="published"),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_board_posts_account_id", "board_posts", ["account_id"])
    op.create_index("ix_board_posts_location_id", "board_posts", ["location_id"])
    op.create_index("ix_board_posts_status", "board_posts", ["status"])
    op.create_index("ix_board_posts_created_at", "board_posts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_board_posts_created_at", table_name="board_posts")
    op.drop_index("ix_board_posts_status", table_name="board_posts")
    op.drop_index("ix_board_posts_location_id", table_name="board_posts")
    op.drop_index("ix_board_posts_account_id", table_name="board_posts")
    op.drop_table("board_posts")
