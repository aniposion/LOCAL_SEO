"""Add credit_purchase_orders table

Revision ID: 20260329_credit_purchase_orders
Revises: 20260329_notification_history
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260329_credit_purchase_orders"
down_revision = "20260329_notification_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enum for purchase order status
    op.execute("""
        CREATE TYPE creditpurchasestatus AS ENUM (
            'pending', 'completed', 'canceled', 'expired'
        )
    """)

    op.create_table(
        "credit_purchase_orders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Stripe session that drives this purchase
        sa.Column("stripe_session_id", sa.String(255), nullable=False),
        # Package details captured at order creation
        sa.Column("package_id", sa.String(50), nullable=False),
        sa.Column("credits_amount", sa.Integer, nullable=False),
        sa.Column("price_cents", sa.Integer, nullable=False),
        # Lifecycle state
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending", "completed", "canceled", "expired",
                name="creditpurchasestatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        # Filled in from webhook after payment confirmation
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        # Standard audit columns
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # UNIQUE on stripe_session_id prevents double-application of the same session
    op.create_index(
        "idx_credit_purchase_orders_session",
        "credit_purchase_orders",
        ["stripe_session_id"],
        unique=True,
    )
    op.create_index(
        "idx_credit_purchase_orders_account_status",
        "credit_purchase_orders",
        ["account_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_credit_purchase_orders_account_status")
    op.drop_index("idx_credit_purchase_orders_session")
    op.drop_table("credit_purchase_orders")
    op.execute("DROP TYPE IF EXISTS creditpurchasestatus")
