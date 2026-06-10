"""P0: Analytics events for server-side tracking

Revision ID: 2026_01_05_p0_analytics
Revises: 2026_01_05_p0_stripe
Create Date: 2026-01-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '2026_01_05_p0_analytics'
down_revision = '2026_01_05_p0_stripe'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================
    # Analytics Events (Server-Side Tracking)
    # ============================================
    op.create_table(
        'analytics_events',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('event_name', sa.String(100), nullable=False),
        sa.Column('properties', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    
    # Indexes for funnel queries
    op.create_index('idx_analytics_events_user', 'analytics_events', ['user_id', 'event_name'])
    op.create_index('idx_analytics_events_account', 'analytics_events', ['account_id', 'event_name'])
    op.create_index('idx_analytics_events_name', 'analytics_events', ['event_name'])
    op.create_index('idx_analytics_events_created', 'analytics_events', ['created_at'])
    
    # GIN index for JSONB property filtering
    op.create_index(
        'idx_analytics_events_properties',
        'analytics_events',
        ['properties'],
        postgresql_using='gin'
    )
    
    # WHY: Server-side events are single source of truth
    # No client-side tracking = no ad blockers, no missing data
    # JSONB properties allow flexible schema without migrations


def downgrade() -> None:
    op.drop_table('analytics_events')
