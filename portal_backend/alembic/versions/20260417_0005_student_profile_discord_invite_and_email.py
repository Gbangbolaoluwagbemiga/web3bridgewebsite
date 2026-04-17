"""student profile discord invite link and discord email

Revision ID: 20260417_0005
Revises: 20260330_0004
Create Date: 2026-04-17 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op
from app.core.config import get_settings

revision = "20260417_0005"
down_revision = "20260330_0004"
branch_labels = None
depends_on = None

settings = get_settings()
schema_name = settings.POSTGRES_SCHEMA


def upgrade() -> None:
    op.add_column(
        "student_profiles",
        sa.Column("discord_invite_link", sa.String(length=500), nullable=True),
        schema=schema_name,
    )
    op.add_column(
        "student_profiles",
        sa.Column("discord_email", sa.String(length=255), nullable=True),
        schema=schema_name,
    )


def downgrade() -> None:
    op.drop_column("student_profiles", "discord_email", schema=schema_name)
    op.drop_column("student_profiles", "discord_invite_link", schema=schema_name)
