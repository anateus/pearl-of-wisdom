"""Local stdio MCP transport for Pearl's dependency-free analysis core."""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from pearl_of_wisdom import __version__
from pearl_of_wisdom.engines import ENGINE_FACTORIES
from pearl_of_wisdom.investigation import InvestigationStatus
from pearl_of_wisdom.json_transport import dumps_json
from pearl_of_wisdom.store import InvestigationNotFoundError, InvestigationStore

REQUIRED_CORE = ">=0.4.0,<0.5.0"
Engine = Literal[
    "monte-carlo", "discrete-bayes", "decision-analysis", "causal", "system-simulation"
]
RecordKind = Literal["context", "assumption", "evidence", "analysis"]


def _compatible_core() -> bool:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", __version__)
    return match is not None and (0, 4, 0) <= tuple(map(int, match.groups())) < (0, 5, 0)


def _invoke(operation: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Keep known failures machine-readable and mark them as failed MCP calls."""
    try:
        result = operation()
        dumps_json(result)
        return result
    except InvestigationNotFoundError as error:
        code, message = "investigation_not_found", str(error)
    except (sqlite3.Error, OSError) as error:
        code, message = "storage_error", str(error)
    except (ValueError, TypeError) as error:
        code, message = "validation_error", str(error)
    raise ToolError(dumps_json({"error": {"code": code, "message": message}})) from None


def create_server(database: str | Path) -> MCPServer:
    """Build a server without opening or creating its investigation database."""
    if not str(database).strip() or str(database) == ":memory:":
        raise ValueError("A file-backed investigation database path is required")
    path = Path(database).expanduser().resolve()
    server = MCPServer(
        "Pearl of Wisdom",
        version=__version__,
        log_level="WARNING",
        instructions=(
            "Use pearl_status before Pearl work. Discover an engine with pearl_example, then "
            "call pearl_analyze with explicit inputs and assumptions. Analysis is stateless. "
            "Create an investigation only for a requested durable record, keep its ID, append "
            "context/assumptions/evidence/analysis separately, and verify with "
            "pearl_show_investigation. Never treat example inputs or optional recalled memory "
            "as observed evidence. Tool results are sent to the Claude model account even "
            "though calculation and SQLite storage are local."
        ),
    )
    read_only = ToolAnnotations(
        read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
    )
    append_only = ToolAnnotations(
        read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False
    )

    def guard() -> None:
        if not _compatible_core():
            raise ToolError(
                dumps_json(
                    {
                        "error": {
                            "code": "core_incompatible",
                            "required": REQUIRED_CORE,
                            "message": "Update the Pearl extension before using its tools.",
                        }
                    }
                )
            )

    def store(*, create: bool = False) -> InvestigationStore:
        guard()
        if create:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        elif not path.exists():
            raise InvestigationNotFoundError(
                "No investigation database exists at the configured path"
            )
        return InvestigationStore(path)

    @server.tool(annotations=read_only)
    def pearl_status() -> dict[str, Any]:
        """Check compatibility, available engines, and configured storage without creating state."""
        return {
            "version": __version__,
            "required": REQUIRED_CORE,
            "compatible": _compatible_core(),
            "transport": "stdio",
            "engines": sorted(ENGINE_FACTORIES),
            "database": str(path),
        }

    @server.tool(annotations=read_only)
    def pearl_example(engine: Engine) -> dict[str, Any]:
        """Discover a runnable engine request and its result. Inputs are examples, not evidence."""

        def run() -> dict[str, Any]:
            guard()
            instance = ENGINE_FACTORIES[engine]()
            request = instance.example_request()
            return {"request": request, "result": instance.analyze(request).to_dict()}

        return _invoke(run)

    @server.tool(annotations=read_only)
    def pearl_analyze(engine: Engine, data: dict[str, Any]) -> dict[str, Any]:
        """Run a bounded analysis of explicit JSON inputs without opening a database."""

        def run() -> dict[str, Any]:
            guard()
            dumps_json(data)
            return ENGINE_FACTORIES[engine]().analyze(data).to_dict()

        return _invoke(run)

    @server.tool(annotations=append_only)
    def pearl_create_investigation(
        status: Literal["ephemeral", "durable"] = "ephemeral",
    ) -> dict[str, Any]:
        """Create one requested investigation. Save its ID and resume that same record."""
        return _invoke(
            lambda: (
                store(create=True)
                .create_investigation(status=InvestigationStatus.parse(status))
                .to_dict()
            )
        )

    @server.tool(annotations=read_only)
    def pearl_list_investigations() -> dict[str, Any]:
        """List local investigation envelopes. Does not create a missing database."""

        def run() -> dict[str, Any]:
            guard()
            if not path.exists():
                return {"investigations": []}
            return {"investigations": [item.to_dict() for item in store().list_investigations()]}

        return _invoke(run)

    @server.tool(annotations=read_only)
    def pearl_show_investigation(investigation_id: str) -> dict[str, Any]:
        """Read one investigation and verify its saved records and lifecycle state."""
        return _invoke(lambda: store().get_investigation(investigation_id).to_dict())

    @server.tool(annotations=append_only)
    def pearl_record(
        investigation_id: str,
        kind: RecordKind,
        data: dict[str, Any],
        engine: Engine | None = None,
    ) -> dict[str, Any]:
        """Append one separate context, assumption, evidence, or analyzed-result entry."""

        def run() -> dict[str, Any]:
            guard()
            dumps_json(data)
            if kind == "analysis":
                if engine is None:
                    raise ValueError("An analysis record requires its engine")
                return (
                    store().record_analysis(investigation_id, engine=engine, payload=data).to_dict()
                )
            if engine is not None:
                raise ValueError("Only analysis records accept an engine")
            operation = {
                "context": InvestigationStore.record_context,
                "assumption": InvestigationStore.record_assumption,
                "evidence": InvestigationStore.record_evidence,
            }[kind]
            return operation(store(), investigation_id, data).to_dict()

        return _invoke(run)

    @server.tool(annotations=append_only)
    def pearl_promote_investigation(investigation_id: str) -> dict[str, Any]:
        """Promote a reviewed ephemeral investigation to durable, then return the saved record."""
        return _invoke(lambda: store().promote(investigation_id).to_dict())

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"pearl-of-wisdom MCP {__version__}")
    parser.add_argument(
        "--db",
        default=os.environ.get("PEARL_DB", str(Path.home() / ".pearl-of-wisdom/pearl.sqlite3")),
        help="Local investigation database. Never selected by a model tool argument.",
    )
    arguments = parser.parse_args()
    create_server(arguments.db).run(transport="stdio")


if __name__ == "__main__":
    main()
