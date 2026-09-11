"""JSON command-line interface for Pearl of Wisdom investigations."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections.abc import Sequence
from typing import Any

from . import __version__
from .engines import AnalysisEngine, DiscreteBayesEngine, MonteCarloEngine
from .investigation import InvestigationStatus, JsonValue
from .store import InvestigationNotFoundError, InvestigationStore


class CliUsageError(ValueError):
    """Raised instead of letting argparse write non-JSON errors."""


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser whose invalid-input path is machine-readable."""

    def error(self, message: str) -> None:
        raise CliUsageError(message)


ENGINE_FACTORIES = {
    "discrete-bayes": DiscreteBayesEngine,
    "monte-carlo": MonteCarloEngine,
}


def _json_payload(value: str) -> JsonValue:
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError(f"Invalid JSON payload: {error.msg}") from error


def _parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(prog="pearl-of-wisdom")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--db", default=os.environ.get("PEARL_DB", "pearl.sqlite3"), help="SQLite database path"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument(
        "--status", choices=[item.value for item in InvestigationStatus], default="ephemeral"
    )
    commands.add_parser("list")
    show = commands.add_parser("show")
    show.add_argument("investigation_id")
    promote = commands.add_parser("promote")
    promote.add_argument("investigation_id")
    for command in ("record-context", "record-assumption", "record-evidence"):
        record = commands.add_parser(command)
        record.add_argument("investigation_id")
        record.add_argument("--data", required=True, type=_json_payload)
    analysis = commands.add_parser("record-analysis")
    analysis.add_argument("investigation_id")
    analysis.add_argument("--engine", required=True)
    analysis.add_argument("--data", required=True, type=_json_payload)
    run_engine = commands.add_parser(
        "analyze",
        help="run an engine or print a runnable input example",
        description="Run an engine with JSON input, or print a runnable example and its result.",
    )
    run_engine.add_argument(
        "--engine",
        required=True,
        choices=sorted(ENGINE_FACTORIES),
    )
    input_source = run_engine.add_mutually_exclusive_group(required=True)
    input_source.add_argument("--data", type=_json_payload, help="engine request as a JSON object")
    input_source.add_argument(
        "--example",
        action="store_true",
        help="print a runnable request and the result produced from it",
    )
    return parser


def _engine(engine_name: str) -> AnalysisEngine:
    return ENGINE_FACTORIES[engine_name]()


def _analyze(engine_name: str, payload: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(payload, dict):
        raise ValueError("analyze --data must be a JSON object")
    return _engine(engine_name).analyze(payload).to_dict()


def _example(engine_name: str) -> dict[str, JsonValue]:
    engine = _engine(engine_name)
    request = engine.example_request()
    return {"request": request, "result": engine.analyze(request).to_dict()}


def _emit(value: Any, *, stream: Any | None = None) -> None:
    if stream is None:
        stream = sys.stdout
    print(json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True), file=stream)


def _error(code: str, message: str) -> int:
    _emit({"error": {"code": code, "message": message}}, stream=sys.stderr)
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    """Run a single command and return a shell-compatible exit code."""
    parser = _parser()
    try:
        arguments = parser.parse_args(argv)
        command = arguments.command
        if command == "analyze":
            output = (
                _example(arguments.engine)
                if arguments.example
                else _analyze(arguments.engine, arguments.data)
            )
        else:
            store = InvestigationStore(arguments.db)
            if command == "create":
                output = store.create_investigation(
                    status=InvestigationStatus.parse(arguments.status)
                ).to_dict()
            elif command == "list":
                output = [item.to_dict() for item in store.list_investigations()]
            elif command == "show":
                output = store.get_investigation(arguments.investigation_id).to_dict()
            elif command == "promote":
                output = store.promote(arguments.investigation_id).to_dict()
            elif command == "record-context":
                output = store.record_context(arguments.investigation_id, arguments.data).to_dict()
            elif command == "record-assumption":
                output = store.record_assumption(
                    arguments.investigation_id, arguments.data
                ).to_dict()
            elif command == "record-evidence":
                output = store.record_evidence(arguments.investigation_id, arguments.data).to_dict()
            elif command == "record-analysis":
                output = store.record_analysis(
                    arguments.investigation_id,
                    engine=arguments.engine,
                    payload=arguments.data,
                ).to_dict()
            else:  # argparse guarantees the command; defensive for direct callers.
                return _error("invalid_command", f"Unknown command {command!r}")
    except InvestigationNotFoundError as error:
        return _error("investigation_not_found", str(error))
    except CliUsageError as error:
        return _error("invalid_arguments", str(error))
    except sqlite3.Error as error:
        return _error("storage_error", str(error))
    except (ValueError, TypeError) as error:
        return _error("validation_error", str(error))
    except SystemExit as error:
        return int(error.code) if isinstance(error.code, int) else 2
    _emit(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
