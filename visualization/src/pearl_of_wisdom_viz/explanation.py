"""Bind authored context to saved calculations without executing model code."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model import (
    MAX_INPUT_BYTES,
    PearlResult,
    Threshold,
    VisualizationError,
    _duplicate_safe_object,
    _integer,
    _list,
    _mapping,
    _number,
    _reject_constant,
    parse_result_bytes,
)

MAX_CONTEXT_BYTES = 256 * 1024


def text(value: object, path: str, *, limit: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise VisualizationError(f"{path} must be nonempty text of at most {limit} characters")
    return value.strip()


def fields(value: object, path: str, required: set[str], optional: set[str] | None = None) -> dict:
    mapping = _mapping(value, path)
    missing, extra = required - mapping.keys(), mapping.keys() - required - (optional or set())
    if missing or extra:
        raise VisualizationError(
            f"{path}: missing fields {sorted(missing)}; unknown fields {sorted(extra)}"
        )
    return dict(mapping)


def read_bounded(path: Path, limit: int) -> bytes:
    try:
        with path.open("rb") as handle:
            source = handle.read(limit + 1)
    except OSError as error:
        raise VisualizationError(f"cannot read {path}: {error.strerror}") from error
    if len(source) > limit:
        raise VisualizationError(f"{path} exceeds the {limit}-byte input limit")
    return source


@dataclass(frozen=True, slots=True)
class Assumption:
    name: str
    label: str
    unit: str
    description: str
    status: str
    note: str
    reference: str | None


@dataclass(frozen=True, slots=True)
class Change:
    path: str
    description: str
    before: Any
    after: Any


@dataclass(frozen=True, slots=True)
class Scenario:
    identifier: str
    label: str
    source: bytes
    result: PearlResult
    threshold: Threshold
    changes: tuple[Change, ...]


@dataclass(frozen=True, slots=True)
class Explanation:
    question: str
    quantity: str
    unit: str
    subject: str
    target_id: str
    model_explanation: str
    assumptions: tuple[Assumption, ...]
    limitations: tuple[str, ...]
    scenarios: tuple[Scenario, ...]
    context_sha256: str
    illustrative: bool


def _leaves(value: dict, prefix: str = "") -> dict[str, Any]:
    result = {}
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict) and item:
            result.update(_leaves(item, path))
        else:
            result[path] = item
    return result


def _computational_fields(result: PearlResult) -> dict[str, Any]:
    assert result.draws is not None
    request = result.draws.effective_request
    return _leaves({"variables": request["variables"], "expression": request["expression"]})


def _assumptions(raw: object) -> tuple[Assumption, ...]:
    inputs = _mapping(raw, "model.inputs")
    if not 1 <= len(inputs) <= 64:
        raise VisualizationError("model.inputs requires 1 to 64 described variables")
    result = []
    for name, item in inputs.items():
        if not name.isidentifier():
            raise VisualizationError("model.inputs keys must be variable identifiers")
        path = f"model.inputs.{name}"
        item = fields(item, path, {"label", "unit", "description", "evidence"})
        evidence = fields(item["evidence"], f"{path}.evidence", {"status", "note"}, {"reference"})
        status = text(evidence["status"], f"{path}.evidence.status")
        if status not in {"assumed", "observed", "inferred"}:
            raise VisualizationError(
                f"{path}.evidence.status must be assumed, observed, or inferred"
            )
        reference = (
            text(evidence["reference"], f"{path}.evidence.reference")
            if "reference" in evidence
            else None
        )
        if status != "assumed" and reference is None:
            raise VisualizationError(f"{path}: {status} inputs require an evidence reference")
        result.append(
            Assumption(
                name,
                text(item["label"], f"{path}.label", limit=120),
                text(item["unit"], f"{path}.unit", limit=120),
                text(item["description"], f"{path}.description"),
                status,
                text(evidence["note"], f"{path}.evidence.note"),
                reference,
            )
        )
    return tuple(result)


def load_explanation(path: Path) -> Explanation:
    source = read_bounded(path, MAX_CONTEXT_BYTES)
    try:
        raw = json.loads(
            source.decode("utf-8"),
            object_pairs_hook=_duplicate_safe_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VisualizationError("context must be complete UTF-8 JSON") from error
    raw = fields(
        raw,
        "context",
        {"schema_version", "question", "outcome", "target", "model", "scenarios", "illustrative"},
    )
    if _integer(raw["schema_version"], "context.schema_version") != 1:
        raise VisualizationError("context.schema_version must be 1")
    if not isinstance(raw["illustrative"], bool):
        raise VisualizationError("context.illustrative must be a boolean")
    outcome = fields(raw["outcome"], "outcome", {"label", "unit", "subject"})
    target = fields(raw["target"], "target", {"id", "operator", "value"})
    target_id = text(target["id"], "target.id", limit=64)
    comparison = text(target["operator"], "target.operator")
    if comparison not in {"lt", "le", "gt", "ge"}:
        raise VisualizationError("target.operator must be lt, le, gt, or ge")
    target_value = _number(target["value"], "target.value")
    model = fields(raw["model"], "model", {"explanation", "inputs", "limitations"})
    assumptions = _assumptions(model["inputs"])
    limitations = tuple(
        text(item, "model.limitations[]")
        for item in _list(model["limitations"], "model.limitations")
    )
    if not 1 <= len(limitations) <= 32:
        raise VisualizationError("model.limitations requires 1 to 32 explicit limitations")
    raw_scenarios = _list(raw["scenarios"], "scenarios")
    if not 1 <= len(raw_scenarios) <= 8:
        raise VisualizationError("scenarios requires between one and eight saved results")
    scenarios, identifiers, labels = [], set(), set()
    remaining = MAX_INPUT_BYTES
    baseline = {}
    for index, item in enumerate(raw_scenarios):
        item = fields(item, f"scenarios[{index}]", {"id", "label", "source", "sha256", "changes"})
        identifier = text(item["id"], "scenario.id", limit=64)
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", identifier) or identifier in identifiers:
            raise VisualizationError("scenario.id must be a unique simple identifier")
        identifiers.add(identifier)
        label = text(item["label"], "scenario.label", limit=120)
        if label in labels:
            raise VisualizationError("scenario labels must be unique")
        labels.add(label)
        filename = text(item["source"], "scenario.source")
        if "://" in filename:
            raise VisualizationError("scenario.source must name a local file")
        result_source = read_bounded(path.parent / filename, remaining)
        remaining -= len(result_source)
        expected_hash = text(item["sha256"], "scenario.sha256", limit=64)
        if hashlib.sha256(result_source).hexdigest() != expected_hash:
            raise VisualizationError(
                f"scenario {identifier}: stale source SHA-256; regenerate the context"
            )
        result = parse_result_bytes(result_source, require_draws=True)
        assert result.draws is not None
        request = result.draws.effective_request
        text(request.get("expression"), "effective_request.expression")
        if {assumption.name for assumption in assumptions} != set(request["variables"]):
            raise VisualizationError("model.inputs must describe exactly the declared variables")
        for name, distribution in request["variables"].items():
            _mapping(distribution, f"effective_request.variables.{name}")
        for quantile in (0.05, 0.5, 0.95):
            result.summary.require_quantile(quantile)
        event = result.thresholds.get(target_id)
        if event is None:
            raise VisualizationError(
                f"scenario {identifier} lacks threshold {target_id!r}; rerun with thresholds"
            )
        if event.operator != comparison or event.value != target_value:
            raise VisualizationError(
                f"scenario {identifier}: threshold does not match the context target"
            )
        current = _computational_fields(result)
        if index == 0:
            baseline = current
        actual = {
            key for key in baseline.keys() | current.keys() if baseline.get(key) != current.get(key)
        }
        changes = []
        for change in _list(item["changes"], "scenario.changes"):
            change = fields(change, "scenario.changes[]", {"path", "description"})
            key = text(change["path"], "scenario.changes[].path")
            changes.append(
                Change(
                    key,
                    text(change["description"], "scenario.changes[].description"),
                    baseline.get(key),
                    current.get(key),
                )
            )
        if (
            len({change.path for change in changes}) != len(changes)
            or {change.path for change in changes} != actual
        ):
            raise VisualizationError(
                f"scenario {identifier}: changes must describe exactly {sorted(actual)}"
            )
        scenarios.append(Scenario(identifier, label, result_source, result, event, tuple(changes)))
    return Explanation(
        text(raw["question"], "question", limit=500),
        text(outcome["label"], "outcome.label", limit=120),
        text(outcome["unit"], "outcome.unit", limit=120),
        text(outcome["subject"], "outcome.subject", limit=120),
        target_id,
        text(model["explanation"], "model.explanation"),
        assumptions,
        limitations,
        tuple(scenarios),
        hashlib.sha256(source).hexdigest(),
        raw["illustrative"],
    )


def frequency(event: Threshold) -> str:
    if event.matched == 0:
        return "None in this run"
    if event.matched == event.total:
        return "All in this run"
    rounded = round(100 * event.fraction)
    if rounded == 0:
        return "Fewer than 1 in 100"
    if rounded == 100:
        return "More than 99 in 100"
    return f"About {rounded} in 100"
