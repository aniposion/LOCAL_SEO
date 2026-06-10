"""P0: Stripe webhook idempotency and access state

Revision ID: 2026_01_05_p0_stripe
Revises: 2024_12_26_addons_system
Create Date: 2026-01-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '2026_01_05_p0_stripe'
down_revision = '2024_12_26_addons'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================
    # 1) Stripe Events (Webhook Idempotency)
    # ============================================
    op.create_table(
        'stripe_events',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('event_id', sa.String(255), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    
    # CRITICAL: UNIQUE constraint prevents race conditions
    # Multiple webhook deliveries will fail on INSERT, ensuring exactly-once processing
    op.create_index('idx_stripe_events_event_id', 'stripe_events', ['event_id'], unique=True)
    op.create_index('idx_stripe_events_type', 'stripe_events', ['event_type'])
    op.create_index('idx_stripe_events_created', 'stripe_events', ['created_at'])
    
    # ============================================
    # 2) Subscription Access State
    # ============================================
    # Add access_state column (internal control, decoupled from Stripe status)
    op.add_column('subscriptions',
        sa.Column('access_state', sa.String(20), nullable=False, server_default='active')
    )
    # Values: 'active', 'warning', 'suspended'
    
    # Create index for dunning queries (partial index for performance)
    op.execute("""
        CREATE INDEX idx_subscriptions_access_state 
        ON subscriptions(access_state, dunning_started_at) 
        WHERE access_state IN ('warning', 'suspended')
    """)
    
    # WHY: Separate access_state from Stripe status allows us to:
    # 1. Suspend access immediately without waiting for Stripe webhook
    # 2. Handle grace periods independently
    # 3. Prevent race conditions between Stripe updates and our logic


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_subscriptions_access_state")
    op.drop_column('subscriptions', 'access_state')
    op.drop_table('stripe_events')
