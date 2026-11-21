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
        DO $$
        DECLARE
            parent_contest RECORD;
            problem RECORD;
            reserved INTEGER[];
            candidate INTEGER;
        BEGIN
            FOR parent_contest IN
                SELECT DISTINCT contest_id FROM problems
            LOOP
                reserved := ARRAY(
                    SELECT ordinal
                    FROM (
                        SELECT
                            ordinal,
                            count(*) OVER (PARTITION BY ordinal) AS value_count,
                            row_number() OVER (
                                PARTITION BY ordinal ORDER BY id
                            ) AS value_rank
                        FROM problems
                        WHERE contest_id = parent_contest.contest_id
                          AND ordinal > 0
                    ) ranked_positive
                    WHERE value_count = 1 OR value_rank = 1
                );

                FOR problem IN
                    SELECT
                        id,
                        CASE
                            WHEN ordinal <= 0 THEN true
                            WHEN count(*) OVER (PARTITION BY ordinal) > 1
                                 AND row_number() OVER (
                                     PARTITION BY ordinal ORDER BY id
                                 ) > 1 THEN true
                            ELSE false
                        END AS needs_number
                    FROM problems
                    WHERE contest_id = parent_contest.contest_id
                    ORDER BY id
                LOOP
                    IF NOT problem.needs_number THEN
                        CONTINUE;
                    END IF;

                    candidate := 1;
                    WHILE candidate = ANY(reserved) LOOP
                        candidate := candidate + 1;
                    END LOOP;
                    UPDATE problems SET ordinal = candidate WHERE id = problem.id;
                    reserved := array_append(reserved, candidate);
                END LOOP;
            END LOOP;
        END $$;
        """
    )

    op.execute(
        """
        DO $$
        DECLARE
            parent_problem RECORD;
            test RECORD;
            reserved INTEGER[];
            candidate INTEGER;
        BEGIN
            FOR parent_problem IN
                SELECT DISTINCT problem_id FROM tests
            LOOP
                reserved := ARRAY(
                    SELECT ordinal
                    FROM (
                        SELECT
                            ordinal,
                            count(*) OVER (PARTITION BY ordinal) AS value_count,
                            row_number() OVER (
                                PARTITION BY ordinal ORDER BY id
                            ) AS value_rank
                        FROM tests
                        WHERE problem_id = parent_problem.problem_id
                          AND ordinal > 0
                    ) ranked_positive
                    WHERE value_count = 1 OR value_rank = 1
                );

                FOR test IN
                    SELECT
                        id,
                        CASE
                            WHEN ordinal <= 0 THEN true
                            WHEN count(*) OVER (PARTITION BY ordinal) > 1
                                 AND row_number() OVER (
                                     PARTITION BY ordinal ORDER BY id
                                 ) > 1 THEN true
                            ELSE false
                        END AS needs_number
                    FROM tests
                    WHERE problem_id = parent_problem.problem_id
                    ORDER BY id
                LOOP
                    IF NOT test.needs_number THEN
                        CONTINUE;
                    END IF;

                    candidate := 1;
                    WHILE candidate = ANY(reserved) LOOP
                        candidate := candidate + 1;
                    END LOOP;
                    UPDATE tests SET ordinal = candidate WHERE id = test.id;
                    reserved := array_append(reserved, candidate);
                END LOOP;
            END LOOP;
        END $$;
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
