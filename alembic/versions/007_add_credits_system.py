"""Add credits system tables

Revision ID: 007
Revises: 006
Create Date: 2024-12-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # CREDIT BALANCES
    # =========================================================================
    
    op.create_table(
        'credit_balances',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
        
        # Current balance
        sa.Column('balance', sa.Integer, default=0, nullable=False),
        sa.Column('bonus_balance', sa.Integer, default=0, nullable=False),
        
        # Monthly allocation tracking
        sa.Column('monthly_allocation', sa.Integer, default=0, nullable=False),
        sa.Column('last_allocation_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_allocation_date', sa.DateTime(timezone=True), nullable=True),
        
        # Lifetime stats
        sa.Column('total_credits_received', sa.Integer, default=0, nullable=False),
        sa.Column('total_credits_used', sa.Integer, default=0, nullable=False),
        sa.Column('total_credits_purchased', sa.Integer, default=0, nullable=False),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    # =========================================================================
    # CREDIT TRANSACTIONS
    # =========================================================================
    
    # Create enum for transaction types
    op.execute("""
        CREATE TYPE credittransactiontype AS ENUM (
            'monthly_allocation', 'purchase', 'bonus', 'refund', 'admin_grant',
            'sms_usage', 'ai_content_usage', 'ai_image_usage', 'ai_response_usage', 'overage_charge'
        )
    """)
    
    op.create_table(
        'credit_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True),
        
        # Transaction details
        sa.Column('type', postgresql.ENUM('monthly_allocation', 'purchase', 'bonus', 'refund', 'admin_grant',
                                          'sms_usage', 'ai_content_usage', 'ai_image_usage', 'ai_response_usage', 'overage_charge',
                                          name='credittransactiontype', create_type=False), nullable=False),
        sa.Column('amount', sa.Integer, nullable=False),
        sa.Column('balance_after', sa.Integer, nullable=False),
        
        # Description
        sa.Column('description', sa.String(500), nullable=True),
        
        # Reference
        sa.Column('reference_type', sa.String(50), nullable=True),
        sa.Column('reference_id', sa.String(255), nullable=True),
        
        # Admin
        sa.Column('admin_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    # =========================================================================
    # USAGE RECORDS
    # =========================================================================
    
    op.create_table(
        'usage_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True),
        
        # Usage type
        sa.Column('usage_type', sa.String(50), nullable=False),
        
        # Date tracking
        sa.Column('date', sa.DateTime(timezone=True), nullable=False),
        
        # Counts
        sa.Column('daily_count', sa.Integer, default=0, nullable=False),
        sa.Column('monthly_count', sa.Integer, default=0, nullable=False),
        
        # Last usage timestamp
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )
    
    # =========================================================================
    # INDEXES
    # =========================================================================
    
    op.create_index('idx_credit_transactions_account_date', 'credit_transactions', ['account_id', 'created_at'])
    op.create_index('idx_credit_transactions_type', 'credit_transactions', ['type'])
    op.create_index('idx_usage_records_account_type_date', 'usage_records', ['account_id', 'usage_type', 'date'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_usage_records_account_type_date')
    op.drop_index('idx_credit_transactions_type')
    op.drop_index('idx_credit_transactions_account_date')
    
    # Drop tables
    op.drop_table('usage_records')
    op.drop_table('credit_transactions')
    op.drop_table('credit_balances')
    
    # Drop enum
    op.execute('DROP TYPE IF EXISTS credittransactiontype')
