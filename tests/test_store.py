from pathlib import Path

import pytest

from pearl_of_wisdom.investigation import InvestigationStatus
from pearl_of_wisdom.store import InvestigationNotFoundError, InvestigationStore


@pytest.fixture
def store(tmp_path: Path) -> InvestigationStore:
    return InvestigationStore(tmp_path / "pearl.sqlite3")


def test_store_creates_and_round_trips_all_record_kinds(store: InvestigationStore) -> None:
    investigation = store.create_investigation()
    store.record_context(investigation.id, {"repository": "pearl"})
    store.record_assumption(investigation.id, {"claim": "tests are representative"})
    store.record_evidence(investigation.id, {"source": "pytest", "result": "passed"})
    store.record_analysis(investigation.id, engine="monte-carlo", payload={"p": 0.75})

    loaded = store.get_investigation(investigation.id)

    assert loaded.id == investigation.id
    assert loaded.context[0].payload == {"repository": "pearl"}
    assert loaded.assumptions[0].payload["claim"] == "tests are representative"
    assert loaded.evidence[0].payload["result"] == "passed"
    assert loaded.analyses[0].engine == "monte-carlo"
    assert loaded.analyses[0].payload == {"p": 0.75}


def test_store_lists_in_creation_order_and_promotes_once(store: InvestigationStore) -> None:
    first = store.create_investigation()
    second = store.create_investigation(status=InvestigationStatus.DURABLE)

    assert [item.id for item in store.list_investigations()] == [first.id, second.id]
    assert store.promote(first.id).status is InvestigationStatus.DURABLE
    with pytest.raises(ValueError, match="already durable"):
        store.promote(first.id)


def test_store_rejects_unknown_investigations(store: InvestigationStore) -> None:
    with pytest.raises(InvestigationNotFoundError):
        store.record_evidence("inv_missing", {"source": "none"})


def test_store_rejects_unknown_analysis_engines(store: InvestigationStore) -> None:
    investigation = store.create_investigation()

    with pytest.raises(ValueError, match="Unknown analysis engine 'bogus'"):
        store.record_analysis(investigation.id, engine="bogus", payload={})

    assert store.get_investigation(investigation.id).analyses == ()


def test_store_rejects_process_local_memory_database() -> None:
    with pytest.raises(ValueError, match=":memory:"):
        InvestigationStore(":memory:")
