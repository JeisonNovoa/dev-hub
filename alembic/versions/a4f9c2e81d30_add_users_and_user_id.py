"""add users table and user_id to projects, services, credentials

Revision ID: a4f9c2e81d30
Revises: 312aa53a0fd2
Create Date: 2026-04-05 18:00:00.000000

"""
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4f9c2e81d30"
down_revision: Union[str, None] = "312aa53a0fd2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Hash bcrypt de "changeme" — cámbiala en tu primer login
_ADMIN_EMAIL = "admin@devhub.local"
_ADMIN_HASH = "$2b$12$YI.OdAL756LjMBrw.YoI5uJQc25s5i.fXkjsywk4hAKZ.PhLoN4fW"


def upgrade() -> None:
    # ── 1. Crear tabla users ──────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── 2. Añadir user_id nullable a las tres tablas raíz ────────────────────
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_projects_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.create_index("ix_projects_user_id", ["user_id"])

    with op.batch_alter_table("services") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_services_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.create_index("ix_services_user_id", ["user_id"])

    with op.batch_alter_table("credentials") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_credentials_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
        batch_op.create_index("ix_credentials_user_id", ["user_id"])

    # ── 3. Insertar usuario admin seed ────────────────────────────────────────
    now = datetime.now(timezone.utc).isoformat()
    op.execute(
        f"INSERT INTO users (email, hashed_password, is_active, created_at, updated_at) "
        f"VALUES ('{_ADMIN_EMAIL}', '{_ADMIN_HASH}', 1, '{now}', '{now}')"
    )

    # ── 4. Asignar todos los datos existentes al admin ────────────────────────
    op.execute(
        f"UPDATE projects SET user_id = (SELECT id FROM users WHERE email = '{_ADMIN_EMAIL}')"
    )
    op.execute(
        f"UPDATE services SET user_id = (SELECT id FROM users WHERE email = '{_ADMIN_EMAIL}')"
    )
    op.execute(
        f"UPDATE credentials SET user_id = (SELECT id FROM users WHERE email = '{_ADMIN_EMAIL}')"
    )

    # ── 5. Hacer user_id NOT NULL ─────────────────────────────────────────────
    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column("user_id", nullable=False)

    with op.batch_alter_table("services") as batch_op:
        batch_op.alter_column("user_id", nullable=False)

    with op.batch_alter_table("credentials") as batch_op:
        batch_op.alter_column("user_id", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("credentials") as batch_op:
        batch_op.drop_index("ix_credentials_user_id")
        batch_op.drop_constraint("fk_credentials_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("services") as batch_op:
        batch_op.drop_index("ix_services_user_id")
        batch_op.drop_constraint("fk_services_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_index("ix_projects_user_id")
        batch_op.drop_constraint("fk_projects_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
