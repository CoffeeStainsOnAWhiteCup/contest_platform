"""add account state rating revision and notifications

Revision ID: a53bf892e107
Revises: 6d233f26b0ba
Create Date: 2026-11-21 12:40:29.586802

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a53bf892e107"
down_revision: Union[str, None] = "6d233f26b0ba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("chat_id", sa.String(length=100), nullable=False),
        sa.Column("event_key", sa.String(length=160), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("transient_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "event_key", name="uq_notification_event"),
    )
    op.create_index(
        "ix_notification_due", "notifications", ["status", "available_at"], unique=False
    )
    op.create_table(
        "user_audit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("field", sa.String(length=24), nullable=False),
        sa.Column("old_value", sa.String(length=48), nullable=False),
        sa.Column("new_value", sa.String(length=48), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "contests", sa.Column("rating_revision", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "users", sa.Column("name_customized", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column("users", sa.Column("avatar_url", sa.String(length=2048), nullable=True))
    op.add_column(
        "users", sa.Column("is_blocked", sa.Boolean(), server_default="false", nullable=False)
    )
    op.add_column(
        "users", sa.Column("auth_version", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "users", sa.Column("telegram_linked_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "telegram_linked_at")
    op.drop_column("users", "auth_version")
    op.drop_column("users", "is_blocked")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "name_customized")
    op.drop_column("contests", "rating_revision")
    op.drop_table("user_audit")
    op.drop_index("ix_notification_due", table_name="notifications")
    op.drop_table("notifications")
