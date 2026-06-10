"""Extend credit_purchase_orders: add refunded status and refunded_at column

Revision ID: 20260328_credit_purchase_refund
Revises: 20260329_credit_purchase_orders
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa

revision = "20260328_credit_purchase_refund"
down_revision = "20260329_credit_purchase_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend the enum with the new 'refunded' value.
    # PostgreSQL requires ALTER TYPE ... ADD VALUE outside a transaction.
    op.execute("ALTER TYPE creditpurchasestatus ADD VALUE IF NOT EXISTS 'refunded'")

    # Add refunded_at column
    op.add_column(
        "credit_purchase_orders",
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("credit_purchase_orders", "refunded_at")
    # PostgreSQL does not support removing enum values; downgrade leaves the
    # enum value in place (harmless – the column constraint prevents its use).
