"""Add onboarding audits table

Revision ID: 004
Revises: 003
Create Date: 2024-01-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create onboarding status enum
    op.execute("""
        CREATE TYPE onboardingstatus AS ENUM (
            'pending', 'searching', 'analyzing', 'completed', 'failed'
        )
    """)

    # Create audit grade enum
    op.execute("""
        CREATE TYPE auditgrade AS ENUM (
            'A+', 'A', 'B+', 'B', 'B-', 'C+', 'C', 'D', 'F'
        )
    """)

    # Create onboarding_audits table
    op.create_table(
        'onboarding_audits',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=True),
        
        # Business input
        sa.Column('business_name', sa.String(255), nullable=False),
        sa.Column('address', sa.String(500), nullable=False),
        sa.Column('city', sa.String(100)),
        sa.Column('state', sa.String(50)),
        sa.Column('country', sa.String(50), default='US'),
        sa.Column('phone', sa.String(50)),
        sa.Column('website_url', sa.String(500)),
        
        # Google Places matching
        sa.Column('place_id', sa.String(255)),
        sa.Column('matched_name', sa.String(255)),
        sa.Column('matched_address', sa.String(500)),
        sa.Column('category', sa.String(100)),
        sa.Column('latitude', sa.Float),
        sa.Column('longitude', sa.Float),
        sa.Column('place_candidates', postgresql.JSONB),
        
        # Collected data
        sa.Column('review_count', sa.Integer, default=0),
        sa.Column('average_rating', sa.Float),
        sa.Column('latest_review_date', sa.DateTime(timezone=True)),
        sa.Column('photo_count', sa.Integer, default=0),
        sa.Column('has_hours', sa.Boolean, default=False),
        sa.Column('has_phone', sa.Boolean, default=False),
        sa.Column('has_website', sa.Boolean, default=False),
        sa.Column('has_description', sa.Boolean, default=False),
        
        # Post/activity data
        sa.Column('latest_post_date', sa.DateTime(timezone=True)),
        sa.Column('post_count_30_days', sa.Integer, default=0),
        
        # Competitor data
        sa.Column('competitor_avg_reviews', sa.Float),
        sa.Column('competitor_avg_rating', sa.Float),
        sa.Column('competitor_count', sa.Integer, default=0),
        sa.Column('competitors_data', postgresql.JSONB),
        
        # Social presence
        sa.Column('has_instagram', sa.Boolean),
        sa.Column('instagram_handle', sa.String(100)),
        sa.Column('has_facebook', sa.Boolean),
        sa.Column('has_yelp', sa.Boolean),
        
        # Scores
        sa.Column('total_score', sa.Float),
        sa.Column('grade', sa.Enum('A+', 'A', 'B+', 'B', 'B-', 'C+', 'C', 'D', 'F', 
                                   name='auditgrade', create_type=False)),
        sa.Column('review_score', sa.Float),
        sa.Column('activity_score', sa.Float),
        sa.Column('completeness_score', sa.Float),
        sa.Column('competition_score', sa.Float),
        
        # AI Analysis
        sa.Column('estimated_monthly_loss', sa.Float),
        sa.Column('estimated_missed_calls', sa.Integer),
        sa.Column('summary', sa.Text),
        sa.Column('recommendations', postgresql.JSONB),
        sa.Column('recommended_plan', sa.String(50)),
        
        # Status
        sa.Column('status', sa.Enum('pending', 'searching', 'analyzing', 'completed', 'failed',
                                    name='onboardingstatus', create_type=False),
                  default='pending'),
        sa.Column('error_message', sa.Text),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
    )

    # Create indexes
    op.create_index('ix_onboarding_audits_account_id', 'onboarding_audits', ['account_id'])
    op.create_index('ix_onboarding_audits_place_id', 'onboarding_audits', ['place_id'])
    op.create_index('ix_onboarding_audits_status', 'onboarding_audits', ['status'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_onboarding_audits_status', table_name='onboarding_audits')
    op.drop_index('ix_onboarding_audits_place_id', table_name='onboarding_audits')
    op.drop_index('ix_onboarding_audits_account_id', table_name='onboarding_audits')

    # Drop table
    op.drop_table('onboarding_audits')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS auditgrade')
    op.execute('DROP TYPE IF EXISTS onboardingstatus')
