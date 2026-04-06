"""add deleted_at to credentials (soft delete / papelera)

Revision ID: c4e2f8a1b9d3
Revises: a4f9c2e81d30
Create Date: 2026-04-06 09:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4e2f8a1b9d3"
down_revision: Union[str, None] = "a4f9c2e81d30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("credentials") as batch_op:
        batch_op.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("credentials") as batch_op:
        batch_op.drop_column("deleted_at")
