"""settings y settings_history: politicas operativas editables con historial

DDL del modulo compartido `leo_sdk.settings_store.migration` (mismo esquema que
en las demas apps). Acuarius no tiene tabla de usuarios: `users_table=None`
deja `updated_by`/`changed_by` como UUID del usuario de Leo sin llave foranea.
`settings_history` es append-only (trigger) y sin FK a `settings` para que
sobreviva a cambios del catalogo. El downgrade elimina ambas tablas con sus
filas.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-23 12:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
from leo_sdk.settings_store import migration

# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: str | Sequence[str] | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    migration.upgrade(op, users_table=None)


def downgrade() -> None:
    """Downgrade schema."""
    migration.downgrade(op, users_table=None)
