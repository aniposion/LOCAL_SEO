"""Add social response audit log table.

Revision ID: 20260306_social_response_logs
Revises: 20260306_review_retry
Create Date: 2026-03-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260306_social_response_logs"
down_revision = "20260306_review_retry"
branch_labels = None
depends_on = None


social_response_mode = sa.Enum("manual", "auto", name="socialresponsemode")


def upgrade() -> None:
    bind = op.get_bind()
    social_response_mode.create(bind, checkfirst=True)

    op.create_table(
        "social_response_logs",
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("message_type", sa.String(length=50), nullable=False),
        sa.Column("response_mode", social_response_mode, nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=False),
        sa.Column("sender_id", sa.String(length=255), nullable=True),
        sa.Column("sender_name", sa.String(length=255), nullable=True),
        sa.Column("post_id", sa.String(length=255), nullable=True),
        sa.Column("source_message", sa.Text(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_social_response_logs_location_id", "social_response_logs", ["location_id"])
    op.create_index("ix_social_response_logs_message_id", "social_response_logs", ["message_id"])
    op.alter_column("social_response_logs", "success", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_social_response_logs_message_id", table_name="social_response_logs")
    op.drop_index("ix_social_response_logs_location_id", table_name="social_response_logs")
    op.drop_table("social_response_logs")
    social_response_mode.drop(op.get_bind(), checkfirst=True)
