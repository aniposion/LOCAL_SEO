"""Add P1 features - Review Booster, Call Leads, Support Tickets

Revision ID: 006
Revises: 005
Create Date: 2024-12-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # REVIEW BOOSTER (P1-4)
    # =========================================================================
    
    op.create_table(
        'review_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        
        # Customer info
        sa.Column('customer_name', sa.String(200), nullable=True),
        sa.Column('customer_phone', sa.String(50), nullable=True),
        sa.Column('customer_email', sa.String(200), nullable=True),
        
        # Delivery
        sa.Column('channel', sa.String(20), default='sms'),
        
        # Tracking timestamps
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('clicked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rating_gate_at', sa.DateTime(timezone=True), nullable=True),
        
        # Gate results
        sa.Column('gate_rating', sa.Integer, nullable=True),
        sa.Column('gate_sentiment', sa.String(20), nullable=True),
        
        # Conversion
        sa.Column('google_review_clicked', sa.Boolean, default=False),
        sa.Column('google_review_submitted', sa.Boolean, default=False),
        sa.Column('internal_feedback_submitted', sa.Boolean, default=False),
        
        # Resolution
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('support_ticket_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Metadata
        sa.Column('visit_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('service_type', sa.String(100), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    # =========================================================================
    # SUPPORT TICKETS (P1-4)
    # =========================================================================
    
    op.create_table(
        'support_tickets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        
        # Source
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Customer info
        sa.Column('customer_name', sa.String(200), nullable=True),
        sa.Column('customer_contact', sa.String(200), nullable=True),
        
        # Issue
        sa.Column('issue_category', sa.String(30), nullable=True),
        sa.Column('issue_description', sa.Text, nullable=True),
        sa.Column('original_rating', sa.Integer, nullable=True),
        
        # Status
        sa.Column('status', sa.String(30), default='open'),
        sa.Column('priority', sa.Integer, default=2),
        
        # Resolution
        sa.Column('resolution_type', sa.String(30), nullable=True),
        sa.Column('resolution_notes', sa.Text, nullable=True),
        
        # Follow-up
        sa.Column('coupon_sent', sa.Boolean, default=False),
        sa.Column('coupon_code', sa.String(50), nullable=True),
        sa.Column('callback_scheduled', sa.Boolean, default=False),
        sa.Column('callback_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('callback_completed', sa.Boolean, default=False),
        
        # Assignment
        sa.Column('assigned_to', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    # =========================================================================
    # CALL LEADS (P1-5)
    # =========================================================================
    
    op.create_table(
        'call_leads',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, index=True),
        
        # Call info
        sa.Column('caller_phone', sa.String(50), nullable=False),
        sa.Column('call_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('call_status', sa.String(30), nullable=False),
        sa.Column('call_duration', sa.Integer, nullable=True),
        
        # SMS
        sa.Column('sms_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sms_template_used', sa.String(50), nullable=True),
        sa.Column('sms_content', sa.Text, nullable=True),
        
        # Customer response
        sa.Column('customer_replied', sa.Boolean, default=False),
        sa.Column('customer_reply_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('customer_reply_text', sa.Text, nullable=True),
        
        # Intent classification
        sa.Column('intent', sa.String(30), nullable=True),
        sa.Column('intent_confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('intent_raw', postgresql.JSONB, nullable=True),
        
        # Follow-up
        sa.Column('followup_type', sa.String(30), nullable=True),
        sa.Column('followup_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('followup_content', sa.Text, nullable=True),
        
        # Conversion tracking
        sa.Column('booking_link_clicked', sa.Boolean, default=False),
        sa.Column('booking_link_clicked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('booking_completed', sa.Boolean, default=False),
        sa.Column('booking_completed_at', sa.DateTime(timezone=True), nullable=True),
        
        # Revenue
        sa.Column('estimated_revenue', sa.Numeric(10, 2), nullable=True),
        sa.Column('actual_revenue', sa.Numeric(10, 2), nullable=True),
        
        # Twilio IDs
        sa.Column('twilio_call_sid', sa.String(50), nullable=True),
        sa.Column('twilio_sms_sid', sa.String(50), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    # =========================================================================
    # INDEXES
    # =========================================================================
    
    op.create_index('idx_review_requests_location_sent', 'review_requests', ['location_id', 'sent_at'])
    op.create_index('idx_review_requests_sentiment', 'review_requests', ['gate_sentiment'])
    op.create_index('idx_support_tickets_location_status', 'support_tickets', ['location_id', 'status'])
    op.create_index('idx_support_tickets_priority', 'support_tickets', ['priority', 'status'])
    op.create_index('idx_call_leads_location_call', 'call_leads', ['location_id', 'call_at'])
    op.create_index('idx_call_leads_intent', 'call_leads', ['intent'])
    op.create_index('idx_call_leads_conversion', 'call_leads', ['booking_completed'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_call_leads_conversion')
    op.drop_index('idx_call_leads_intent')
    op.drop_index('idx_call_leads_location_call')
    op.drop_index('idx_support_tickets_priority')
    op.drop_index('idx_support_tickets_location_status')
    op.drop_index('idx_review_requests_sentiment')
    op.drop_index('idx_review_requests_location_sent')
    
    # Drop tables
    op.drop_table('call_leads')
    op.drop_table('support_tickets')
    op.drop_table('review_requests')
