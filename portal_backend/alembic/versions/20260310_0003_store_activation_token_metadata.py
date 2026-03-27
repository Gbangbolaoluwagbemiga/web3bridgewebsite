"""store activation token metadata

Revision ID: 20260310_0003
Revises: 20260308_0002
Create Date: 2026-03-10 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op
from app.core.config import get_settings

# revision identifiers, used by Alembic.
revision = "20260310_0003"
down_revision = "20260308_0002"
branch_labels = None
depends_on = None

settings = get_settings()
schema_name = settings.POSTGRES_SCHEMA


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("activation_token_jti", sa.String(length=255), nullable=True),
        schema=schema_name,
    )
    op.add_column(
        "users",
        sa.Column("activation_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        schema=schema_name,
    )


def downgrade() -> None:
    op.drop_column("users", "activation_token_expires_at", schema=schema_name)
    op.drop_column("users", "activation_token_jti", schema=schema_name)
