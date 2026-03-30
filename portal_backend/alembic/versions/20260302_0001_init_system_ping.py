"""init system ping table

Revision ID: 20260302_0001
Revises: 
Create Date: 2026-03-02 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op
from app.core.config import get_settings

# revision identifiers, used by Alembic.
revision = "20260302_0001"
down_revision = None
branch_labels = None
depends_on = None

settings = get_settings()
schema_name = settings.POSTGRES_SCHEMA


def upgrade() -> None:
    op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

    op.create_table(
        "system_pings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_system_pings")),
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_system_pings_source"),
        "system_pings",
        ["source"],
        unique=False,
        schema=schema_name,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_system_pings_source"), table_name="system_pings", schema=schema_name)
    op.drop_table("system_pings", schema=schema_name)
