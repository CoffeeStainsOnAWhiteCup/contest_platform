"""Store private Telegram chat details and retain contest event keys."""
import sqlalchemy as sa
from alembic import op

revision = "7cb39214e06a"
down_revision = "e4a680bb4321"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("telegram_name", sa.Text()))
    op.add_column("users", sa.Column("telegram_username", sa.Text()))
    op.create_table(
        "contest_notification_keys",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("event_key", sa.String(160), primary_key=True),
    )
    op.execute("""
        INSERT INTO contest_notification_keys (user_id, event_key)
        SELECT user_id, event_key FROM notifications WHERE event_key LIKE 'contest:%'
    """)


def downgrade() -> None:
    op.drop_table("contest_notification_keys")
    op.drop_column("users", "telegram_username")
    op.drop_column("users", "telegram_name")
