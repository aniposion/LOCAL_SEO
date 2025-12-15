"""Add approval workflow fields to posts

Revision ID: 003
Revises: 002
Create Date: 2024-01-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new PostStatus enum values
    op.execute("ALTER TYPE poststatus ADD VALUE IF NOT EXISTS 'pending_approval'")
    op.execute("ALTER TYPE poststatus ADD VALUE IF NOT EXISTS 'approved'")
    op.execute("ALTER TYPE poststatus ADD VALUE IF NOT EXISTS 'rejected'")

    # Add approval workflow columns to posts table
    op.add_column('posts', sa.Column('approval_token', sa.String(255), nullable=True, unique=True))
    op.add_column('posts', sa.Column('approval_requested_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('posts', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('posts', sa.Column('approved_by_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('posts', sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('posts', sa.Column('rejection_reason', sa.Text(), nullable=True))

    # Add notification tracking columns
    op.add_column('posts', sa.Column('notification_sent', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('posts', sa.Column('notification_channel', sa.String(50), nullable=True))
    op.add_column('posts', sa.Column('notification_sent_at', sa.DateTime(timezone=True), nullable=True))

    # Add AI image columns
    op.add_column('posts', sa.Column('ai_image_url', sa.String(500), nullable=True))
    op.add_column('posts', sa.Column('ai_image_generated_at', sa.DateTime(timezone=True), nullable=True))

    # Add foreign key for approved_by
    op.create_foreign_key(
        'fk_posts_approved_by_id',
        'posts', 'accounts',
        ['approved_by_id'], ['id'],
        ondelete='SET NULL'
    )

    # Create index for approval token
    op.create_index('ix_posts_approval_token', 'posts', ['approval_token'])


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_posts_approval_token', table_name='posts')

    # Drop foreign key
    op.drop_constraint('fk_posts_approved_by_id', 'posts', type_='foreignkey')

    # Drop columns
    op.drop_column('posts', 'ai_image_generated_at')
    op.drop_column('posts', 'ai_image_url')
    op.drop_column('posts', 'notification_sent_at')
    op.drop_column('posts', 'notification_channel')
    op.drop_column('posts', 'notification_sent')
    op.drop_column('posts', 'rejection_reason')
    op.drop_column('posts', 'rejected_at')
    op.drop_column('posts', 'approved_by_id')
    op.drop_column('posts', 'approved_at')
    op.drop_column('posts', 'approval_requested_at')
    op.drop_column('posts', 'approval_token')
