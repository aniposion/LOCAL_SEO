"""Add P0 features - Action Plan, Autopilot, Reliable Publisher, Feedback

Revision ID: 005
Revises: 004
Create Date: 2024-12-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # RECOMMENDATIONS & PERFORMANCE TRACKING (P0-2)
    # =========================================================================
    
    op.create_table(
        'recommendations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('audit_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        sa.Column('type', sa.String(30), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        
        sa.Column('impact_score', sa.Integer, default=50),
        sa.Column('effort', sa.String(20), default='medium'),
        sa.Column('autopilot_possible', sa.Boolean, default=False),
        
        sa.Column('expected_calls_lift', sa.Float, nullable=True),
        sa.Column('expected_directions_lift', sa.Float, nullable=True),
        sa.Column('expected_views_lift', sa.Float, nullable=True),
        
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('week_of', sa.DateTime(timezone=True), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    op.create_table(
        'performance_tracking',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('week_of', sa.DateTime(timezone=True), nullable=False),
        
        sa.Column('calls', sa.Integer, nullable=True),
        sa.Column('directions', sa.Integer, nullable=True),
        sa.Column('views', sa.Integer, nullable=True),
        sa.Column('reviews', sa.Integer, nullable=True),
        sa.Column('avg_rating', sa.Float, nullable=True),
        
        sa.Column('calls_change', sa.Float, nullable=True),
        sa.Column('directions_change', sa.Float, nullable=True),
        sa.Column('views_change', sa.Float, nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    # =========================================================================
    # CONTENT CALENDAR & AUTOPILOT (P0-1)
    # =========================================================================
    
    op.create_table(
        'autopilot_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
        
        sa.Column('enabled', sa.Boolean, default=False),
        sa.Column('posts_per_week', sa.Integer, default=2),
        sa.Column('preferred_days', postgresql.JSONB, nullable=True),
        sa.Column('preferred_time', sa.String(10), nullable=True),
        sa.Column('platforms', postgresql.JSONB, nullable=True),
        sa.Column('theme_preferences', postgresql.JSONB, nullable=True),
        sa.Column('excluded_topics', postgresql.JSONB, nullable=True),
        sa.Column('auto_approve', sa.Boolean, default=False),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    op.create_table(
        'content_calendar',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        
        sa.Column('week_of', sa.DateTime(timezone=True), nullable=False),
        sa.Column('month_of', sa.DateTime(timezone=True), nullable=False),
        
        sa.Column('theme', sa.String(200), nullable=True),
        sa.Column('offer', sa.String(200), nullable=True),
        sa.Column('cta', sa.String(100), nullable=True),
        sa.Column('target_platforms', postgresql.JSONB, nullable=True),
        sa.Column('image_concept', sa.Text, nullable=True),
        
        sa.Column('auto_generated', sa.Boolean, default=True),
        sa.Column('approved', sa.Boolean, default=False),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('post_ids', postgresql.JSONB, nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    op.create_table(
        'content_usage_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        
        sa.Column('content_type', sa.String(50), nullable=False),
        sa.Column('content_value', sa.Text, nullable=False),
        sa.Column('embedding', postgresql.ARRAY(sa.Float), nullable=True),
        
        sa.Column('used_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    # =========================================================================
    # PUBLISH JOBS & RELIABILITY (P0-1)
    # =========================================================================
    
    op.create_table(
        'publish_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('posts.id', ondelete='CASCADE'), nullable=False, index=True),
        
        sa.Column('platform', sa.String(30), nullable=False),
        sa.Column('status', sa.String(20), default='pending'),
        
        sa.Column('tries', sa.Integer, default=0),
        sa.Column('max_tries', sa.Integer, default=5),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.Column('idempotency_key', sa.String(100), unique=True, nullable=True),
        
        sa.Column('last_error', sa.Text, nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        
        sa.Column('platform_post_id', sa.String(200), nullable=True),
        sa.Column('platform_url', sa.Text, nullable=True),
        
        sa.Column('request_payload', postgresql.JSONB, nullable=True),
        sa.Column('response_payload', postgresql.JSONB, nullable=True),
        
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    op.create_table(
        'platform_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        
        sa.Column('platform', sa.String(30), nullable=False),
        sa.Column('access_token', sa.Text, nullable=True),
        sa.Column('refresh_token', sa.Text, nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.Column('status', sa.String(30), default='active'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_refreshed_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.Column('scopes', postgresql.JSONB, nullable=True),
        sa.Column('account_info', postgresql.JSONB, nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    op.create_table(
        'rate_limit_tracker',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('platform', sa.String(30), nullable=False),
        sa.Column('endpoint', sa.String(100), nullable=True),
        
        sa.Column('requests_count', sa.Integer, default=0),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('window_seconds', sa.Integer, default=3600),
        sa.Column('max_requests', sa.Integer, default=100),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    # =========================================================================
    # FEEDBACK & BRAND VOICE (P0-3)
    # =========================================================================
    
    op.create_table(
        'rejection_reason_codes',
        sa.Column('code', sa.String(50), primary_key=True),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('usage_count', sa.Integer, default=0),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    # Insert default rejection codes
    op.execute("""
        INSERT INTO rejection_reason_codes (code, label, description, category, usage_count) VALUES
        ('tone_too_formal', '톤이 너무 딱딱함', '더 친근한 톤으로 수정', 'tone', 0),
        ('tone_too_casual', '톤이 너무 가벼움', '더 전문적인 톤으로 수정', 'tone', 0),
        ('price_mention', '가격 언급 금지 위반', '직접적인 가격 언급 제거', 'compliance', 0),
        ('medical_claim', '의학적 효과 주장', '효과 대신 경험으로 수정', 'compliance', 0),
        ('too_long', '내용이 너무 김', '간결하게 줄이기', 'content', 0),
        ('too_short', '내용이 너무 짧음', '더 상세하게 작성', 'content', 0),
        ('weak_cta', 'CTA가 약함', '행동 유도 문구 강화', 'content', 0),
        ('off_brand', '브랜드와 맞지 않음', '브랜드 톤에 맞게 수정', 'brand', 0),
        ('wrong_hashtags', '해시태그 부적절', '타겟 해시태그로 수정', 'content', 0),
        ('factual_error', '사실 관계 오류', '정확한 정보로 수정', 'content', 0),
        ('competitor_mention', '경쟁사 언급', '경쟁사 언급 제거', 'compliance', 0)
    """)
    
    op.create_table(
        'post_feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('posts.id', ondelete='CASCADE'), nullable=False, index=True),
        
        sa.Column('action', sa.String(30), nullable=False),
        sa.Column('reason_codes', postgresql.JSONB, nullable=True),
        sa.Column('free_text', sa.Text, nullable=True),
        
        sa.Column('original_content', postgresql.JSONB, nullable=True),
        sa.Column('edited_content', postgresql.JSONB, nullable=True),
        sa.Column('diff_summary', sa.Text, nullable=True),
        
        sa.Column('learned', sa.Boolean, default=False),
        sa.Column('learned_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    op.create_table(
        'brand_voice_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
        
        sa.Column('preferred_terms', postgresql.JSONB, nullable=True),
        sa.Column('avoided_terms', postgresql.JSONB, nullable=True),
        
        sa.Column('tone_formal_level', sa.Integer, default=5),
        sa.Column('tone_keywords', postgresql.JSONB, nullable=True),
        
        sa.Column('compliance_rules', postgresql.JSONB, nullable=True),
        
        sa.Column('industry', sa.String(50), nullable=True),
        sa.Column('industry_presets_applied', sa.Boolean, default=False),
        
        sa.Column('feedback_count', sa.Integer, default=0),
        sa.Column('last_learned_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    # =========================================================================
    # INDEXES
    # =========================================================================
    
    op.create_index('idx_recommendations_location_week', 'recommendations', ['location_id', 'week_of'])
    op.create_index('idx_recommendations_status', 'recommendations', ['status'])
    op.create_index('idx_content_calendar_location_month', 'content_calendar', ['location_id', 'month_of'])
    op.create_index('idx_publish_jobs_status_next_run', 'publish_jobs', ['status', 'next_run_at'])
    op.create_index('idx_post_feedback_post', 'post_feedback', ['post_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_post_feedback_post')
    op.drop_index('idx_publish_jobs_status_next_run')
    op.drop_index('idx_content_calendar_location_month')
    op.drop_index('idx_recommendations_status')
    op.drop_index('idx_recommendations_location_week')
    
    # Drop tables
    op.drop_table('brand_voice_profiles')
    op.drop_table('post_feedback')
    op.drop_table('rejection_reason_codes')
    op.drop_table('rate_limit_tracker')
    op.drop_table('platform_tokens')
    op.drop_table('publish_jobs')
    op.drop_table('content_usage_history')
    op.drop_table('content_calendar')
    op.drop_table('autopilot_settings')
    op.drop_table('performance_tracking')
    op.drop_table('recommendations')
