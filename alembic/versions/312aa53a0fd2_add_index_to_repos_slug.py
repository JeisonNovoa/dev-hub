"""add index to repos slug

Revision ID: 312aa53a0fd2
Revises: da83db200bcd
Create Date: 2026-04-05 16:12:03.899528

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '312aa53a0fd2'
down_revision: Union[str, None] = 'da83db200bcd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF NOT EXISTS para ser idempotente (el índice puede ya existir en DBs pre-migración)
    op.execute("CREATE INDEX IF NOT EXISTS ix_repos_slug ON repos (slug)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_repos_slug")
