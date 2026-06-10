"""Normalize AI feature foreign keys to UUID

Revision ID: 2026_03_06_ai_feature_uuid_fk
Revises: 2026_03_06_revenue_profiles
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '2026_03_06_ai_feature_uuid_fk'
down_revision = '2026_03_06_revenue_profiles'
branch_labels = None
depends_on = None


TARGET_TABLES = [
    'competitors',
    'competitor_analyses',
    'review_responses',
    'review_webhooks',
    'social_proof_cards',
    'social_proof_schedules',
]


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_type_name(table_name: str, column_name: str) -> str | None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return None

    for column in inspector.get_columns(table_name):
        if column["name"] == column_name:
            return str(column["type"]).upper()
    return None


def _assert_tables_empty_for_postgres() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    for table_name in TARGET_TABLES:
        if not _table_exists(table_name):
            continue
        count = bind.execute(sa.text(f'SELECT COUNT(*) FROM {table_name}')).scalar() or 0
        if count > 0:
            raise RuntimeError(
                f'Cannot auto-convert {table_name} foreign keys from integer to UUID with existing rows. '
                'Backfill or recreate data first, then rerun migration.'
            )


def upgrade() -> None:
    _assert_tables_empty_for_postgres()

    if _column_type_name('competitors', 'location_id') == 'INTEGER':
        with op.batch_alter_table('competitors') as batch_op:
            batch_op.alter_column('location_id', existing_type=sa.Integer(), type_=postgresql.UUID(as_uuid=True), existing_nullable=False)

    if _column_type_name('competitor_analyses', 'location_id') == 'INTEGER':
        with op.batch_alter_table('competitor_analyses') as batch_op:
            batch_op.alter_column('location_id', existing_type=sa.Integer(), type_=postgresql.UUID(as_uuid=True), existing_nullable=False)

    if _column_type_name('review_responses', 'location_id') == 'INTEGER' or _column_type_name('review_responses', 'approved_by') == 'INTEGER':
        with op.batch_alter_table('review_responses') as batch_op:
            if _column_type_name('review_responses', 'location_id') == 'INTEGER':
                batch_op.alter_column('location_id', existing_type=sa.Integer(), type_=postgresql.UUID(as_uuid=True), existing_nullable=False)
            if _column_type_name('review_responses', 'approved_by') == 'INTEGER':
                batch_op.alter_column('approved_by', existing_type=sa.Integer(), type_=postgresql.UUID(as_uuid=True), existing_nullable=True)

    if _column_type_name('review_webhooks', 'location_id') == 'INTEGER':
        with op.batch_alter_table('review_webhooks') as batch_op:
            batch_op.alter_column('location_id', existing_type=sa.Integer(), type_=postgresql.UUID(as_uuid=True), existing_nullable=False)

    if _column_type_name('social_proof_cards', 'location_id') == 'INTEGER' or _column_type_name('social_proof_cards', 'approved_by') == 'INTEGER':
        with op.batch_alter_table('social_proof_cards') as batch_op:
            if _column_type_name('social_proof_cards', 'location_id') == 'INTEGER':
                batch_op.alter_column('location_id', existing_type=sa.Integer(), type_=postgresql.UUID(as_uuid=True), existing_nullable=False)
            if _column_type_name('social_proof_cards', 'approved_by') == 'INTEGER':
                batch_op.alter_column('approved_by', existing_type=sa.Integer(), type_=postgresql.UUID(as_uuid=True), existing_nullable=True)

    if _column_type_name('social_proof_schedules', 'location_id') == 'INTEGER':
        with op.batch_alter_table('social_proof_schedules') as batch_op:
            batch_op.alter_column('location_id', existing_type=sa.Integer(), type_=postgresql.UUID(as_uuid=True), existing_nullable=False)


def downgrade() -> None:
    _assert_tables_empty_for_postgres()

    if _column_type_name('social_proof_schedules', 'location_id') == 'UUID':
        with op.batch_alter_table('social_proof_schedules') as batch_op:
            batch_op.alter_column('location_id', existing_type=postgresql.UUID(as_uuid=True), type_=sa.Integer(), existing_nullable=False)

    if _column_type_name('social_proof_cards', 'location_id') == 'UUID' or _column_type_name('social_proof_cards', 'approved_by') == 'UUID':
        with op.batch_alter_table('social_proof_cards') as batch_op:
            if _column_type_name('social_proof_cards', 'approved_by') == 'UUID':
                batch_op.alter_column('approved_by', existing_type=postgresql.UUID(as_uuid=True), type_=sa.Integer(), existing_nullable=True)
            if _column_type_name('social_proof_cards', 'location_id') == 'UUID':
                batch_op.alter_column('location_id', existing_type=postgresql.UUID(as_uuid=True), type_=sa.Integer(), existing_nullable=False)

    if _column_type_name('review_webhooks', 'location_id') == 'UUID':
        with op.batch_alter_table('review_webhooks') as batch_op:
            batch_op.alter_column('location_id', existing_type=postgresql.UUID(as_uuid=True), type_=sa.Integer(), existing_nullable=False)

    if _column_type_name('review_responses', 'location_id') == 'UUID' or _column_type_name('review_responses', 'approved_by') == 'UUID':
        with op.batch_alter_table('review_responses') as batch_op:
            if _column_type_name('review_responses', 'approved_by') == 'UUID':
                batch_op.alter_column('approved_by', existing_type=postgresql.UUID(as_uuid=True), type_=sa.Integer(), existing_nullable=True)
            if _column_type_name('review_responses', 'location_id') == 'UUID':
                batch_op.alter_column('location_id', existing_type=postgresql.UUID(as_uuid=True), type_=sa.Integer(), existing_nullable=False)

    if _column_type_name('competitor_analyses', 'location_id') == 'UUID':
        with op.batch_alter_table('competitor_analyses') as batch_op:
            batch_op.alter_column('location_id', existing_type=postgresql.UUID(as_uuid=True), type_=sa.Integer(), existing_nullable=False)

    if _column_type_name('competitors', 'location_id') == 'UUID':
        with op.batch_alter_table('competitors') as batch_op:
            batch_op.alter_column('location_id', existing_type=postgresql.UUID(as_uuid=True), type_=sa.Integer(), existing_nullable=False)
