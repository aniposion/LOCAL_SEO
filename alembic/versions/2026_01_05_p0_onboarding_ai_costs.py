"""P0: Onboarding progress and AI usage costs

Revision ID: 2026_01_05_p0_onboarding
Revises: 2026_01_05_p0_analytics
Create Date: 2026-01-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '2026_01_05_p0_onboarding'
down_revision = '2026_01_05_p0_analytics'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================
    # 1) Onboarding Progress
    # ============================================
    op.create_table(
        'onboarding_progress',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('completed_steps', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_steps', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('current_step', sa.String(50), nullable=True),
        sa.Column('steps_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        # steps_data: {"run_audit": "2026-01-05T10:00:00Z", "view_insights": null, ...}
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
    )
    
    op.create_index('idx_onboarding_completed', 'onboarding_progress', ['completed_steps', 'completed_at'])
    
    # WHY: Track time-to-activation accurately
    # steps_data JSONB allows flexible step definitions without schema changes
    
    # ============================================
    # 2) AI Usage Costs
    # ============================================
    op.create_table(
        'ai_usage_costs',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('location_id', sa.String(36), sa.ForeignKey('locations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('feature', sa.String(50), nullable=False),
        # 'competitor_analysis', 'social_card', 'review_response', 'content_generation'
        sa.Column('api_provider', sa.String(50), nullable=False),
        # 'gemini', 'imagen', 'google_places'
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=False),
        sa.Column('tokens_input', sa.Integer(), nullable=True),
        sa.Column('tokens_output', sa.Integer(), nullable=True),
        sa.Column('api_calls', sa.Integer(), server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    
    # Indexes for cost cap queries (CRITICAL for performance)
    op.execute("""
        CREATE INDEX idx_ai_costs_user_month 
        ON ai_usage_costs(user_id, DATE_TRUNC('month', created_at))
    """)
    op.execute("""
        CREATE INDEX idx_ai_costs_account_month 
        ON ai_usage_costs(account_id, DATE_TRUNC('month', created_at))
    """)
    op.create_index('idx_ai_costs_feature', 'ai_usage_costs', ['feature', 'created_at'])
    
    # WHY: Cost cap must be checked BEFORE API call
    # Index on (user_id, month) allows fast SUM query
    # Numeric(10,6) stores costs accurately (e.g., $0.000015 per token)


def downgrade() -> None:
    op.drop_table('ai_usage_costs')
    op.drop_table('onboarding_progress')
