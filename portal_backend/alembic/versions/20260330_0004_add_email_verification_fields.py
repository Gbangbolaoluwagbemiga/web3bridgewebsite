"""add email verification fields

Revision ID: 20260330_0004
Revises: 20260310_0003
Create Date: 2026-03-30 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op
from app.core.config import get_settings

# revision identifiers, used by Alembic.
revision = "20260330_0004"
down_revision = "20260310_0003"
branch_labels = None
depends_on = None

settings = get_settings()
schema_name = settings.POSTGRES_SCHEMA


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema=schema_name,
    )
    op.add_column(
        "users",
        sa.Column("email_verification_code", sa.String(length=6), nullable=True),
        schema=schema_name,
    )
    op.add_column(
        "users",
        sa.Column("email_verification_expires_at", sa.DateTime(timezone=True), nullable=True),
        schema=schema_name,
    )


def downgrade() -> None:
    op.drop_column("users", "email_verification_expires_at", schema=schema_name)
    op.drop_column("users", "email_verification_code", schema=schema_name)
    op.drop_column("users", "email_verified", schema=schema_name)
