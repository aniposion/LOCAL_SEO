"""Billing system enhancements - Dunning, Disputes, Refunds, Audit logs.

Revision ID: 2024_12_25_billing
Revises: p1p6_features_001
Create Date: 2024-12-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '2024_12_25_billing'
down_revision = 'p1p6_features_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create subscription_items table
    op.create_table(
        'subscription_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('subscription_id', sa.String(36), sa.ForeignKey('subscriptions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('stripe_subscription_item_id', sa.String(255), unique=True, nullable=False),
        sa.Column('stripe_price_id', sa.String(255), nullable=False),
        sa.Column('stripe_product_id', sa.String(255), nullable=True),
        sa.Column('product_name', sa.String(100), nullable=False),
        sa.Column('quantity', sa.Integer(), default=1),
        sa.Column('unit_amount', sa.Integer(), default=0),
        sa.Column('is_addon', sa.Boolean(), default=False),
        sa.Column('is_base_plan', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('idx_subscription_items_subscription', 'subscription_items', ['subscription_id'])
    op.create_index('idx_subscription_items_stripe', 'subscription_items', ['stripe_subscription_item_id'])

    # Create invoices table
    op.create_table(
        'invoices',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('stripe_invoice_id', sa.String(255), unique=True, nullable=False),
        sa.Column('stripe_subscription_id', sa.String(255), nullable=True),
        sa.Column('stripe_payment_intent_id', sa.String(255), nullable=True),
        sa.Column('stripe_charge_id', sa.String(255), nullable=True),
        sa.Column('number', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), default='draft', nullable=False),
        sa.Column('subtotal', sa.Integer(), default=0),
        sa.Column('tax', sa.Integer(), default=0),
        sa.Column('total', sa.Integer(), nullable=False),
        sa.Column('amount_paid', sa.Integer(), default=0),
        sa.Column('amount_due', sa.Integer(), default=0),
        sa.Column('amount_remaining', sa.Integer(), default=0),
        sa.Column('currency', sa.String(3), default='usd'),
        sa.Column('hosted_invoice_url', sa.Text(), nullable=True),
        sa.Column('invoice_pdf_url', sa.Text(), nullable=True),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('voided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('line_items', sa.JSON(), nullable=True),
        sa.Column('customer_name', sa.String(255), nullable=True),
        sa.Column('customer_email', sa.String(255), nullable=True),
        sa.Column('customer_address', sa.JSON(), nullable=True),
        sa.Column('customer_tax_id', sa.String(50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('footer', sa.Text(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), default=0),
        sa.Column('next_payment_attempt', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('idx_invoices_account', 'invoices', ['account_id'])
    op.create_index('idx_invoices_stripe', 'invoices', ['stripe_invoice_id'])
    op.create_index('idx_invoices_status', 'invoices', ['status'])
    op.create_index('idx_invoices_created', 'invoices', ['created_at'])

    # Create payments table
    op.create_table(
        'payments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('invoice_id', sa.String(36), sa.ForeignKey('invoices.id', ondelete='SET NULL'), nullable=True),
        sa.Column('stripe_payment_intent_id', sa.String(255), unique=True, nullable=True),
        sa.Column('stripe_charge_id', sa.String(255), nullable=True),
        sa.Column('stripe_invoice_id', sa.String(255), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('amount_refunded', sa.Integer(), default=0),
        sa.Column('currency', sa.String(3), default='usd'),
        sa.Column('status', sa.String(50), default='pending', nullable=False),
        sa.Column('payment_method_type', sa.String(50), nullable=True),
        sa.Column('payment_method_last4', sa.String(4), nullable=True),
        sa.Column('payment_method_brand', sa.String(50), nullable=True),
        sa.Column('payment_method_exp_month', sa.Integer(), nullable=True),
        sa.Column('payment_method_exp_year', sa.Integer(), nullable=True),
        sa.Column('failure_code', sa.String(100), nullable=True),
        sa.Column('failure_message', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('receipt_url', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('idx_payments_account', 'payments', ['account_id'])
    op.create_index('idx_payments_invoice', 'payments', ['invoice_id'])
    op.create_index('idx_payments_status', 'payments', ['status'])
    op.create_index('idx_payments_created', 'payments', ['created_at'])

    # Create refunds table
    op.create_table(
        'refunds',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('payment_id', sa.String(36), sa.ForeignKey('payments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('stripe_refund_id', sa.String(255), unique=True, nullable=False),
        sa.Column('stripe_charge_id', sa.String(255), nullable=True),
        sa.Column('stripe_payment_intent_id', sa.String(255), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(3), default='usd'),
        sa.Column('status', sa.String(50), default='pending', nullable=False),
        sa.Column('reason', sa.String(50), nullable=True),
        sa.Column('requested_by_user_id', sa.String(36), sa.ForeignKey('accounts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('request_reason', sa.Text(), nullable=True),
        sa.Column('internal_notes', sa.Text(), nullable=True),
        sa.Column('failure_reason', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('idx_refunds_account', 'refunds', ['account_id'])
    op.create_index('idx_refunds_payment', 'refunds', ['payment_id'])
    op.create_index('idx_refunds_stripe', 'refunds', ['stripe_refund_id'])

    # Create disputes table
    op.create_table(
        'disputes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('payment_id', sa.String(36), sa.ForeignKey('payments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('stripe_dispute_id', sa.String(255), unique=True, nullable=False),
        sa.Column('stripe_charge_id', sa.String(255), nullable=False),
        sa.Column('stripe_payment_intent_id', sa.String(255), nullable=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(3), default='usd'),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('reason', sa.String(50), nullable=True),
        sa.Column('evidence_snapshot', sa.JSON(), nullable=True),
        sa.Column('evidence_due_by', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_charge_refundable', sa.Boolean(), default=False),
        sa.Column('network_reason_code', sa.String(50), nullable=True),
        sa.Column('internal_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('idx_disputes_account', 'disputes', ['account_id'])
    op.create_index('idx_disputes_stripe', 'disputes', ['stripe_dispute_id'])
    op.create_index('idx_disputes_status', 'disputes', ['status'])

    # Create webhook_events_log table
    op.create_table(
        'webhook_events_log',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('stripe_event_id', sa.String(255), unique=True, nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('status', sa.String(50), default='pending', nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('related_account_id', sa.String(36), sa.ForeignKey('accounts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('related_entity_type', sa.String(50), nullable=True),
        sa.Column('related_entity_id', sa.String(255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_traceback', sa.Text(), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_duration_ms', sa.Integer(), nullable=True),
        sa.Column('retry_count', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('idx_webhook_events_stripe', 'webhook_events_log', ['stripe_event_id'])
    op.create_index('idx_webhook_events_type', 'webhook_events_log', ['event_type'])
    op.create_index('idx_webhook_events_status', 'webhook_events_log', ['status'])
    op.create_index('idx_webhook_events_created', 'webhook_events_log', ['created_at'])

    # Create billing_audit_log table
    op.create_table(
        'billing_audit_log',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('accounts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('accounts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=True),
        sa.Column('entity_id', sa.String(255), nullable=True),
        sa.Column('old_value', sa.JSON(), nullable=True),
        sa.Column('new_value', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('idx_billing_audit_account', 'billing_audit_log', ['account_id'])
    op.create_index('idx_billing_audit_action', 'billing_audit_log', ['action'])
    op.create_index('idx_billing_audit_created', 'billing_audit_log', ['created_at'])

    # Create billing_info table
    op.create_table(
        'billing_info',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_id', sa.String(36), sa.ForeignKey('accounts.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('company_name', sa.String(255), nullable=True),
        sa.Column('tax_id', sa.String(50), nullable=True),
        sa.Column('tax_id_type', sa.String(50), nullable=True),
        sa.Column('tax_exempt', sa.Boolean(), default=False),
        sa.Column('address_line1', sa.String(255), nullable=True),
        sa.Column('address_line2', sa.String(255), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(100), nullable=True),
        sa.Column('postal_code', sa.String(20), nullable=True),
        sa.Column('country', sa.String(2), nullable=True),
        sa.Column('billing_email', sa.String(255), nullable=True),
        sa.Column('billing_phone', sa.String(50), nullable=True),
        sa.Column('invoice_footer', sa.Text(), nullable=True),
        sa.Column('preferred_currency', sa.String(3), default='usd'),
        sa.Column('stripe_tax_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('idx_billing_info_account', 'billing_info', ['account_id'])

    # Add dunning columns to subscriptions table
    op.add_column('subscriptions', sa.Column('trial_start', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subscriptions', sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subscriptions', sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subscriptions', sa.Column('cancellation_reason', sa.String(100), nullable=True))
    op.add_column('subscriptions', sa.Column('cancellation_feedback', sa.Text(), nullable=True))
    op.add_column('subscriptions', sa.Column('dunning_status', sa.String(50), default='none', nullable=False, server_default='none'))
    op.add_column('subscriptions', sa.Column('dunning_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subscriptions', sa.Column('last_payment_error', sa.Text(), nullable=True))
    op.add_column('subscriptions', sa.Column('payment_retry_count', sa.Integer(), default=0, server_default='0'))
    op.add_column('subscriptions', sa.Column('next_payment_retry_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subscriptions', sa.Column('grace_period_ends_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subscriptions', sa.Column('billing_cycle_anchor', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove columns from subscriptions
    op.drop_column('subscriptions', 'billing_cycle_anchor')
    op.drop_column('subscriptions', 'grace_period_ends_at')
    op.drop_column('subscriptions', 'next_payment_retry_at')
    op.drop_column('subscriptions', 'payment_retry_count')
    op.drop_column('subscriptions', 'last_payment_error')
    op.drop_column('subscriptions', 'dunning_started_at')
    op.drop_column('subscriptions', 'dunning_status')
    op.drop_column('subscriptions', 'cancellation_feedback')
    op.drop_column('subscriptions', 'cancellation_reason')
    op.drop_column('subscriptions', 'ended_at')
    op.drop_column('subscriptions', 'canceled_at')
    op.drop_column('subscriptions', 'trial_start')

    # Drop tables
    op.drop_table('billing_info')
    op.drop_table('billing_audit_log')
    op.drop_table('webhook_events_log')
    op.drop_table('disputes')
    op.drop_table('refunds')
    op.drop_table('payments')
    op.drop_table('invoices')
    op.drop_table('subscription_items')
