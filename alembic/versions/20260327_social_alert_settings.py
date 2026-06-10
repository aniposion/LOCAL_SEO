"""Add social high-priority alert settings.

Revision ID: 20260327_social_alert_settings
Revises: 20260327_website_seo_approval
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260327_social_alert_settings"
down_revision = "20260327_website_seo_approval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "social_automation_settings",
        sa.Column("high_priority_alerts_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "social_automation_settings",
        sa.Column("high_priority_alert_channel", sa.String(length=20), nullable=False, server_default="preferred"),
    )
    op.alter_column("social_automation_settings", "high_priority_alerts_enabled", server_default=None)
    op.alter_column("social_automation_settings", "high_priority_alert_channel", server_default=None)


def downgrade() -> None:
    op.drop_column("social_automation_settings", "high_priority_alert_channel")
    op.drop_column("social_automation_settings", "high_priority_alerts_enabled")
