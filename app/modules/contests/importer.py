"""Parse and append an entire UTF-8 problem test file in a single transaction."""

import csv
import io
import json
import uuid
from pathlib import Path

from fastapi import HTTPException
from pydantic import ConfigDict, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Problem, Test
from app.modules.contests.schemas import TestCreate

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 1000
MAX_ORDINAL = 2**31 - 1
csv.field_size_limit(1_000_000)


class ImportRow(TestCreate):
    model_config = ConfigDict(extra="forbid")


def parse_file(filename: str, content: bytes) -> list[TestCreate]:
    """Validate the complete input before writing any rows."""
    suffix = Path(filename).suffix.lower()
    if suffix not in {".json", ".csv"}:
        raise HTTPException(415, "Expected a .json or .csv file")
    try:
        document = content.decode("utf-8-sig")
        if suffix == ".json":
            records = json.loads(document)
            if not isinstance(records, list):
                raise ValueError("Expected a JSON array")
        else:
            reader = csv.DictReader(io.StringIO(document, newline=""), strict=True)
            headers = reader.fieldnames or []
            if (
                len(set(headers)) != len(headers)
                or set(headers) - ImportRow.model_fields.keys()
                or not {"input_data", "expected_output"} <= set(headers)
            ):
                raise ValueError("Invalid CSV header")
            records = reader
        rows: list[TestCreate] = []
        for index, record in enumerate(records, 1):
            if index > MAX_ROWS:
                raise HTTPException(413, "Too many test cases")
            if suffix == ".csv":
                if None in record or None in record.values():
                    raise ValueError(f"Wrong column count in record {index}")
                record = {k: v for k, v in record.items() if k not in {"ordinal", "is_sample"} or v != ""}
            try:
                row = ImportRow.model_validate(record)
                if row.ordinal is not None and row.ordinal > MAX_ORDINAL:
                    raise ValueError("Ordinal is too large")
                for value in (row.input_data, row.expected_output):
                    value.encode("utf-8")
                    if "\x00" in value:
                        raise ValueError("Null character in text")
            except (ValidationError, ValueError) as exc:
                raise HTTPException(422, f"Invalid test case at record {index}") from exc
            rows.append(row)
        if not rows:
            raise ValueError("Empty test set")
        return rows
    except (ValueError, csv.Error, RecursionError) as exc:
        raise HTTPException(422, "Invalid UTF-8 test file: " + str(exc)[:160]) from exc


async def append_tests(db: AsyncSession, problem_id: uuid.UUID, rows: list[TestCreate]) -> int:
    """Serialize imports per problem and let the unique index guard concurrent edits."""
    problem = await db.scalar(select(Problem.id).where(Problem.id == problem_id).with_for_update())
    if problem is None:
        raise HTTPException(404, "Problem not found")
    existing = set(await db.scalars(select(Test.ordinal).where(Test.problem_id == problem_id)))
    explicit = [row.ordinal for row in rows if row.ordinal is not None]
    if len(set(explicit)) != len(explicit) or existing.intersection(explicit):
        raise HTTPException(409, "Test ordinal already exists")
    reserved = set(explicit)
    next_number = max(existing, default=0) + 1
    for row in rows:
        number = row.ordinal
        if number is None:
            while next_number in reserved:
                next_number += 1
            number = next_number
            next_number += 1
        if number > MAX_ORDINAL:
            raise HTTPException(409, "No ordinal available")
        db.add(Test(problem_id=problem_id, ordinal=number, **row.model_dump(exclude={"ordinal"})))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Conflict with a concurrent test update") from None
    return len(rows)
