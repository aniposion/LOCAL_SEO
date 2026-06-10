"""Normalize post status enum labels to lowercase values used by the ORM.

Revision ID: 20260306_poststatus
Revises: 20260306_sub_enum
Create Date: 2026-03-06
"""

from alembic import op


revision = "20260306_poststatus"
down_revision = "20260306_sub_enum"
branch_labels = None
depends_on = None


def _rename_enum_value(old_value: str, new_value: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_enum e ON e.enumtypid = t.oid
                WHERE t.typname = 'poststatus' AND e.enumlabel = '{old_value}'
            ) AND NOT EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_enum e ON e.enumtypid = t.oid
                WHERE t.typname = 'poststatus' AND e.enumlabel = '{new_value}'
            ) THEN
                ALTER TYPE poststatus RENAME VALUE '{old_value}' TO '{new_value}';
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    _rename_enum_value("DRAFT", "draft")
    _rename_enum_value("QUEUED", "queued")
    _rename_enum_value("POSTED", "posted")
    _rename_enum_value("FAILED", "failed")


def downgrade() -> None:
    _rename_enum_value("draft", "DRAFT")
    _rename_enum_value("queued", "QUEUED")
    _rename_enum_value("posted", "POSTED")
    _rename_enum_value("failed", "FAILED")
