"""Exercise the actual Desktop server over stdio, not direct handler calls."""

from __future__ import annotations

import asyncio
import sqlite3
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

ROOT = Path(__file__).parents[1]
SERVER = ROOT / "desktop" / "server.py"


def _server(database: Path, *, environment: dict[str, str] | None = None) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER), "--db", str(database)],
        env=environment,
        cwd=database.parent.parent,
    )


@pytest.mark.parametrize("mode", ["legacy", "auto"])
def test_status_and_discovery_do_not_create_database(tmp_path: Path, mode: str) -> None:
    database = tmp_path / "not-created" / "investigations.sqlite3"

    async def exercise() -> None:
        async with Client(_server(database), mode=mode, read_timeout_seconds=10) as client:
            listed = await client.list_tools()
            tools = {tool.name: tool for tool in listed.tools}
            assert set(tools) == {
                "pearl_status",
                "pearl_example",
                "pearl_analyze",
                "pearl_create_investigation",
                "pearl_list_investigations",
                "pearl_show_investigation",
                "pearl_record",
                "pearl_promote_investigation",
            }
            for name, tool in tools.items():
                assert tool.annotations.open_world_hint is False
                assert tool.annotations.destructive_hint is False
                assert tool.annotations.read_only_hint is (
                    name
                    not in {
                        "pearl_create_investigation",
                        "pearl_record",
                        "pearl_promote_investigation",
                    }
                )
                assert "database" not in tool.input_schema.get("properties", {})
                assert "path" not in tool.input_schema.get("properties", {})
            result = await client.call_tool("pearl_status", {})
            assert not result.is_error
            assert result.structured_content["compatible"] is True
            assert result.structured_content["version"] == "0.4.0"
            assert result.structured_content["required"] == ">=0.4.0,<0.5.0"
            assert result.structured_content["database"] == str(database)
            assert not database.exists()

    asyncio.run(exercise())
    assert not database.parent.exists()


@pytest.mark.parametrize(
    "engine", ["monte-carlo", "discrete-bayes", "decision-analysis", "causal", "system-simulation"]
)
def test_every_engine_example_is_runnable_without_database(tmp_path: Path, engine: str) -> None:
    database = tmp_path / "example-only" / "investigations.sqlite3"

    async def exercise() -> None:
        async with Client(_server(database), mode="legacy", read_timeout_seconds=10) as client:
            example = await client.call_tool("pearl_example", {"engine": engine})
            assert not example.is_error
            analyzed = await client.call_tool(
                "pearl_analyze", {"engine": engine, "data": example.structured_content["request"]}
            )
            assert not analyzed.is_error
            assert analyzed.structured_content == example.structured_content["result"]
            assert analyzed.structured_content["engine"] == engine.replace("-", "_")

    asyncio.run(exercise())
    assert not database.parent.exists()


def test_storage_error_recovers_after_directory_is_fixed(tmp_path: Path) -> None:
    parent = tmp_path / "blocked-directory"
    parent.write_text("Known blocker, not a database directory.")
    database = parent / "investigations.sqlite3"

    async def exercise() -> None:
        async with Client(_server(database), mode="legacy", read_timeout_seconds=10) as client:
            failed = await client.call_tool("pearl_create_investigation", {})
            assert failed.is_error
            assert "storage_error" in failed.content[0].text
            parent.unlink()
            parent.mkdir()
            created = await client.call_tool("pearl_create_investigation", {})
            assert not created.is_error
            listed = await client.call_tool("pearl_list_investigations", {})
            assert not listed.is_error
            assert [item["id"] for item in listed.structured_content["investigations"]] == [
                created.structured_content["id"]
            ]

    asyncio.run(exercise())
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM investigations").fetchone() == (1,)


def test_read_tools_do_not_initialize_an_existing_non_pearl_database(tmp_path: Path) -> None:
    database = tmp_path / "unrelated.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE unrelated (value INTEGER)")
        connection.execute("INSERT INTO unrelated VALUES (42)")
    before = database.read_bytes()

    async def exercise() -> None:
        async with Client(_server(database), mode="legacy", read_timeout_seconds=10) as client:
            listed = await client.call_tool("pearl_list_investigations", {})
            assert listed.is_error
            assert "storage_error" in listed.content[0].text
            shown = await client.call_tool("pearl_show_investigation", {"investigation_id": "fake"})
            assert shown.is_error
            assert "storage_error" in shown.content[0].text

    asyncio.run(exercise())
    assert database.read_bytes() == before
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall() == [("unrelated",)]
        assert connection.execute("SELECT value FROM unrelated").fetchall() == [(42,)]


def test_stateless_exact_calculation(tmp_path: Path) -> None:
    database = tmp_path / "analysis-only" / "investigations.sqlite3"

    async def exercise() -> None:
        async with Client(_server(database), mode="legacy", read_timeout_seconds=10) as client:
            result = await client.call_tool(
                "pearl_analyze",
                {
                    "engine": "monte-carlo",
                    "data": {
                        "variables": {
                            "price": {"distribution": "constant", "value": 12.5},
                            "units": {"distribution": "constant", "value": 8},
                        },
                        "expression": "price * units - 10",
                        "samples": 5,
                        "seed": 71,
                    },
                },
            )
            assert not result.is_error
            assert result.structured_content["data"]["mean"] == 90.0
            assert result.structured_content["metadata"] == {"samples": 5, "seed": 71}

    asyncio.run(exercise())
    assert not database.parent.exists()


def test_durable_history_survives_server_restart(tmp_path: Path) -> None:
    database = tmp_path / "persistent" / "investigations.sqlite3"
    question = {"question": "Will the synthetic release queue exceed capacity?"}
    assumption = {"name": "service_seconds", "value": 2, "units": "seconds"}
    evidence = {"source": "synthetic experiment", "completed": 17, "total": 20}

    async def create() -> str:
        async with Client(_server(database), mode="legacy", read_timeout_seconds=10) as client:
            created = await client.call_tool("pearl_create_investigation", {})
            assert not created.is_error
            investigation_id = created.structured_content["id"]
            assert created.structured_content["status"] == "ephemeral"
            for kind, data in (
                ("context", question),
                ("assumption", assumption),
                ("evidence", evidence),
            ):
                recorded = await client.call_tool(
                    "pearl_record",
                    {"investigation_id": investigation_id, "kind": kind, "data": data},
                )
                assert not recorded.is_error
                assert recorded.structured_content["payload"] == data
            example = await client.call_tool("pearl_example", {"engine": "discrete-bayes"})
            assert not example.is_error
            analyzed = await client.call_tool(
                "pearl_analyze",
                {"engine": "discrete-bayes", "data": example.structured_content["request"]},
            )
            assert not analyzed.is_error
            assert analyzed.structured_content == example.structured_content["result"]
            recorded = await client.call_tool(
                "pearl_record",
                {
                    "investigation_id": investigation_id,
                    "kind": "analysis",
                    "engine": "discrete-bayes",
                    "data": analyzed.structured_content,
                },
            )
            assert not recorded.is_error
            promoted = await client.call_tool(
                "pearl_promote_investigation", {"investigation_id": investigation_id}
            )
            assert not promoted.is_error
            assert promoted.structured_content["status"] == "durable"
            return investigation_id

    investigation_id = asyncio.run(create())

    async def resume() -> None:
        async with Client(_server(database), mode="legacy", read_timeout_seconds=10) as client:
            listed = await client.call_tool("pearl_list_investigations", {})
            assert not listed.is_error
            assert [item["id"] for item in listed.structured_content["investigations"]] == [
                investigation_id
            ]
            shown = await client.call_tool(
                "pearl_show_investigation", {"investigation_id": investigation_id}
            )
            assert not shown.is_error
            value = shown.structured_content
            assert value["status"] == "durable"
            assert [entry["payload"] for entry in value["context"]] == [question]
            assert [entry["payload"] for entry in value["assumptions"]] == [assumption]
            assert [entry["payload"] for entry in value["evidence"]] == [evidence]
            assert value["analyses"][0]["engine"] == "discrete-bayes"

    asyncio.run(resume())

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM investigations").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM investigation_records").fetchone() == (4,)


def test_errors_are_failed_calls_and_do_not_break_next_request(tmp_path: Path) -> None:
    database = tmp_path / "errors" / "investigations.sqlite3"

    async def exercise() -> None:
        async with Client(_server(database), mode="legacy", read_timeout_seconds=10) as client:
            missing = await client.call_tool(
                "pearl_show_investigation", {"investigation_id": "not-a-real-investigation"}
            )
            assert missing.is_error
            assert "investigation_not_found" in missing.content[0].text
            listed = await client.call_tool("pearl_list_investigations", {})
            assert not listed.is_error
            assert listed.structured_content == {"investigations": []}
            assert not database.exists()
            example = await client.call_tool("pearl_example", {"engine": "monte-carlo"})
            assert not example.is_error
            invalid = await client.call_tool(
                "pearl_analyze",
                {
                    "engine": "monte-carlo",
                    "data": example.structured_content["request"] | {"expression": "f()"},
                },
            )
            assert invalid.is_error
            assert "validation_error" in invalid.content[0].text
            created = await client.call_tool("pearl_create_investigation", {})
            assert not created.is_error
            investigation_id = created.structured_content["id"]
            invalid_record = await client.call_tool(
                "pearl_record",
                {"investigation_id": investigation_id, "kind": "analysis", "data": {}},
            )
            assert invalid_record.is_error
            assert "validation_error" in invalid_record.content[0].text
            invalid_record = await client.call_tool(
                "pearl_record",
                {
                    "investigation_id": investigation_id,
                    "kind": "context",
                    "data": {},
                    "engine": "monte-carlo",
                },
            )
            assert invalid_record.is_error
            recorded = await client.call_tool(
                "pearl_record",
                {"investigation_id": investigation_id, "kind": "context", "data": {"ok": True}},
            )
            assert not recorded.is_error
            shown = await client.call_tool(
                "pearl_show_investigation", {"investigation_id": investigation_id}
            )
            assert not shown.is_error
            assert shown.structured_content["analyses"] == []
            assert [entry["payload"] for entry in shown.structured_content["context"]] == [
                {"ok": True}
            ]

    asyncio.run(exercise())
