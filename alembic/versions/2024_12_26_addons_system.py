"""Add-ons system tables

Revision ID: 2024_12_26_addons
Revises: 2024_12_25_billing_system
Create Date: 2024-12-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2024_12_26_addons'
down_revision = '2024_12_25_billing'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create addon_definitions table
    op.create_table(
        'addon_definitions',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('price_monthly', sa.Numeric(10, 2), nullable=False),
        sa.Column('price_yearly', sa.Numeric(10, 2), nullable=False),
        sa.Column('stripe_price_id_monthly', sa.String(100), nullable=True),
        sa.Column('stripe_price_id_yearly', sa.String(100), nullable=True),
        sa.Column('min_plan', sa.String(20), nullable=False, server_default='pro'),
        sa.Column('feature_flag', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('sort_order', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # Seed addon definitions
    op.execute("""
        INSERT INTO addon_definitions (id, name, description, price_monthly, price_yearly, min_plan, feature_flag, sort_order) VALUES
        ('missed_call_text_back', 'Missed Call Text Back', 'Automatically text customers who call when you''re unavailable', 29, 290, 'pro', 'missed_call_text_back', 1),
        ('review_booster', 'Review Booster', 'Send review requests via SMS and Email to boost your ratings', 39, 390, 'pro', 'review_booster_campaigns', 2),
        ('website_seo_upgrade', 'Website SEO Upgrade', 'Advanced keyword analysis and auto-generated blog posts', 49, 490, 'pro', 'website_seo_advanced', 3),
        ('social_auto_responder', 'Social Auto-Responder', 'Auto-reply to Instagram DMs and comments', 29, 290, 'pro', 'social_auto_responder', 4),
        ('short_video_generator', 'Short Video Generator', 'AI-generated promotional videos for Reels and Shorts', 49, 490, 'premium', 'video_generation', 5)
    """)
    
    # Create subscription_addons table
    op.create_table(
        'subscription_addons',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('subscriptions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('addon_id', sa.String(50), sa.ForeignKey('addon_definitions.id'), nullable=False),
        sa.Column('stripe_subscription_item_id', sa.String(100), nullable=True),
        sa.Column('status', sa.String(20), server_default='active'),  # active, pending_cancel, canceled
        sa.Column('attached_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('cancel_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('subscription_id', 'addon_id', name='uq_subscription_addon'),
    )
    
    # Create indexes
    op.create_index('idx_subscription_addons_subscription', 'subscription_addons', ['subscription_id'])
    op.create_index('idx_subscription_addons_status', 'subscription_addons', ['status'])
    op.create_index('idx_subscription_addons_addon', 'subscription_addons', ['addon_id'])


def downgrade() -> None:
    op.drop_index('idx_subscription_addons_addon', table_name='subscription_addons')
    op.drop_index('idx_subscription_addons_status', table_name='subscription_addons')
    op.drop_index('idx_subscription_addons_subscription', table_name='subscription_addons')
    op.drop_table('subscription_addons')
    op.drop_table('addon_definitions')
