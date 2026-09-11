"""Typed records used by durable Pearl investigations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


class InvestigationStatus(StrEnum):
    """The lifecycle state of an investigation."""

    EPHEMERAL = "ephemeral"
    DURABLE = "durable"

    @classmethod
    def parse(cls, value: str) -> InvestigationStatus:
        """Parse a status with a stable, user-facing validation error."""
        try:
            return cls(value)
        except ValueError as error:
            allowed = ", ".join(status.value for status in cls)
            raise ValueError(
                f"Unknown investigation status {value!r}; expected one of: {allowed}"
            ) from error


def timestamp(value: datetime) -> str:
    """Render an aware timestamp in a portable UTC form."""
    if value.tzinfo is None:
        raise ValueError("Timestamps must be timezone-aware")
    utc_value = value.astimezone(UTC)
    timespec = "seconds" if utc_value.microsecond == 0 else "microseconds"
    return utc_value.isoformat(timespec=timespec).replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class InvestigationRecord:
    """A timestamped JSON payload appended to an investigation."""

    id: str
    payload: JsonValue
    created_at: str
    engine: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "created_at": self.created_at,
            "id": self.id,
            "payload": self.payload,
        }
        if self.engine is not None:
            result["engine"] = self.engine
        return result


@dataclass(frozen=True, slots=True)
class Investigation:
    """Immutable envelope reconstructed from the append-only SQLite records."""

    id: str
    status: InvestigationStatus
    created_at: str
    updated_at: str
    context: tuple[InvestigationRecord, ...] = field(default_factory=tuple)
    assumptions: tuple[InvestigationRecord, ...] = field(default_factory=tuple)
    evidence: tuple[InvestigationRecord, ...] = field(default_factory=tuple)
    analyses: tuple[InvestigationRecord, ...] = field(default_factory=tuple)

    @classmethod
    def new(
        cls,
        *,
        id: str,
        now: datetime,
        status: InvestigationStatus = InvestigationStatus.EPHEMERAL,
    ) -> Investigation:
        """Create an empty envelope using a caller-generated immutable ID."""
        if not id:
            raise ValueError("Investigation ID must not be empty")
        rendered = timestamp(now)
        return cls(id=id, status=status, created_at=rendered, updated_at=rendered)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly, deterministically ordered envelope."""
        return {
            "analyses": [record.to_dict() for record in self.analyses],
            "assumptions": [record.to_dict() for record in self.assumptions],
            "context": [record.to_dict() for record in self.context],
            "created_at": self.created_at,
            "evidence": [record.to_dict() for record in self.evidence],
            "id": self.id,
            "status": self.status.value,
            "updated_at": self.updated_at,
        }
