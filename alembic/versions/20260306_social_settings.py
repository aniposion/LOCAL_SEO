"""Add social settings and sentiment tracking.

Revision ID: 20260306_social_settings
Revises: 20260306_social_response_logs
Create Date: 2026-03-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260306_social_settings"
down_revision = "20260306_social_response_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("social_response_logs", sa.Column("sentiment", sa.String(length=20), nullable=True))
    op.create_table(
        "social_automation_settings",
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("auto_respond_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("auto_respond_dms", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("auto_respond_comments", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("response_delay_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("excluded_keywords", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("location_id"),
    )
    op.create_index("ix_social_automation_settings_location_id", "social_automation_settings", ["location_id"])
    op.alter_column("social_automation_settings", "auto_respond_enabled", server_default=None)
    op.alter_column("social_automation_settings", "auto_respond_dms", server_default=None)
    op.alter_column("social_automation_settings", "auto_respond_comments", server_default=None)
    op.alter_column("social_automation_settings", "response_delay_seconds", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_social_automation_settings_location_id", table_name="social_automation_settings")
    op.drop_table("social_automation_settings")
    op.drop_column("social_response_logs", "sentiment")
