"""Add AI features: Competitor Analysis, Review Responder, Social Proof

Revision ID: 007_add_ai_features
Revises: 006
Create Date: 2026-01-05 21:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '007_add_ai_features'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    bind = op.get_bind()
    competitor_status_enum = postgresql.ENUM(
        'active', 'inactive', 'removed', name='competitorstatus', create_type=False
    )
    review_intent_enum = postgresql.ENUM(
        'praise', 'complaint', 'suggestion', 'question', 'misunderstanding',
        name='reviewintent', create_type=False
    )
    response_status_enum = postgresql.ENUM(
        'pending', 'approved', 'rejected', 'published', 'failed',
        name='responsestatus', create_type=False
    )
    social_proof_status_enum = postgresql.ENUM(
        'draft', 'pending', 'approved', 'rejected', 'published',
        name='socialproofstatus', create_type=False
    )

    competitor_status_enum.create(bind, checkfirst=True)
    review_intent_enum.create(bind, checkfirst=True)
    response_status_enum.create(bind, checkfirst=True)
    social_proof_status_enum.create(bind, checkfirst=True)
    
    # Create competitors table
    op.create_table(
        'competitors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('place_id', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('business_type', sa.String(length=100), nullable=True),
        sa.Column('rating', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('review_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('distance_miles', sa.Float(), nullable=True),
        sa.Column('status', competitor_status_enum,
                  nullable=False, server_default='active'),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('place_id')
    )
    op.create_index('ix_competitors_place_id', 'competitors', ['place_id'])
    op.create_index('ix_competitors_location_id', 'competitors', ['location_id'])
    
    # Create competitor_analyses table
    op.create_table(
        'competitor_analyses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('competitor_id', sa.Integer(), nullable=True),
        sa.Column('week_start', sa.DateTime(), nullable=False),
        sa.Column('week_end', sa.DateTime(), nullable=False),
        sa.Column('trending_keywords', sa.JSON(), nullable=True),
        sa.Column('threat_level', sa.String(length=20), nullable=True),
        sa.Column('rating_trend', sa.String(length=20), nullable=True),
        sa.Column('recommended_actions', sa.JSON(), nullable=True),
        sa.Column('summary_text', sa.Text(), nullable=True),
        sa.Column('metrics_snapshot', sa.JSON(), nullable=True),
        sa.Column('generated_by_ai', sa.String(length=50), nullable=True, server_default='gemini-1.5-flash'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['competitor_id'], ['competitors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_competitor_analyses_location_id', 'competitor_analyses', ['location_id'])
    
    # Create competitor_reviews table
    op.create_table(
        'competitor_reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('competitor_id', sa.Integer(), nullable=False),
        sa.Column('review_id', sa.String(length=255), nullable=False),
        sa.Column('author_name', sa.String(length=255), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('publish_time', sa.DateTime(), nullable=True),
        sa.Column('extracted_keywords', sa.JSON(), nullable=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['competitor_id'], ['competitors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('review_id')
    )
    op.create_index('ix_competitor_reviews_review_id', 'competitor_reviews', ['review_id'])
    
    # Create review_responses table
    op.create_table(
        'review_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('review_id', sa.String(length=255), nullable=False),
        sa.Column('review_author', sa.String(length=255), nullable=True),
        sa.Column('review_rating', sa.Integer(), nullable=False),
        sa.Column('review_text', sa.Text(), nullable=True),
        sa.Column('review_date', sa.DateTime(), nullable=True),
        sa.Column('platform', sa.String(length=50), nullable=True, server_default='google'),
        sa.Column('platform_review_url', sa.String(length=500), nullable=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('intent', review_intent_enum, nullable=False),
        sa.Column('detected_issues', sa.Text(), nullable=True),
        sa.Column('ai_draft', sa.Text(), nullable=False),
        sa.Column('tone', sa.String(length=50), nullable=True),
        sa.Column('generated_by_ai', sa.String(length=50), nullable=True, server_default='gemini-1.5-flash'),
        sa.Column('status', response_status_enum, nullable=False, server_default='pending'),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('platform_response_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approved_by'], ['accounts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('review_id')
    )
    op.create_index('ix_review_responses_review_id', 'review_responses', ['review_id'])
    op.create_index('ix_review_responses_location_id', 'review_responses', ['location_id'])
    op.create_index('ix_review_responses_status', 'review_responses', ['status'])
    
    # Create review_webhooks table
    op.create_table(
        'review_webhooks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=True),
        sa.Column('review_id', sa.String(length=255), nullable=False),
        sa.Column('payload', sa.Text(), nullable=True),
        sa.Column('processed', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_review_webhooks_location_id', 'review_webhooks', ['location_id'])
    op.create_index('ix_review_webhooks_processed', 'review_webhooks', ['processed'])
    
    # Create social_proof_cards table
    op.create_table(
        'social_proof_cards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('review_id', sa.String(length=255), nullable=False),
        sa.Column('review_author', sa.String(length=255), nullable=True),
        sa.Column('review_rating', sa.Integer(), nullable=False),
        sa.Column('review_text', sa.Text(), nullable=False),
        sa.Column('review_date', sa.DateTime(), nullable=True),
        sa.Column('card_title', sa.String(length=255), nullable=True),
        sa.Column('card_text', sa.Text(), nullable=True),
        sa.Column('image_prompt', sa.Text(), nullable=True),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('background_image_url', sa.String(length=500), nullable=True),
        sa.Column('final_card_url', sa.String(length=500), nullable=True),
        sa.Column('layout_style', sa.String(length=50), nullable=True, server_default='instagram_square'),
        sa.Column('text_color', sa.String(length=20), nullable=True, server_default='#FFFFFF'),
        sa.Column('background_color', sa.String(length=20), nullable=True, server_default='#000000'),
        sa.Column('font_family', sa.String(length=100), nullable=True, server_default='Arial'),
        sa.Column('status', social_proof_status_enum, nullable=False, server_default='draft'),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('published_to', sa.String(length=50), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('platform_post_id', sa.String(length=255), nullable=True),
        sa.Column('generated_by_ai', sa.String(length=50), nullable=True, server_default='imagen-3'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approved_by'], ['accounts.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_social_proof_cards_review_id', 'social_proof_cards', ['review_id'])
    op.create_index('ix_social_proof_cards_location_id', 'social_proof_cards', ['location_id'])
    op.create_index('ix_social_proof_cards_status', 'social_proof_cards', ['status'])
    
    # Create social_proof_schedules table
    op.create_table(
        'social_proof_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('enabled', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('frequency', sa.String(length=50), nullable=True, server_default='weekly'),
        sa.Column('day_of_week', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('time_of_day', sa.String(length=10), nullable=True, server_default='18:00'),
        sa.Column('min_rating', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('min_text_length', sa.Integer(), nullable=True, server_default='50'),
        sa.Column('max_cards_per_run', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('auto_approve', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('auto_publish', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_social_proof_schedules_location_id', 'social_proof_schedules', ['location_id'])


def downgrade() -> None:
    """Downgrade database schema."""
    
    # Drop tables in reverse order
    op.drop_index('ix_social_proof_schedules_location_id', table_name='social_proof_schedules')
    op.drop_table('social_proof_schedules')
    
    op.drop_index('ix_social_proof_cards_status', table_name='social_proof_cards')
    op.drop_index('ix_social_proof_cards_location_id', table_name='social_proof_cards')
    op.drop_index('ix_social_proof_cards_review_id', table_name='social_proof_cards')
    op.drop_table('social_proof_cards')
    
    op.drop_index('ix_review_webhooks_processed', table_name='review_webhooks')
    op.drop_index('ix_review_webhooks_location_id', table_name='review_webhooks')
    op.drop_table('review_webhooks')
    
    op.drop_index('ix_review_responses_status', table_name='review_responses')
    op.drop_index('ix_review_responses_location_id', table_name='review_responses')
    op.drop_index('ix_review_responses_review_id', table_name='review_responses')
    op.drop_table('review_responses')
    
    op.drop_index('ix_competitor_reviews_review_id', table_name='competitor_reviews')
    op.drop_table('competitor_reviews')
    
    op.drop_index('ix_competitor_analyses_location_id', table_name='competitor_analyses')
    op.drop_table('competitor_analyses')
    
    op.drop_index('ix_competitors_location_id', table_name='competitors')
    op.drop_index('ix_competitors_place_id', table_name='competitors')
    op.drop_table('competitors')
    
    # Drop enums
    op.execute('DROP TYPE socialproofstatus')
    op.execute('DROP TYPE responsestatus')
    op.execute('DROP TYPE reviewintent')
    op.execute('DROP TYPE competitorstatus')
