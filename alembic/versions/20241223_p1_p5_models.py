"""P1-P5 Models: Metrics, Review Booster, Calls, OAuth, Vault

Revision ID: 20241223_p1_p5
Revises: 
Create Date: 2024-12-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20241223_p1_p5'
down_revision: Union[str, None] = None  # Update this to your latest migration
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ====================
    # P1: Metrics Tables
    # ====================
    
    # metric_snapshots
    op.create_table(
        'metric_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('snapshot_date', sa.Date(), nullable=False, index=True),
        sa.Column('snapshot_type', sa.Enum('daily', 'weekly', 'monthly', name='snapshottype'), nullable=False),
        sa.Column('calls', sa.Integer(), default=0, nullable=False),
        sa.Column('directions', sa.Integer(), default=0, nullable=False),
        sa.Column('website_clicks', sa.Integer(), default=0, nullable=False),
        sa.Column('profile_views', sa.Integer(), default=0, nullable=False),
        sa.Column('photo_views', sa.Integer(), default=0, nullable=False),
        sa.Column('total_reviews', sa.Integer(), default=0, nullable=False),
        sa.Column('new_reviews', sa.Integer(), default=0, nullable=False),
        sa.Column('avg_rating', sa.Numeric(2, 1), nullable=True),
        sa.Column('calls_delta', sa.Integer(), nullable=True),
        sa.Column('directions_delta', sa.Integer(), nullable=True),
        sa.Column('website_clicks_delta', sa.Integer(), nullable=True),
        sa.Column('attributed_post_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column('call_value', sa.Numeric(10, 2), default=50.00, nullable=False),
        sa.Column('raw_data', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('location_id', 'snapshot_date', 'snapshot_type', name='uq_metric_snapshot_unique'),
    )
    
    # utm_links
    op.create_table(
        'utm_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('posts.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('original_url', sa.Text(), nullable=False),
        sa.Column('utm_url', sa.Text(), nullable=False),
        sa.Column('utm_source', sa.String(50), default='gbp', nullable=False),
        sa.Column('utm_medium', sa.String(50), default='post', nullable=False),
        sa.Column('utm_campaign', sa.String(100), nullable=True),
        sa.Column('utm_content', sa.String(100), nullable=True),
        sa.Column('clicks', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # weekly_reports
    op.create_table(
        'weekly_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('report_week', sa.Date(), nullable=False),
        sa.Column('report_type', sa.String(20), default='weekly', nullable=False),
        sa.Column('current_snapshot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('metric_snapshots.id'), nullable=True),
        sa.Column('previous_snapshot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('metric_snapshots.id'), nullable=True),
        sa.Column('summary', postgresql.JSONB(), nullable=False),
        sa.Column('pdf_url', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_to', postgresql.ARRAY(sa.String(255)), nullable=True),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('location_id', 'report_week', 'report_type', name='uq_weekly_report_unique'),
    )
    
    # ====================
    # P2: Review Booster Tables
    # ====================
    
    # review_campaigns
    op.create_table(
        'review_campaigns',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('status', sa.Enum('active', 'paused', 'completed', name='campaignstatus'), default='active', nullable=False),
        sa.Column('sms_template', sa.Text(), nullable=True),
        sa.Column('email_template', sa.Text(), nullable=True),
        sa.Column('email_subject', sa.String(200), nullable=True),
        sa.Column('delay_hours', sa.Integer(), default=24, nullable=False),
        sa.Column('channels', postgresql.ARRAY(sa.String(10)), default=['sms'], nullable=False),
        sa.Column('google_review_url', sa.Text(), nullable=False),
        sa.Column('private_feedback_url', sa.Text(), nullable=True),
        sa.Column('total_sent', sa.Integer(), default=0, nullable=False),
        sa.Column('total_clicked', sa.Integer(), default=0, nullable=False),
        sa.Column('total_reviews_estimated', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # booster_requests
    op.create_table(
        'booster_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('review_campaigns.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('customer_name', sa.String(200), nullable=True),
        sa.Column('customer_phone', sa.String(20), nullable=True),
        sa.Column('customer_email', sa.String(200), nullable=True),
        sa.Column('consent_given', sa.Boolean(), nullable=False),
        sa.Column('consent_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('consent_method', sa.String(50), nullable=True),
        sa.Column('channel', sa.Enum('sms', 'email', name='requestchannel'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'sent', 'delivered', 'failed', 'opted_out', name='requeststatus'), default='pending', nullable=False),
        sa.Column('message_content', sa.Text(), nullable=False),
        sa.Column('google_link_included', sa.Boolean(), default=True, nullable=False),
        sa.Column('feedback_link_included', sa.Boolean(), default=False, nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('google_link_clicked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('feedback_link_clicked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('opted_out_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('twilio_message_sid', sa.String(100), nullable=True),
        sa.Column('sendgrid_message_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('google_link_included = TRUE', name='compliance_google_link'),
    )
    
    # review_optouts
    op.create_table(
        'review_optouts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('email', sa.String(200), nullable=True),
        sa.Column('opted_out_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('reason', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('location_id', 'phone', name='uq_optout_phone'),
        sa.UniqueConstraint('location_id', 'email', name='uq_optout_email'),
    )
    
    # private_feedbacks
    op.create_table(
        'private_feedbacks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('booster_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('booster_requests.id', ondelete='SET NULL'), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('feedback_text', sa.Text(), nullable=True),
        sa.Column('customer_name', sa.String(200), nullable=True),
        sa.Column('customer_contact', sa.String(200), nullable=True),
        sa.Column('status', sa.Enum('new', 'in_progress', 'resolved', 'closed', name='feedbackstatus'), default='new', nullable=False),
        sa.Column('assigned_to', postgresql.UUID(as_uuid=True), sa.ForeignKey('accounts.id'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # ====================
    # P3: Calls Tables
    # ====================
    
    # twilio_numbers
    op.create_table(
        'twilio_numbers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('twilio_number', sa.String(20), unique=True, nullable=False),
        sa.Column('forward_to', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), default='active', nullable=False),
        sa.Column('missed_call_sms_enabled', sa.Boolean(), default=True, nullable=False),
        sa.Column('sms_template', sa.Text(), nullable=False),
        sa.Column('total_calls', sa.Integer(), default=0, nullable=False),
        sa.Column('missed_calls', sa.Integer(), default=0, nullable=False),
        sa.Column('sms_sent', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # sms_threads (create before call_logs due to FK)
    op.create_table(
        'sms_threads',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('customer_phone', sa.String(20), nullable=False, index=True),
        sa.Column('twilio_number', sa.String(20), nullable=False),
        sa.Column('status', sa.Enum('open', 'closed', 'spam', name='threadstatus'), default='open', nullable=False),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('unread_count', sa.Integer(), default=0, nullable=False),
        sa.Column('tags', postgresql.ARRAY(sa.String(50)), default=[], nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('location_id', 'customer_phone', 'twilio_number', name='uq_sms_thread'),
    )
    
    # call_logs
    op.create_table(
        'call_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('twilio_number_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('twilio_numbers.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('twilio_call_sid', sa.String(100), unique=True, nullable=False),
        sa.Column('caller_number', sa.String(20), nullable=False, index=True),
        sa.Column('call_status', sa.String(20), nullable=False),
        sa.Column('call_duration', sa.Integer(), default=0, nullable=False),
        sa.Column('sms_sent', sa.Boolean(), default=False, nullable=False),
        sa.Column('sms_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sms_message_sid', sa.String(100), nullable=True),
        sa.Column('thread_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sms_threads.id', ondelete='SET NULL'), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.String(50)), default=[], nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # sms_messages
    op.create_table(
        'sms_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('thread_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sms_threads.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('direction', sa.Enum('inbound', 'outbound', name='messagedirection'), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('twilio_message_sid', sa.String(100), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # ====================
    # P4: OAuth Tables
    # ====================
    
    # oauth_tokens
    op.create_table(
        'oauth_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('provider', sa.Enum('google', 'instagram', 'facebook', name='oauthprovider'), nullable=False),
        sa.Column('access_token_ref', sa.String(200), nullable=False),
        sa.Column('refresh_token_ref', sa.String(200), nullable=True),
        sa.Column('scopes', postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.Enum('healthy', 'needs_reauth', 'degraded', 'revoked', name='oauthstatus'), default='healthy', nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_refresh_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_error_code', sa.String(50), nullable=True),
        sa.Column('refresh_failure_count', sa.Integer(), default=0, nullable=False),
        sa.Column('next_refresh_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('account_id', 'location_id', 'provider', name='uq_oauth_token'),
    )
    
    # oauth_events
    op.create_table(
        'oauth_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('token_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('oauth_tokens.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('event_type', sa.Enum('created', 'refreshed', 'refresh_failed', 'revoked', 'reauthorized', 'used', 'scopes_changed', name='oautheventtype'), nullable=False),
        sa.Column('event_data', postgresql.JSONB(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # ====================
    # P5: Vault Tables
    # ====================
    
    # entity_vaults
    op.create_table(
        'entity_vaults',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), unique=True, nullable=False, index=True),
        sa.Column('business_name', sa.String(200), nullable=False),
        sa.Column('tagline', sa.String(200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('services', postgresql.JSONB(), default=[], nullable=False),
        sa.Column('price_range', sa.String(50), nullable=True),
        sa.Column('tone', sa.String(50), default='professional_friendly', nullable=False),
        sa.Column('forbidden_phrases', postgresql.ARRAY(sa.String(100)), default=[], nullable=False),
        sa.Column('required_phrases', postgresql.ARRAY(sa.String(100)), default=[], nullable=False),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(50), nullable=True),
        sa.Column('zip_code', sa.String(20), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('website', sa.String(200), nullable=True),
        sa.Column('faq', postgresql.JSONB(), default=[], nullable=False),
        sa.Column('primary_keywords', postgresql.ARRAY(sa.String(100)), default=[], nullable=False),
        sa.Column('secondary_keywords', postgresql.ARRAY(sa.String(100)), default=[], nullable=False),
        sa.Column('local_keywords', postgresql.ARRAY(sa.String(100)), default=[], nullable=False),
        sa.Column('compliance_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # approval_analyses
    op.create_table(
        'approval_analyses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('post_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('posts.id', ondelete='CASCADE'), unique=True, nullable=False, index=True),
        sa.Column('risk_score', sa.Integer(), default=0, nullable=False),
        sa.Column('risk_flags', postgresql.JSONB(), default=[], nullable=False),
        sa.Column('keyword_score', sa.Integer(), default=0, nullable=False),
        sa.Column('keywords_found', postgresql.ARRAY(sa.String(100)), default=[], nullable=False),
        sa.Column('keywords_missing', postgresql.ARRAY(sa.String(100)), default=[], nullable=False),
        sa.Column('tone_match_score', sa.Integer(), default=0, nullable=False),
        sa.Column('forbidden_found', postgresql.ARRAY(sa.String(100)), default=[], nullable=False),
        sa.Column('suggestions', postgresql.JSONB(), default=[], nullable=False),
        sa.Column('vault_version_used', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('approval_analyses')
    op.drop_table('entity_vaults')
    op.drop_table('oauth_events')
    op.drop_table('oauth_tokens')
    op.drop_table('sms_messages')
    op.drop_table('call_logs')
    op.drop_table('sms_threads')
    op.drop_table('twilio_numbers')
    op.drop_table('private_feedbacks')
    op.drop_table('review_optouts')
    op.drop_table('booster_requests')
    op.drop_table('review_campaigns')
    op.drop_table('weekly_reports')
    op.drop_table('utm_links')
    op.drop_table('metric_snapshots')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS snapshottype')
    op.execute('DROP TYPE IF EXISTS campaignstatus')
    op.execute('DROP TYPE IF EXISTS requestchannel')
    op.execute('DROP TYPE IF EXISTS requeststatus')
    op.execute('DROP TYPE IF EXISTS feedbackstatus')
    op.execute('DROP TYPE IF EXISTS threadstatus')
    op.execute('DROP TYPE IF EXISTS messagedirection')
    op.execute('DROP TYPE IF EXISTS oauthprovider')
    op.execute('DROP TYPE IF EXISTS oauthstatus')
    op.execute('DROP TYPE IF EXISTS oautheventtype')
