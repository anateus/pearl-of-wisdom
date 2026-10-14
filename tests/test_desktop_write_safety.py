"""Failure-path data safety for non-creating Desktop MCP writes."""

from __future__ import annotations

import asyncio
import sqlite3
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

SERVER = Path(__file__).parents[1] / "desktop" / "server.py"


@pytest.mark.parametrize("operation", ["pearl_record", "pearl_promote_investigation"])
def test_failed_noncreating_write_leaves_foreign_database_unchanged(
    tmp_path: Path, operation: str
) -> None:
    database = tmp_path / "foreign.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE unrelated (value INTEGER)")
        connection.execute("INSERT INTO unrelated VALUES (42)")
    before = database.read_bytes()
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER), "--db", str(database)],
        cwd=tmp_path,
    )
    arguments = {"investigation_id": "synthetic-not-created"}
    if operation == "pearl_record":
        arguments |= {"kind": "context", "data": {"question": "Synthetic failure-path check"}}

    async def exercise() -> None:
        async with Client(parameters, mode="legacy", read_timeout_seconds=10) as client:
            result = await client.call_tool(operation, arguments)
            assert result.is_error

    asyncio.run(exercise())
    assert database.read_bytes() == before
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall() == [("unrelated",)]
        assert connection.execute("SELECT value FROM unrelated").fetchall() == [(42,)]


def test_noncreating_write_does_not_recreate_database_removed_before_connect(
    tmp_path: Path,
) -> None:
    database = tmp_path / "removed.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE unrelated (value INTEGER)")
    bootstrap = tmp_path / "disappearing-database-server.py"
    bootstrap.write_text(
        "import runpy\nfrom pathlib import Path\n"
        f"namespace = runpy.run_path({str(SERVER)!r})\n"
        f"database = Path({str(database)!r})\n"
        "sqlite = namespace['sqlite3']\noriginal = sqlite.connect\n"
        "def connect(target, *args, **kwargs):\n"
        "    if str(target) in (str(database), database.as_uri() + '?mode=rw'):\n"
        "        database.unlink(missing_ok=True)\n"
        "    return original(target, *args, **kwargs)\n"
        "sqlite.connect = connect\n"
        "namespace['create_server'](database).run(transport='stdio')\n"
    )
    parameters = StdioServerParameters(command=sys.executable, args=[str(bootstrap)], cwd=tmp_path)

    async def exercise() -> None:
        async with Client(parameters, mode="legacy", read_timeout_seconds=10) as client:
            result = await client.call_tool(
                "pearl_promote_investigation", {"investigation_id": "synthetic-not-created"}
            )
            assert result.is_error
            assert "storage_error" in result.content[0].text

    asyncio.run(exercise())
    assert not database.exists()
