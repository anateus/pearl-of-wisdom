"""Launch a freshly built MCPB through its actual manifest, outside the checkout."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

from mcp import Client, StdioServerParameters

ROOT = Path(__file__).parents[1]


def test_packaged_uv_server_calculates_and_retains_records(tmp_path: Path) -> None:
    output = tmp_path / "output with spaces"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_desktop_bundle.py"), "--out-dir", str(output)],
        cwd=tmp_path,
        check=True,
        timeout=120,
    )
    version = json.loads((ROOT / "desktop/manifest.json").read_text())["version"]
    artifact = output / f"pearl-of-wisdom-{version}.mcpb"
    extension = tmp_path / "installed extension with spaces"
    extension.mkdir()
    with zipfile.ZipFile(artifact) as archive:
        assert archive.read("server.py") == (ROOT / "desktop/server.py").read_bytes()
        archive.extractall(extension)
    manifest = json.loads((extension / "manifest.json").read_text())
    config = manifest["server"]["mcp_config"]
    data_directory = tmp_path / "persistent data outside extension"
    database = data_directory / "pearl.sqlite3"
    environment = {
        key: value.replace("${user_config.data_directory}", str(data_directory))
        for key, value in config["env"].items()
    } | {"UV_OFFLINE": "1", "UV_PYTHON_DOWNLOADS": "never"}
    parameters = StdioServerParameters(
        command=config["command"],
        args=[argument.replace("${__dirname}", str(extension)) for argument in config["args"]],
        env=environment,
        cwd=tmp_path,
    )
    context = {"question": "Will the synthetic release queue exceed capacity?"}

    async def exercise() -> str:
        async with Client(parameters, mode="legacy", read_timeout_seconds=30) as client:
            listed = await client.list_tools()
            assert {tool.name for tool in listed.tools} == {
                item["name"] for item in manifest["tools"]
            }
            status = await client.call_tool("pearl_status", {})
            assert not status.is_error
            assert status.structured_content["compatible"] is True
            assert status.structured_content["version"] == version
            assert status.structured_content["database"] == str(database)
            for engine in status.structured_content["engines"]:
                example = await client.call_tool("pearl_example", {"engine": engine})
                assert not example.is_error
                analyzed = await client.call_tool(
                    "pearl_analyze",
                    {"engine": engine, "data": example.structured_content["request"]},
                )
                assert not analyzed.is_error
                assert analyzed.structured_content == example.structured_content["result"]
            exact = await client.call_tool(
                "pearl_analyze",
                {
                    "engine": "monte-carlo",
                    "data": {
                        "variables": {"units": {"distribution": "constant", "value": 8}},
                        "expression": "units * 12.5 - 10",
                        "samples": 5,
                        "seed": 71,
                    },
                },
            )
            assert not exact.is_error
            assert exact.structured_content["data"]["mean"] == 90.0
            assert not database.exists()
            created = await client.call_tool("pearl_create_investigation", {})
            assert not created.is_error
            identifier = created.structured_content["id"]
            recorded = await client.call_tool(
                "pearl_record", {"investigation_id": identifier, "kind": "context", "data": context}
            )
            assert not recorded.is_error
            assert recorded.structured_content["payload"] == context
            promoted = await client.call_tool(
                "pearl_promote_investigation", {"investigation_id": identifier}
            )
            assert not promoted.is_error
            assert promoted.structured_content["status"] == "durable"
        async with Client(parameters, mode="legacy", read_timeout_seconds=30) as client:
            listed = await client.call_tool("pearl_list_investigations", {})
            assert not listed.is_error
            assert [item["id"] for item in listed.structured_content["investigations"]] == [
                identifier
            ]
            shown = await client.call_tool(
                "pearl_show_investigation", {"investigation_id": identifier}
            )
            assert not shown.is_error
            assert shown.structured_content["status"] == "durable"
            assert [entry["payload"] for entry in shown.structured_content["context"]] == [context]
        return identifier

    identifier = asyncio.run(exercise())
    assert database.is_file()
    positive = extension / "known-positive.sqlite3"
    positive.touch()
    assert list(extension.rglob("*.sqlite3")) == [positive]
    positive.unlink()
    assert not list(extension.rglob("*.sqlite3"))
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT id, status FROM investigations").fetchall() == [
            (identifier, "durable")
        ]
        rows = connection.execute("SELECT kind, payload FROM investigation_records").fetchall()
        assert [(kind, json.loads(payload)) for kind, payload in rows] == [("context", context)]
