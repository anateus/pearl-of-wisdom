"""SQLite persistence for investigations, using only the Python standard library."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .investigation import (
    Investigation,
    InvestigationRecord,
    InvestigationStatus,
    JsonValue,
    timestamp,
)


class InvestigationNotFoundError(LookupError):
    """Raised when a requested investigation does not exist."""


class InvestigationStore:
    """A transaction-safe, append-only store of investigation records."""

    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        if self.database == ":memory:":
            raise ValueError(":memory: is unsupported; use a filesystem path for durable records")
        self._initialize()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS investigations (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL CHECK (status IN ('ephemeral', 'durable')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS investigation_records (
                    id TEXT PRIMARY KEY,
                    investigation_id TEXT NOT NULL REFERENCES investigations(id),
                    kind TEXT NOT NULL CHECK (
                        kind IN ('context', 'assumption', 'evidence', 'analysis')
                    ),
                    engine TEXT,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS investigation_records_by_investigation
                    ON investigation_records(investigation_id, created_at, id);
                """
            )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex}"

    @staticmethod
    def _json(payload: JsonValue) -> str:
        try:
            return json.dumps(payload, allow_nan=False, separators=(",", ":"), sort_keys=True)
        except (TypeError, ValueError) as error:
            raise ValueError("Record payload must be JSON-serializable") from error

    def create_investigation(
        self, *, status: InvestigationStatus = InvestigationStatus.EPHEMERAL
    ) -> Investigation:
        """Create and return a new investigation with a generated immutable ID."""
        if not isinstance(status, InvestigationStatus):
            raise TypeError("status must be an InvestigationStatus")
        investigation = Investigation.new(id=self._id("inv"), now=self._now(), status=status)
        with self._connection() as connection:
            connection.execute(
                (
                    "INSERT INTO investigations "
                    "(id, status, created_at, updated_at) VALUES (?, ?, ?, ?)"
                ),
                (
                    investigation.id,
                    investigation.status.value,
                    investigation.created_at,
                    investigation.updated_at,
                ),
            )
        return investigation

    def list_investigations(self) -> list[Investigation]:
        """List envelopes in their stable creation order."""
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id FROM investigations ORDER BY created_at, id"
            ).fetchall()
        return [self.get_investigation(row["id"]) for row in rows]

    def get_investigation(self, investigation_id: str) -> Investigation:
        """Load one investigation and all of its append-only records."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT id, status, created_at, updated_at FROM investigations WHERE id = ?",
                (investigation_id,),
            ).fetchone()
            if row is None:
                raise InvestigationNotFoundError(
                    f"Investigation {investigation_id!r} was not found"
                )
            record_rows = connection.execute(
                """
                SELECT id, kind, engine, payload, created_at
                FROM investigation_records
                WHERE investigation_id = ?
                ORDER BY created_at, id
                """,
                (investigation_id,),
            ).fetchall()
        buckets: dict[str, list[InvestigationRecord]] = {
            "context": [],
            "assumption": [],
            "evidence": [],
            "analysis": [],
        }
        for record in record_rows:
            buckets[record["kind"]].append(
                InvestigationRecord(
                    id=record["id"],
                    engine=record["engine"],
                    payload=json.loads(record["payload"]),
                    created_at=record["created_at"],
                )
            )
        return Investigation(
            id=row["id"],
            status=InvestigationStatus.parse(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            context=tuple(buckets["context"]),
            assumptions=tuple(buckets["assumption"]),
            evidence=tuple(buckets["evidence"]),
            analyses=tuple(buckets["analysis"]),
        )

    def record_context(self, investigation_id: str, payload: JsonValue) -> InvestigationRecord:
        return self._append(investigation_id, kind="context", payload=payload)

    def record_assumption(self, investigation_id: str, payload: JsonValue) -> InvestigationRecord:
        return self._append(investigation_id, kind="assumption", payload=payload)

    def record_evidence(self, investigation_id: str, payload: JsonValue) -> InvestigationRecord:
        return self._append(investigation_id, kind="evidence", payload=payload)

    def record_analysis(
        self, investigation_id: str, *, engine: str, payload: JsonValue
    ) -> InvestigationRecord:
        if not engine.strip():
            raise ValueError("Analysis engine must not be empty")
        return self._append(investigation_id, kind="analysis", payload=payload, engine=engine)

    def _append(
        self, investigation_id: str, *, kind: str, payload: JsonValue, engine: str | None = None
    ) -> InvestigationRecord:
        encoded_payload = self._json(payload)
        record = InvestigationRecord(
            id=self._id(kind[:3]),
            payload=json.loads(encoded_payload),
            created_at=timestamp(self._now()),
            engine=engine,
        )
        with self._connection() as connection:
            if (
                connection.execute(
                    "SELECT 1 FROM investigations WHERE id = ?", (investigation_id,)
                ).fetchone()
                is None
            ):
                raise InvestigationNotFoundError(
                    f"Investigation {investigation_id!r} was not found"
                )
            connection.execute(
                """
                INSERT INTO investigation_records
                    (id, investigation_id, kind, engine, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    investigation_id,
                    kind,
                    record.engine,
                    encoded_payload,
                    record.created_at,
                ),
            )
            connection.execute(
                "UPDATE investigations SET updated_at = ? WHERE id = ?",
                (record.created_at, investigation_id),
            )
        return record

    def promote(self, investigation_id: str) -> Investigation:
        """Atomically transition an ephemeral investigation to durable."""
        updated_at = timestamp(self._now())
        with self._connection() as connection:
            result = connection.execute(
                """
                UPDATE investigations
                SET status = ?, updated_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    InvestigationStatus.DURABLE.value,
                    updated_at,
                    investigation_id,
                    InvestigationStatus.EPHEMERAL.value,
                ),
            )
            if result.rowcount == 0:
                row = connection.execute(
                    "SELECT status FROM investigations WHERE id = ?", (investigation_id,)
                ).fetchone()
                if row is None:
                    raise InvestigationNotFoundError(
                        f"Investigation {investigation_id!r} was not found"
                    )
                raise ValueError(f"Investigation {investigation_id!r} is already durable")
        return self.get_investigation(investigation_id)
