"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Accounts table
    op.create_table(
        'accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('oauth_provider', sa.String(50), nullable=True),
        sa.Column('oauth_id', sa.String(255), nullable=True),
        sa.Column('role', sa.Enum('OWNER', 'MANAGER', 'AGENCY', name='accountrole'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_accounts_email', 'accounts', ['email'], unique=True)

    # Locations table
    op.create_table(
        'locations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('address', sa.String(500), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(100), nullable=True),
        sa.Column('country', sa.String(100), nullable=False, default='US'),
        sa.Column('postal_code', sa.String(20), nullable=True),
        sa.Column('lat', sa.Float(), nullable=True),
        sa.Column('lng', sa.Float(), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('website_url', sa.String(500), nullable=True),
        sa.Column('business_hours', postgresql.JSONB(), nullable=True),
        sa.Column('services', postgresql.JSONB(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('gbp_location_id', sa.String(255), nullable=True),
        sa.Column('ig_business_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_locations_account_id', 'locations', ['account_id'])

    # Channels table
    op.create_table(
        'channels',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.Enum('GBP', 'INSTAGRAM', 'WEBSITE', name='channeltype'), nullable=False),
        sa.Column('credentials', postgresql.JSONB(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('meta', postgresql.JSONB(), nullable=True),
        sa.Column('last_sync_at', sa.String(50), nullable=True),
        sa.Column('error_message', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_channels_location_id', 'channels', ['location_id'])

    # Posts table
    op.create_table(
        'posts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('platform', sa.Enum('GBP', 'INSTAGRAM', 'WEBSITE', name='platform'), nullable=False),
        sa.Column('status', sa.Enum('DRAFT', 'QUEUED', 'POSTED', 'FAILED', name='poststatus'), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('hashtags', postgresql.JSONB(), nullable=True),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('image_prompt', sa.Text(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provider_post_id', sa.String(255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('generated_by', sa.String(100), nullable=True),
        sa.Column('generation_params', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_posts_location_id', 'posts', ['location_id'])
    op.create_index('ix_posts_status', 'posts', ['status'])
    op.create_index('ix_posts_scheduled_at', 'posts', ['scheduled_at'])

    # Analytics table
    op.create_table(
        'analytics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('platform', sa.String(50), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('impressions', sa.Integer(), nullable=True),
        sa.Column('clicks', sa.Integer(), nullable=True),
        sa.Column('calls', sa.Integer(), nullable=True),
        sa.Column('direction_requests', sa.Integer(), nullable=True),
        sa.Column('reach', sa.Integer(), nullable=True),
        sa.Column('likes', sa.Integer(), nullable=True),
        sa.Column('comments', sa.Integer(), nullable=True),
        sa.Column('shares', sa.Integer(), nullable=True),
        sa.Column('saves', sa.Integer(), nullable=True),
        sa.Column('page_views', sa.Integer(), nullable=True),
        sa.Column('unique_visitors', sa.Integer(), nullable=True),
        sa.Column('avg_time_on_page', sa.Integer(), nullable=True),
        sa.Column('source_raw', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_analytics_location_id', 'analytics', ['location_id'])
    op.create_index('ix_analytics_platform', 'analytics', ['platform'])
    op.create_index('ix_analytics_date', 'analytics', ['date'])

    # SEO Scores table
    op.create_table(
        'seo_scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('factors', postgresql.JSONB(), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('recommendations', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_seo_scores_location_id', 'seo_scores', ['location_id'])
    op.create_index('ix_seo_scores_date', 'seo_scores', ['date'])

    # Reports table
    op.create_table(
        'reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('file_url', sa.String(500), nullable=True),
        sa.Column('summary', postgresql.JSONB(), nullable=True),
        sa.Column('email_sent', sa.Boolean(), nullable=False, default=False),
        sa.Column('email_sent_at', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_reports_location_id', 'reports', ['location_id'])

    # Schedules table
    op.create_table(
        'schedules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('platform', sa.String(50), nullable=False),
        sa.Column('cron_expr', sa.String(100), nullable=True),
        sa.Column('rrule', sa.String(255), nullable=True),
        sa.Column('topic_prefs', postgresql.JSONB(), nullable=True),
        sa.Column('tone', sa.String(50), nullable=True),
        sa.Column('language', sa.String(10), nullable=False, default='en'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_schedules_location_id', 'schedules', ['location_id'])


def downgrade() -> None:
    op.drop_table('schedules')
    op.drop_table('reports')
    op.drop_table('seo_scores')
    op.drop_table('analytics')
    op.drop_table('posts')
    op.drop_table('channels')
    op.drop_table('locations')
    op.drop_table('accounts')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS accountrole')
    op.execute('DROP TYPE IF EXISTS channeltype')
    op.execute('DROP TYPE IF EXISTS platform')
    op.execute('DROP TYPE IF EXISTS poststatus')
