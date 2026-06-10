"""merge public launch migration heads

Revision ID: 20260426_merge_public_launch_heads
Revises: 20260306_qa_drafts, 20260327_competitor_review_sync, 20260327_qa_feedback, 20260328_credit_purchase_refund, 20260423_free_audit_contact_email, 2026_01_05_p0_onboarding
Create Date: 2026-04-26
"""

from typing import Sequence, Union


revision: str = "20260426_merge_public_launch_heads"
down_revision: Union[str, Sequence[str], None] = (
    "20260306_qa_drafts",
    "20260327_competitor_review_sync",
    "20260327_qa_feedback",
    "20260328_credit_purchase_refund",
    "20260423_free_audit_contact_email",
    "2026_01_05_p0_onboarding",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge parallel migration branches into a single public-launch head."""


def downgrade() -> None:
    """No-op merge revision."""
