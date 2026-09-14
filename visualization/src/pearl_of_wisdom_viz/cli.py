"""Command-line interface for Pearl visualization artifacts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .model import MAX_INPUT_BYTES, VisualizationError, parse_result_bytes
from .render import RenderedArtifact, render_distribution, render_forest


class CliUsageError(ValueError):
    """Raised instead of allowing argparse to emit plain text."""


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliUsageError(message)


def _parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(prog="pearl-of-wisdom-viz")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    dist = commands.add_parser("dist", help="render an empirical cumulative distribution")
    dist.add_argument("--input", type=Path, help="Pearl JSON result; stdin when omitted")
    forest = commands.add_parser("forest", help="compare full-run scenario intervals")
    forest.add_argument("--input", type=Path, action="append", default=[])
    forest.add_argument("--label", action="append", default=[])
    for command in (dist, forest):
        command.add_argument("--quantity", required=True)
        command.add_argument("--unit", required=True)
        command.add_argument("--out", required=True, type=Path)
        command.add_argument("--backend", choices=("bokeh", "matplotlib"), default="bokeh")
        command.add_argument("--resources", choices=("inline", "shared", "cdn"))
        command.add_argument("--caveat", action="append", default=[])
        command.add_argument("--overwrite", action="store_true")
    return parser


def _json(value: Any) -> str:
    return json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True)


def _emit(value: Any, *, stream: Any = None) -> None:
    print(_json(value), file=stream or sys.stdout)


def _error(code: str, message: str) -> int:
    _emit({"error": {"code": code, "message": message}}, stream=sys.stderr)
    return 1


def _read_source(path: Path | None) -> bytes:
    if path is None:
        source = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(source) > MAX_INPUT_BYTES:
            raise VisualizationError("stdin exceeds the 16777216-byte input limit")
        return source
    try:
        size = path.stat().st_size
    except OSError as error:
        raise VisualizationError(f"cannot inspect input {path}: {error.strerror}") from error
    if size > MAX_INPUT_BYTES:
        raise VisualizationError(f"input {path} exceeds the 16777216-byte limit")
    try:
        source = path.read_bytes()
    except OSError as error:
        raise VisualizationError(f"cannot read input {path}: {error.strerror}") from error
    if len(source) > MAX_INPUT_BYTES:
        raise VisualizationError(f"input {path} exceeds the 16777216-byte limit")
    return source


def _resource_mode(arguments: argparse.Namespace) -> str:
    if arguments.backend == "matplotlib":
        if arguments.resources is not None:
            raise VisualizationError("--resources cannot be used with the Matplotlib backend")
        return "inline"
    resources = arguments.resources or os.environ.get("PEARL_VIZ_RESOURCES", "inline")
    if resources not in {"inline", "shared", "cdn"}:
        raise VisualizationError(
            "PEARL_VIZ_RESOURCES must be one of: inline, shared, cdn"
        )
    return resources


def _validate_output(path: Path, backend: str) -> Path:
    expected = ".png" if backend == "matplotlib" else ".html"
    if path.suffix.lower() != expected:
        raise VisualizationError(f"{backend} output requires a {expected} destination")
    return path.expanduser().resolve()


def _publish(path: Path, content: bytes, *, overwrite: bool) -> None:
    if not path.parent.is_dir():
        raise VisualizationError(f"output directory does not exist: {path.parent}")
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o644)
        if overwrite:
            os.replace(temporary, path)
        else:
            try:
                os.link(temporary, path)
            except FileExistsError as error:
                raise VisualizationError(
                    f"output already exists: {path}; pass --overwrite to replace it"
                ) from error
            temporary.unlink()
    except VisualizationError:
        temporary.unlink(missing_ok=True)
        raise
    except OSError as error:
        temporary.unlink(missing_ok=True)
        raise VisualizationError(f"cannot publish output {path}: {error.strerror}") from error


def _version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def _descriptor(
    path: Path,
    artifact: RenderedArtifact,
    sources: tuple[bytes, ...],
) -> dict[str, Any]:
    descriptor = {
        "artifact_path": str(path),
        "media_type": artifact.media_type,
        "resource_mode": artifact.resource_mode,
        "artifact_sha256": hashlib.sha256(artifact.content).hexdigest(),
        "source_sha256": [hashlib.sha256(source).hexdigest() for source in sources],
        "renderer_version": __version__,
        "dependency_versions": {
            "arviz-base": _version("arviz-base"),
            "arviz-plots": _version("arviz-plots"),
            "bokeh": _version("bokeh"),
            "matplotlib": _version("matplotlib"),
        },
        "summaries": artifact.summaries,
    }
    if artifact.shared_asset is not None:
        descriptor["shared_asset"] = artifact.shared_asset
    return descriptor


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = _parser().parse_args(argv)
        resources = _resource_mode(arguments)
        destination = _validate_output(arguments.out, arguments.backend)
        if arguments.command == "dist":
            sources = (_read_source(arguments.input),)
            result = parse_result_bytes(sources[0], require_draws=True)
            artifact = render_distribution(
                result,
                quantity=arguments.quantity,
                unit=arguments.unit,
                backend=arguments.backend,
                resources=resources,
                caveats=tuple(arguments.caveat),
            )
        else:
            if not 2 <= len(arguments.input) <= 8:
                raise VisualizationError("forest requires between two and eight --input files")
            if len(arguments.label) != len(arguments.input):
                raise VisualizationError("forest requires one --label for each --input")
            sources = tuple(_read_source(path) for path in arguments.input)
            results = tuple(parse_result_bytes(source) for source in sources)
            artifact = render_forest(
                results,
                tuple(arguments.label),
                quantity=arguments.quantity,
                unit=arguments.unit,
                backend=arguments.backend,
                resources=resources,
                caveats=tuple(arguments.caveat),
            )
        _publish(destination, artifact.content, overwrite=arguments.overwrite)
        descriptor = _descriptor(destination, artifact, sources)
    except CliUsageError as error:
        return _error("invalid_arguments", str(error))
    except VisualizationError as error:
        return _error("validation_error", str(error))
    except SystemExit as error:
        return int(error.code) if isinstance(error.code, int) else 2
    try:
        _emit(descriptor)
    except BrokenPipeError:
        try:
            return _error(
                "stdout_closed",
                f"artifact was published at {destination}, but its descriptor was not delivered",
            )
        except BrokenPipeError:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
