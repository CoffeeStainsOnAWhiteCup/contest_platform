"""reindex ordinals and add unique constraints

Revision ID: c1a2b3d4e5f6
Revises: b7e4c9a1f2d3
Create Date: 2026-11-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, None] = "b7e4c9a1f2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE problems DROP CONSTRAINT IF EXISTS uq_problems_contest_ordinal"
    )
    op.execute(
        "ALTER TABLE tests DROP CONSTRAINT IF EXISTS uq_tests_problem_ordinal"
    )

    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (PARTITION BY contest_id ORDER BY id) AS position
            FROM problems
        )
        UPDATE problems
        SET ordinal = ranked.position
        FROM ranked
        WHERE problems.id = ranked.id
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (PARTITION BY problem_id ORDER BY ordinal, id) AS position
            FROM tests
        )
        UPDATE tests
        SET ordinal = ranked.position
        FROM ranked
        WHERE tests.id = ranked.id
        """
    )

    op.create_unique_constraint(
        "uq_problems_contest_ordinal", "problems", ["contest_id", "ordinal"]
    )
    op.create_unique_constraint(
        "uq_tests_problem_ordinal", "tests", ["problem_id", "ordinal"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_tests_problem_ordinal", "tests", type_="unique")
    op.drop_constraint("uq_problems_contest_ordinal", "problems", type_="unique")
