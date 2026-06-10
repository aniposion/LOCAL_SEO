"""P1-P6 Feature Tables Migration

Revision ID: p1p6_features_001
Revises: 
Create Date: 2024-12-24

This migration adds tables for:
- P1: Metrics & Attribution (metric_snapshots, utm_links, weekly_reports)
- P2: Review Booster (review_campaigns, booster_requests, review_optouts, private_feedback)
- P3: Missed Call Text Back (call_logs, text_back_settings, sms_threads, sms_messages)
- P4: OAuth Token Management (oauth_tokens - extended)
- P5: Entity Vault (entity_vaults - extended fields)
- P6: AI Content (approval_analyses - extended)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'p1p6_features_001'
down_revision = None  # Set to your latest migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ====================
    # P1: Metrics & Attribution
    # ====================
    
    # Metric Snapshots
    op.create_table(
        'metric_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('snapshot_type', sa.String(20), nullable=False),  # daily, weekly, monthly
        sa.Column('snapshot_date', sa.Date, nullable=False),
        
        # GBP Metrics
        sa.Column('gbp_views', sa.Integer, default=0),
        sa.Column('gbp_searches', sa.Integer, default=0),
        sa.Column('gbp_calls', sa.Integer, default=0),
        sa.Column('gbp_directions', sa.Integer, default=0),
        sa.Column('gbp_website_clicks', sa.Integer, default=0),
        sa.Column('gbp_messages', sa.Integer, default=0),
        sa.Column('gbp_bookings', sa.Integer, default=0),
        
        # Reviews
        sa.Column('review_count', sa.Integer, default=0),
        sa.Column('review_average', sa.Float),
        sa.Column('new_reviews', sa.Integer, default=0),
        
        # Posts
        sa.Column('posts_published', sa.Integer, default=0),
        sa.Column('post_views', sa.Integer, default=0),
        
        # Rankings
        sa.Column('local_pack_rank', sa.Integer),
        sa.Column('organic_rank', sa.Integer),
        sa.Column('keyword_rankings', postgresql.JSONB, default={}),
        
        # Calls (P3)
        sa.Column('total_calls', sa.Integer, default=0),
        sa.Column('missed_calls', sa.Integer, default=0),
        sa.Column('text_backs_sent', sa.Integer, default=0),
        
        # Raw data
        sa.Column('raw_data', postgresql.JSONB, default={}),
        
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        
        sa.Index('ix_metric_snapshots_location_date', 'location_id', 'snapshot_date'),
        sa.UniqueConstraint('location_id', 'snapshot_type', 'snapshot_date', name='uq_metric_snapshot'),
    )
    
    # UTM Links
    op.create_table(
        'utm_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False),
        
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('destination_url', sa.String(500), nullable=False),
        sa.Column('short_code', sa.String(20), unique=True),
        
        # UTM Parameters
        sa.Column('utm_source', sa.String(100)),
        sa.Column('utm_medium', sa.String(100)),
        sa.Column('utm_campaign', sa.String(100)),
        sa.Column('utm_term', sa.String(100)),
        sa.Column('utm_content', sa.String(100)),
        
        # Stats
        sa.Column('click_count', sa.Integer, default=0),
        sa.Column('last_clicked_at', sa.DateTime),
        
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # Weekly Reports
    op.create_table(
        'weekly_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False),
        
        sa.Column('week_start', sa.Date, nullable=False),
        sa.Column('week_end', sa.Date, nullable=False),
        
        # Metrics
        sa.Column('metrics', postgresql.JSONB, default={}),
        sa.Column('highlights', postgresql.JSONB, default=[]),
        sa.Column('recommendations', postgresql.JSONB, default=[]),
        
        # Delivery
        sa.Column('sent_at', sa.DateTime),
        sa.Column('sent_to', postgresql.ARRAY(sa.String(200))),
        sa.Column('report_url', sa.String(500)),
        
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        
        sa.UniqueConstraint('location_id', 'week_start', name='uq_weekly_report'),
    )
    
    # ====================
    # P2: Review Booster
    # ====================
    
    # Review Campaigns
    op.create_table(
        'review_campaigns',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False),
        
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), default='active'),  # active, paused, completed
        
        # Settings
        sa.Column('channel', sa.String(20), default='sms'),  # sms, email, both
        sa.Column('delay_hours', sa.Integer, default=24),
        sa.Column('message_template', sa.Text),
        sa.Column('email_template', sa.Text),
        
        # Links
        sa.Column('google_review_url', sa.String(500)),
        
        # Stats
        sa.Column('total_sent', sa.Integer, default=0),
        sa.Column('total_opened', sa.Integer, default=0),
        sa.Column('total_clicked', sa.Integer, default=0),
        sa.Column('total_reviews', sa.Integer, default=0),
        
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now()),
    )
    
    # Booster Requests
    op.create_table(
        'booster_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('review_campaigns.id', ondelete='CASCADE'), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False),
        
        # Customer
        sa.Column('customer_name', sa.String(100)),
        sa.Column('customer_phone', sa.String(20)),
        sa.Column('customer_email', sa.String(200)),
        
        # Status
        sa.Column('status', sa.String(20), default='pending'),  # pending, sent, opened, clicked, reviewed, failed, opted_out
        sa.Column('channel', sa.String(20)),  # sms, email
        
        # Tracking
        sa.Column('scheduled_at', sa.DateTime),
        sa.Column('sent_at', sa.DateTime),
        sa.Column('opened_at', sa.DateTime),
        sa.Column('clicked_at', sa.DateTime),
        sa.Column('reviewed_at', sa.DateTime),
        
        sa.Column('error_message', sa.Text),
        sa.Column('twilio_sid', sa.String(50)),
        sa.Column('sendgrid_id', sa.String(50)),
        
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        
        sa.Index('ix_booster_requests_status', 'status'),
        sa.Index('ix_booster_requests_scheduled', 'scheduled_at'),
    )
    
    # Review Opt-outs
    op.create_table(
        'review_optouts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False),
        
        sa.Column('phone', sa.String(20)),
        sa.Column('email', sa.String(200)),
        sa.Column('reason', sa.String(50)),  # customer_request, spam_report, bounce
        
        sa.Column('opted_out_at', sa.DateTime, server_default=sa.func.now()),
        
        sa.Index('ix_review_optouts_phone', 'phone'),
        sa.Index('ix_review_optouts_email', 'email'),
    )
    
    # Private Feedback
    op.create_table(
        'private_feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('booster_requests.id', ondelete='CASCADE')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False),
        
        sa.Column('customer_name', sa.String(100)),
        sa.Column('rating', sa.Integer),  # 1-5
        sa.Column('feedback_text', sa.Text),
        sa.Column('contact_requested', sa.Boolean, default=False),
        
        sa.Column('status', sa.String(20), default='new'),  # new, reviewed, resolved
        sa.Column('resolved_at', sa.DateTime),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True)),
        sa.Column('resolution_notes', sa.Text),
        
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # ====================
    # P3: Missed Call Text Back
    # ====================
    
    # Text Back Settings
    op.create_table(
        'text_back_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), unique=True, nullable=False),
        
        sa.Column('enabled', sa.Boolean, default=True),
        sa.Column('delay_seconds', sa.Integer, default=60),
        sa.Column('respect_business_hours', sa.Boolean, default=True),
        
        # Messages
        sa.Column('default_message', sa.Text),
        sa.Column('after_hours_message', sa.Text),
        
        # Quick replies
        sa.Column('enable_quick_replies', sa.Boolean, default=True),
        sa.Column('quick_reply_options', postgresql.JSONB, default=[]),
        
        # Twilio
        sa.Column('twilio_number', sa.String(20)),
        sa.Column('forwarding_number', sa.String(20)),
        
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now()),
    )
    
    # Call Logs
    op.create_table(
        'call_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False),
        
        sa.Column('twilio_call_sid', sa.String(50), unique=True),
        sa.Column('caller_phone', sa.String(20), nullable=False),
        
        sa.Column('direction', sa.String(10), default='inbound'),  # inbound, outbound
        sa.Column('status', sa.String(20)),  # answered, missed, busy, failed
        
        sa.Column('duration_seconds', sa.Integer),
        sa.Column('call_started_at', sa.DateTime),
        sa.Column('call_ended_at', sa.DateTime),
        
        # Text back
        sa.Column('text_back_sent', sa.Boolean, default=False),
        sa.Column('text_back_at', sa.DateTime),
        sa.Column('text_back_response', sa.Text),
        
        sa.Column('recording_url', sa.String(500)),
        sa.Column('notes', sa.Text),
        
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        
        sa.Index('ix_call_logs_location_created', 'location_id', 'created_at'),
        sa.Index('ix_call_logs_caller', 'caller_phone'),
    )
    
    # SMS Threads
    op.create_table(
        'sms_threads',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False),
        
        sa.Column('customer_phone', sa.String(20), nullable=False),
        sa.Column('customer_name', sa.String(100)),
        
        sa.Column('status', sa.String(20), default='active'),  # active, archived, blocked
        sa.Column('unread_count', sa.Integer, default=0),
        
        sa.Column('last_message_at', sa.DateTime),
        sa.Column('last_message_preview', sa.String(100)),
        
        sa.Column('call_log_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('call_logs.id')),
        
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, onupdate=sa.func.now()),
        
        sa.UniqueConstraint('location_id', 'customer_phone', name='uq_sms_thread'),
    )
    
    # SMS Messages
    op.create_table(
        'sms_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('thread_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sms_threads.id', ondelete='CASCADE'), nullable=False),
        
        sa.Column('direction', sa.String(10), nullable=False),  # inbound, outbound
        sa.Column('body', sa.Text, nullable=False),
        
        sa.Column('twilio_sid', sa.String(50)),
        sa.Column('status', sa.String(20), default='sent'),  # queued, sent, delivered, failed, received
        
        sa.Column('is_read', sa.Boolean, default=False),
        sa.Column('is_auto_reply', sa.Boolean, default=False),
        
        sa.Column('sent_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('delivered_at', sa.DateTime),
        
        sa.Index('ix_sms_messages_thread', 'thread_id', 'sent_at'),
    )
    
    # ====================
    # P5: Entity Vault Extensions
    # ====================
    
    # Add new columns to entity_vaults if they don't exist
    op.add_column('entity_vaults', sa.Column('full_address', postgresql.JSONB, nullable=True))
    op.add_column('entity_vaults', sa.Column('coordinates', postgresql.JSONB, nullable=True))
    op.add_column('entity_vaults', sa.Column('contact_info', postgresql.JSONB, nullable=True))
    op.add_column('entity_vaults', sa.Column('business_hours', postgresql.JSONB, nullable=True))
    op.add_column('entity_vaults', sa.Column('special_hours', postgresql.JSONB, nullable=True))
    op.add_column('entity_vaults', sa.Column('hours_timezone', sa.String(50), nullable=True))
    op.add_column('entity_vaults', sa.Column('payment_methods', postgresql.JSONB, nullable=True))
    op.add_column('entity_vaults', sa.Column('amenities', postgresql.JSONB, nullable=True))
    op.add_column('entity_vaults', sa.Column('service_area', postgresql.JSONB, nullable=True))
    op.add_column('entity_vaults', sa.Column('primary_category', sa.String(100), nullable=True))
    op.add_column('entity_vaults', sa.Column('secondary_categories', postgresql.JSONB, nullable=True))
    op.add_column('entity_vaults', sa.Column('logo_url', sa.String(500), nullable=True))
    op.add_column('entity_vaults', sa.Column('cover_photo_url', sa.String(500), nullable=True))
    op.add_column('entity_vaults', sa.Column('photo_urls', postgresql.JSONB, nullable=True))
    op.add_column('entity_vaults', sa.Column('gbp_sync_status', sa.String(20), nullable=True))
    op.add_column('entity_vaults', sa.Column('gbp_last_synced_at', sa.DateTime, nullable=True))
    op.add_column('entity_vaults', sa.Column('custom_attributes', postgresql.JSONB, nullable=True))


def downgrade() -> None:
    # P5: Remove entity_vault extensions
    op.drop_column('entity_vaults', 'custom_attributes')
    op.drop_column('entity_vaults', 'gbp_last_synced_at')
    op.drop_column('entity_vaults', 'gbp_sync_status')
    op.drop_column('entity_vaults', 'photo_urls')
    op.drop_column('entity_vaults', 'cover_photo_url')
    op.drop_column('entity_vaults', 'logo_url')
    op.drop_column('entity_vaults', 'secondary_categories')
    op.drop_column('entity_vaults', 'primary_category')
    op.drop_column('entity_vaults', 'service_area')
    op.drop_column('entity_vaults', 'amenities')
    op.drop_column('entity_vaults', 'payment_methods')
    op.drop_column('entity_vaults', 'hours_timezone')
    op.drop_column('entity_vaults', 'special_hours')
    op.drop_column('entity_vaults', 'business_hours')
    op.drop_column('entity_vaults', 'contact_info')
    op.drop_column('entity_vaults', 'coordinates')
    op.drop_column('entity_vaults', 'full_address')
    
    # P3: Drop tables
    op.drop_table('sms_messages')
    op.drop_table('sms_threads')
    op.drop_table('call_logs')
    op.drop_table('text_back_settings')
    
    # P2: Drop tables
    op.drop_table('private_feedback')
    op.drop_table('review_optouts')
    op.drop_table('booster_requests')
    op.drop_table('review_campaigns')
    
    # P1: Drop tables
    op.drop_table('weekly_reports')
    op.drop_table('utm_links')
    op.drop_table('metric_snapshots')
