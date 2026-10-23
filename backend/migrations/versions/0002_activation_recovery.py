"""activation recovery

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('activation_recovery',
    sa.Column('reference', sa.String(length=24), nullable=False),
    sa.Column('reason', sa.String(length=32), nullable=False),
    sa.Column('patient_document_type', sa.String(length=16), nullable=False),
    sa.Column('patient_document_number', sa.String(length=32), nullable=False),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolved_note', sa.String(length=200), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('uuidv7()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("reason IN ('leo_conflict', 'leo_weak_password', 'leo_unavailable', 'db_error')", name=op.f('ck_activation_recovery_reason_valid')),
    sa.CheckConstraint('resolved_at IS NULL OR resolved_at >= created_at', name=op.f('ck_activation_recovery_resolved_after_created')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_activation_recovery')),
    sa.UniqueConstraint('reference', name=op.f('uq_activation_recovery_reference'))
    )
    op.create_index('ix_activation_recovery_unresolved', 'activation_recovery', ['created_at'], unique=False, postgresql_where=sa.text('resolved_at IS NULL'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_activation_recovery_unresolved', table_name='activation_recovery', postgresql_where=sa.text('resolved_at IS NULL'))
    op.drop_table('activation_recovery')
