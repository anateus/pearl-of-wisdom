from datetime import UTC, datetime

import pytest

from pearl_of_wisdom.investigation import Investigation, InvestigationStatus


def test_investigation_serializes_a_typed_durable_envelope() -> None:
    created = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
    investigation = Investigation.new(id="inv_1", now=created)

    assert investigation.to_dict() == {
        "analyses": [],
        "assumptions": [],
        "context": [],
        "created_at": "2026-08-31T12:00:00Z",
        "evidence": [],
        "id": "inv_1",
        "status": "ephemeral",
        "updated_at": "2026-08-31T12:00:00Z",
    }


def test_status_accepts_only_known_values() -> None:
    assert InvestigationStatus("durable") is InvestigationStatus.DURABLE
    with pytest.raises(ValueError, match="Unknown investigation status"):
        InvestigationStatus.parse("draft")
