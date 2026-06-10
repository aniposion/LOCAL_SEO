"""Add revenue profiles for revenue-centric ROI

Revision ID: 2026_03_06_revenue_profiles
Revises: 007, 007_add_ai_features, 20241223_p1_p5
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '2026_03_06_revenue_profiles'
down_revision = ('007', '007_add_ai_features', '20241223_p1_p5')
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'revenue_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('business_type', sa.String(length=100), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='USD'),
        sa.Column('average_order_value', sa.Numeric(10, 2), nullable=False, server_default='150.00'),
        sa.Column('gross_margin_percent', sa.Numeric(5, 2), nullable=False, server_default='30.00'),
        sa.Column('call_to_booking_rate', sa.Numeric(5, 2), nullable=False, server_default='35.00'),
        sa.Column('booking_to_visit_rate', sa.Numeric(5, 2), nullable=False, server_default='80.00'),
        sa.Column('visit_to_sale_rate', sa.Numeric(5, 2), nullable=False, server_default='90.00'),
        sa.Column('missed_call_recovery_rate', sa.Numeric(5, 2), nullable=False, server_default='20.00'),
        sa.Column('review_to_conversion_lift_percent', sa.Numeric(5, 2), nullable=False, server_default='3.00'),
        sa.Column('owner_hourly_value', sa.Numeric(10, 2), nullable=False, server_default='50.00'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_revenue_profiles_location_id', 'revenue_profiles', ['location_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_revenue_profiles_location_id', table_name='revenue_profiles')
    op.drop_table('revenue_profiles')
