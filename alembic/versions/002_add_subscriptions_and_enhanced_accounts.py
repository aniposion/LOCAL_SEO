"""Add subscriptions and enhanced accounts

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to accounts table
    op.add_column('accounts', sa.Column('full_name', sa.String(255), nullable=True))
    op.add_column('accounts', sa.Column('company_name', sa.String(255), nullable=True))
    op.add_column('accounts', sa.Column('phone', sa.String(50), nullable=True))
    op.add_column('accounts', sa.Column('timezone', sa.String(50), nullable=False, server_default='UTC'))
    op.add_column('accounts', sa.Column('language', sa.String(10), nullable=False, server_default='en'))
    op.add_column('accounts', sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('accounts', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('accounts', sa.Column('verification_token', sa.String(255), nullable=True))
    op.add_column('accounts', sa.Column('password_reset_token', sa.String(255), nullable=True))
    op.add_column('accounts', sa.Column('password_reset_expires', sa.DateTime(timezone=True), nullable=True))
    op.add_column('accounts', sa.Column('terms_accepted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('accounts', sa.Column('privacy_accepted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('accounts', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('accounts', sa.Column('last_login_ip', sa.String(50), nullable=True))

    # Add ADMIN to account role enum
    op.execute("ALTER TYPE accountrole ADD VALUE IF NOT EXISTS 'ADMIN'")

    # Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_type', sa.Enum('FREE', 'STARTER', 'PRO', 'AGENCY', 'ENTERPRISE', name='plantype'), nullable=False, server_default='FREE'),
        sa.Column('status', sa.Enum('ACTIVE', 'CANCELED', 'PAST_DUE', 'TRIALING', 'PAUSED', 'EXPIRED', name='subscriptionstatus'), nullable=False, server_default='ACTIVE'),
        sa.Column('stripe_customer_id', sa.String(255), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(255), nullable=True),
        sa.Column('stripe_price_id', sa.String(255), nullable=True),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('locations_limit', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('posts_per_month', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('api_calls_per_day', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('trial_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('account_id'),
    )
    op.create_index('ix_subscriptions_account_id', 'subscriptions', ['account_id'])
    op.create_index('ix_subscriptions_stripe_customer_id', 'subscriptions', ['stripe_customer_id'])

    # Create payment_history table
    op.create_table(
        'payment_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stripe_payment_intent_id', sa.String(255), nullable=True),
        sa.Column('stripe_invoice_id', sa.String(255), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('invoice_url', sa.String(500), nullable=True),
        sa.Column('receipt_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_payment_history_account_id', 'payment_history', ['account_id'])

    # Update channels table
    op.add_column('channels', sa.Column('status', sa.Enum('PENDING', 'CONNECTED', 'DISCONNECTED', 'ERROR', 'EXPIRED', name='channelstatus'), nullable=False, server_default='PENDING'))
    op.add_column('channels', sa.Column('credentials_encrypted', sa.Text(), nullable=True))
    op.add_column('channels', sa.Column('platform_account_id', sa.String(255), nullable=True))
    op.add_column('channels', sa.Column('platform_account_name', sa.String(255), nullable=True))
    op.add_column('channels', sa.Column('access_token_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('channels', sa.Column('refresh_token_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('channels', sa.Column('scopes', postgresql.JSONB(), nullable=True))
    op.add_column('channels', sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'))

    # Add new channel types
    op.execute("ALTER TYPE channeltype ADD VALUE IF NOT EXISTS 'FACEBOOK'")
    op.execute("ALTER TYPE channeltype ADD VALUE IF NOT EXISTS 'TWITTER'")

    # Drop old credentials column (migrate data first in production)
    op.drop_column('channels', 'credentials')

    # Change last_sync_at to DateTime
    op.alter_column('channels', 'last_sync_at', type_=sa.DateTime(timezone=True), postgresql_using='last_sync_at::timestamp with time zone')


def downgrade() -> None:
    # Revert channels changes
    op.add_column('channels', sa.Column('credentials', postgresql.JSONB(), nullable=True))
    op.drop_column('channels', 'credentials_encrypted')
    op.drop_column('channels', 'status')
    op.drop_column('channels', 'platform_account_id')
    op.drop_column('channels', 'platform_account_name')
    op.drop_column('channels', 'access_token_expires_at')
    op.drop_column('channels', 'refresh_token_expires_at')
    op.drop_column('channels', 'scopes')
    op.drop_column('channels', 'error_count')

    # Drop payment_history
    op.drop_table('payment_history')

    # Drop subscriptions
    op.drop_table('subscriptions')

    # Remove account columns
    op.drop_column('accounts', 'full_name')
    op.drop_column('accounts', 'company_name')
    op.drop_column('accounts', 'phone')
    op.drop_column('accounts', 'timezone')
    op.drop_column('accounts', 'language')
    op.drop_column('accounts', 'is_verified')
    op.drop_column('accounts', 'email_verified_at')
    op.drop_column('accounts', 'verification_token')
    op.drop_column('accounts', 'password_reset_token')
    op.drop_column('accounts', 'password_reset_expires')
    op.drop_column('accounts', 'terms_accepted_at')
    op.drop_column('accounts', 'privacy_accepted_at')
    op.drop_column('accounts', 'last_login_at')
    op.drop_column('accounts', 'last_login_ip')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS plantype')
    op.execute('DROP TYPE IF EXISTS subscriptionstatus')
    op.execute('DROP TYPE IF EXISTS channelstatus')
