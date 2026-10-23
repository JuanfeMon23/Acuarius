"""patient display_name

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-22 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('patients', sa.Column('display_name', sa.String(length=80), nullable=False, server_default='Familiar'))
    op.alter_column('patients', 'display_name', server_default=None)
    op.create_check_constraint(op.f('ck_patients_display_name_not_empty'), 'patients', 'char_length(display_name) >= 1')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f('ck_patients_display_name_not_empty'), 'patients', type_='check')
    op.drop_column('patients', 'display_name')
