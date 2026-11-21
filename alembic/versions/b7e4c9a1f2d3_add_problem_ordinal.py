"""add problem ordinal

Revision ID: b7e4c9a1f2d3
Revises: 6d233f26b0ba
Create Date: 2026-11-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7e4c9a1f2d3"
down_revision: Union[str, None] = "6d233f26b0ba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "problems",
        sa.Column("ordinal", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.alter_column("problems", "ordinal", server_default=None)


def downgrade() -> None:
    op.drop_column("problems", "ordinal")
