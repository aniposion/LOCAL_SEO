"""add contact requests

Revision ID: 20260502_contact_requests
Revises: 20260427_board_posts
Create Date: 2026-05-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260502_contact_requests"
down_revision: Union[str, Sequence[str], None] = "20260427_board_posts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contact_requests",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("business_name", sa.String(length=200), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("recommended_package", sa.String(length=80), nullable=True),
        sa.Column("lead_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sales_notes", sa.Text(), nullable=True),
        sa.Column("contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_contact_requests_email", "contact_requests", ["email"])
    op.create_index("ix_contact_requests_status", "contact_requests", ["status"])
    op.create_index("ix_contact_requests_recommended_package", "contact_requests", ["recommended_package"])
    op.create_index("ix_contact_requests_lead_score", "contact_requests", ["lead_score"])
    op.create_index("ix_contact_requests_created_at", "contact_requests", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_contact_requests_created_at", table_name="contact_requests")
    op.drop_index("ix_contact_requests_lead_score", table_name="contact_requests")
    op.drop_index("ix_contact_requests_recommended_package", table_name="contact_requests")
    op.drop_index("ix_contact_requests_status", table_name="contact_requests")
    op.drop_index("ix_contact_requests_email", table_name="contact_requests")
    op.drop_table("contact_requests")
