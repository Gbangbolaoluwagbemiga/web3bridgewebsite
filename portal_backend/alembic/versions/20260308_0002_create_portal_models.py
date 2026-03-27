"""create portal models

Revision ID: 20260308_0002
Revises: 20260302_0001
Create Date: 2026-03-08 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op
from app.core.config import get_settings

# revision identifiers, used by Alembic.
revision = "20260308_0002"
down_revision = "20260302_0001"
branch_labels = None
depends_on = None

settings = get_settings()
schema_name = settings.POSTGRES_SCHEMA


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'student'"),
        ),
        sa.Column(
            "account_state",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'invited'"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        schema=schema_name,
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False, schema=schema_name)
    op.create_index(
        op.f("ix_users_account_state"),
        "users",
        ["account_state"],
        unique=False,
        schema=schema_name,
    )

    op.create_table(
        "student_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("discord_id", sa.String(length=100), nullable=True),
        sa.Column("wallet_address", sa.String(length=255), nullable=True),
        sa.Column("cohort", sa.String(length=100), nullable=True),
        sa.Column(
            "onboarding_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("bio", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            [f"{schema_name}.users.id"],
            name=op.f("fk_student_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_profiles")),
        sa.UniqueConstraint("user_id", name=op.f("uq_student_profiles_user_id")),
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_student_profiles_cohort"),
        "student_profiles",
        ["cohort"],
        unique=False,
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_student_profiles_onboarding_status"),
        "student_profiles",
        ["onboarding_status"],
        unique=False,
        schema=schema_name,
    )

    op.create_table(
        "external_student_map",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "source_system",
            sa.String(length=100),
            nullable=False,
            server_default=sa.text("'backend_v2'"),
        ),
        sa.Column("external_student_id", sa.String(length=255), nullable=False),
        sa.Column("source_email", sa.String(length=255), nullable=False),
        sa.Column(
            "approval_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("approval_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            [f"{schema_name}.users.id"],
            name=op.f("fk_external_student_map_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_external_student_map")),
        sa.UniqueConstraint(
            "external_student_id",
            name=op.f("uq_external_student_map_external_student_id"),
        ),
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_external_student_map_user_id"),
        "external_student_map",
        ["user_id"],
        unique=False,
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_external_student_map_source_email"),
        "external_student_map",
        ["source_email"],
        unique=False,
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_external_student_map_approval_status"),
        "external_student_map",
        ["approval_status"],
        unique=False,
        schema=schema_name,
    )

    op.create_table(
        "student_status_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("from_state", sa.String(length=20), nullable=True),
        sa.Column("to_state", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.Integer(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["changed_by"],
            [f"{schema_name}.users.id"],
            name=op.f("fk_student_status_history_changed_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            [f"{schema_name}.users.id"],
            name=op.f("fk_student_status_history_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_status_history")),
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_student_status_history_user_id"),
        "student_status_history",
        ["user_id"],
        unique=False,
        schema=schema_name,
    )

    op.create_table(
        "student_updates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_ref", sa.String(length=255), nullable=True),
        sa.Column(
            "is_published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["created_by"],
            [f"{schema_name}.users.id"],
            name=op.f("fk_student_updates_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_updates")),
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_student_updates_target_type"),
        "student_updates",
        ["target_type"],
        unique=False,
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_student_updates_target_ref"),
        "student_updates",
        ["target_ref"],
        unique=False,
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_student_updates_is_published"),
        "student_updates",
        ["is_published"],
        unique=False,
        schema=schema_name,
    )

    op.create_table(
        "student_update_reads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("update_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["update_id"],
            [f"{schema_name}.student_updates.id"],
            name=op.f("fk_student_update_reads_update_id_student_updates"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            [f"{schema_name}.users.id"],
            name=op.f("fk_student_update_reads_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_update_reads")),
        sa.UniqueConstraint(
            "update_id",
            "user_id",
            name="uq_update_read_per_user",
        ),
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_student_update_reads_update_id"),
        "student_update_reads",
        ["update_id"],
        unique=False,
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_student_update_reads_user_id"),
        "student_update_reads",
        ["user_id"],
        unique=False,
        schema=schema_name,
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("jti", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            [f"{schema_name}.users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("jti", name=op.f("uq_refresh_tokens_jti")),
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_refresh_tokens_user_id"),
        "refresh_tokens",
        ["user_id"],
        unique=False,
        schema=schema_name,
    )

    op.create_table(
        "external_sync_record",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_name", sa.String(length=100), nullable=False),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_payload", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_external_sync_record")),
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_external_sync_record_job_name"),
        "external_sync_record",
        ["job_name"],
        unique=False,
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_external_sync_record_status"),
        "external_sync_record",
        ["status"],
        unique=False,
        schema=schema_name,
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("before_json", sa.JSON(), nullable=True),
        sa.Column("after_json", sa.JSON(), nullable=True),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            [f"{schema_name}.users.id"],
            name=op.f("fk_audit_logs_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_audit_logs_actor_user_id"),
        "audit_logs",
        ["actor_user_id"],
        unique=False,
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_audit_logs_action"),
        "audit_logs",
        ["action"],
        unique=False,
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_audit_logs_resource_type"),
        "audit_logs",
        ["resource_type"],
        unique=False,
        schema=schema_name,
    )
    op.create_index(
        op.f("ix_audit_logs_request_id"),
        "audit_logs",
        ["request_id"],
        unique=False,
        schema=schema_name,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_request_id"), table_name="audit_logs", schema=schema_name)
    op.drop_index(op.f("ix_audit_logs_resource_type"), table_name="audit_logs", schema=schema_name)
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs", schema=schema_name)
    op.drop_index(op.f("ix_audit_logs_actor_user_id"), table_name="audit_logs", schema=schema_name)
    op.drop_table("audit_logs", schema=schema_name)

    op.drop_index(
        op.f("ix_external_sync_record_status"),
        table_name="external_sync_record",
        schema=schema_name,
    )
    op.drop_index(
        op.f("ix_external_sync_record_job_name"),
        table_name="external_sync_record",
        schema=schema_name,
    )
    op.drop_table("external_sync_record", schema=schema_name)

    op.drop_index(
        op.f("ix_refresh_tokens_user_id"),
        table_name="refresh_tokens",
        schema=schema_name,
    )
    op.drop_table("refresh_tokens", schema=schema_name)

    op.drop_index(
        op.f("ix_student_update_reads_user_id"),
        table_name="student_update_reads",
        schema=schema_name,
    )
    op.drop_index(
        op.f("ix_student_update_reads_update_id"),
        table_name="student_update_reads",
        schema=schema_name,
    )
    op.drop_table("student_update_reads", schema=schema_name)

    op.drop_index(
        op.f("ix_student_updates_is_published"),
        table_name="student_updates",
        schema=schema_name,
    )
    op.drop_index(
        op.f("ix_student_updates_target_ref"),
        table_name="student_updates",
        schema=schema_name,
    )
    op.drop_index(
        op.f("ix_student_updates_target_type"),
        table_name="student_updates",
        schema=schema_name,
    )
    op.drop_table("student_updates", schema=schema_name)

    op.drop_index(
        op.f("ix_student_status_history_user_id"),
        table_name="student_status_history",
        schema=schema_name,
    )
    op.drop_table("student_status_history", schema=schema_name)

    op.drop_index(
        op.f("ix_external_student_map_approval_status"),
        table_name="external_student_map",
        schema=schema_name,
    )
    op.drop_index(
        op.f("ix_external_student_map_source_email"),
        table_name="external_student_map",
        schema=schema_name,
    )
    op.drop_index(
        op.f("ix_external_student_map_user_id"),
        table_name="external_student_map",
        schema=schema_name,
    )
    op.drop_table("external_student_map", schema=schema_name)

    op.drop_index(
        op.f("ix_student_profiles_onboarding_status"),
        table_name="student_profiles",
        schema=schema_name,
    )
    op.drop_index(
        op.f("ix_student_profiles_cohort"),
        table_name="student_profiles",
        schema=schema_name,
    )
    op.drop_table("student_profiles", schema=schema_name)

    op.drop_index(op.f("ix_users_account_state"), table_name="users", schema=schema_name)
    op.drop_index(op.f("ix_users_email"), table_name="users", schema=schema_name)
    op.drop_table("users", schema=schema_name)
