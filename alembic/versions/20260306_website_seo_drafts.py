"""Add website SEO draft history table.

Revision ID: 20260306_website_seo_drafts
Revises: 2026_03_06_ai_feature_uuid_fk, 20260306_social_settings
Create Date: 2026-03-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260306_website_seo_drafts"
down_revision = ("2026_03_06_ai_feature_uuid_fk", "20260306_social_settings")
branch_labels = None
depends_on = None


website_seo_content_type = sa.Enum(
    "meta_tags",
    "service_page",
    "blog_post",
    "optimization",
    name="websiteseocontenttype",
)
website_seo_draft_status = sa.Enum(
    "draft",
    "published",
    "failed",
    name="websiteseodraftstatus",
)


def upgrade() -> None:
    bind = op.get_bind()
    website_seo_content_type.create(bind, checkfirst=True)
    website_seo_draft_status.create(bind, checkfirst=True)

    op.create_table(
        "website_seo_drafts",
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("content_type", website_seo_content_type, nullable=False),
        sa.Column("status", website_seo_draft_status, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("slug", sa.String(length=255), nullable=True),
        sa.Column("page_type", sa.String(length=50), nullable=True),
        sa.Column("source_topic", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("published_url", sa.String(length=500), nullable=True),
        sa.Column("provider_reference", sa.String(length=255), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_website_seo_drafts_location_id", "website_seo_drafts", ["location_id"])


def downgrade() -> None:
    op.drop_index("ix_website_seo_drafts_location_id", table_name="website_seo_drafts")
    op.drop_table("website_seo_drafts")
    website_seo_draft_status.drop(op.get_bind(), checkfirst=True)
    website_seo_content_type.drop(op.get_bind(), checkfirst=True)
