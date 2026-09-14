"""Strict result model consumed by visualization backends."""

from __future__ import annotations

import hashlib
import json
import math
import operator
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

MAX_INPUT_BYTES = 16 * 1024 * 1024


class VisualizationError(ValueError):
    """A user-correctable visualization input or output error."""


@dataclass(frozen=True, slots=True)
class Summary:
    count: int
    mean: float
    standard_deviation: float
    minimum: float
    maximum: float
    quantiles: dict[float, float]

    def require_quantile(self, probability: float) -> float:
        try:
            return self.quantiles[probability]
        except KeyError as error:
            raise VisualizationError(
                f"data.quantiles is missing required quantile {probability:g}"
            ) from error


@dataclass(frozen=True, slots=True)
class Draws:
    population: int
    returned: int
    selection: str
    indices: tuple[int, ...]
    outcomes: tuple[float, ...]
    inputs: dict[str, tuple[float, ...]]
    pearl_version: str
    python_version: str
    effective_request: dict[str, Any]
    input_order: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PearlResult:
    summary: Summary
    draws: Draws | None
    metadata: dict[str, Any]
    source_sha256: str
    thresholds: dict[str, Threshold] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Threshold:
    operator: str
    value: float
    matched: int
    total: int

    @property
    def fraction(self) -> float:
        return self.matched / self.total

    def matches(self, value: float) -> bool:
        return {"lt": operator.lt, "le": operator.le, "gt": operator.gt, "ge": operator.ge}[
            self.operator
        ](value, self.value)


def _duplicate_safe_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VisualizationError(f"JSON contains duplicate key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise VisualizationError(f"JSON constant {value} is not finite")


def _mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise VisualizationError(f"{path} must be an object")
    return value


def _list(value: object, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise VisualizationError(f"{path} must be an array")
    return value


def _integer(value: object, path: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise VisualizationError(f"{path} must be an integer")
    if minimum is not None and value < minimum:
        raise VisualizationError(f"{path} must be at least {minimum}")
    return value


def _number(value: object, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise VisualizationError(f"{path} must be numeric")
    try:
        result = float(value)
    except OverflowError as error:
        raise VisualizationError(f"{path} must be finite") from error
    if not math.isfinite(result):
        raise VisualizationError(f"{path} must be finite")
    return result


def _summary(data: Mapping[str, Any]) -> Summary:
    count = _integer(data.get("count"), "data.count", minimum=1)
    mean = _number(data.get("mean"), "data.mean")
    standard_deviation = _number(data.get("standard_deviation"), "data.standard_deviation")
    minimum = _number(data.get("minimum"), "data.minimum")
    maximum = _number(data.get("maximum"), "data.maximum")
    if standard_deviation < 0:
        raise VisualizationError("data.standard_deviation must be non-negative")
    if not minimum <= mean <= maximum:
        raise VisualizationError("data summary ordering must satisfy minimum <= mean <= maximum")

    raw_quantiles = _mapping(data.get("quantiles"), "data.quantiles")
    quantiles: dict[float, float] = {}
    for label, raw_value in raw_quantiles.items():
        try:
            probability = float(label)
        except (TypeError, ValueError) as error:
            raise VisualizationError(
                f"data.quantiles key {label!r} must be a probability"
            ) from error
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise VisualizationError(f"data.quantiles key {label!r} must be between 0 and 1")
        if probability in quantiles:
            raise VisualizationError(f"data.quantiles repeats probability {probability:g}")
        quantiles[probability] = _number(raw_value, f"data.quantiles.{label}")
    ordered = [quantiles[probability] for probability in sorted(quantiles)]
    if ordered != sorted(ordered) or any(not minimum <= value <= maximum for value in ordered):
        raise VisualizationError(
            "data quantile summary ordering must stay between minimum and maximum"
        )
    return Summary(count, mean, standard_deviation, minimum, maximum, quantiles)


def _numeric_tuple(value: object, path: str) -> tuple[float, ...]:
    items = _list(value, path)
    if not items:
        raise VisualizationError(f"{path} must not be empty")
    return tuple(_number(item, f"{path}[{index}]") for index, item in enumerate(items))


def _draws(value: object, summary: Summary) -> Draws:
    draw_map = _mapping(value, "data.draws")
    version = _integer(draw_map.get("schema_version"), "data.draws.schema_version")
    if version != 1:
        raise VisualizationError(f"data.draws.schema_version {version} is unsupported; expected 1")
    population = _integer(draw_map.get("population"), "data.draws.population", minimum=1)
    returned = _integer(draw_map.get("returned"), "data.draws.returned", minimum=1)
    if population != summary.count:
        raise VisualizationError("data.draws.population must equal data.count")
    if returned > population:
        raise VisualizationError("data.draws.returned must not exceed population")

    selection = draw_map.get("selection")
    if selection not in {"all", "uniform_without_replacement_v1"}:
        raise VisualizationError("data.draws.selection is unsupported")

    raw_indices = _list(draw_map.get("indices"), "data.draws.indices")
    indices = tuple(
        _integer(item, f"data.draws.indices[{index}]", minimum=0)
        for index, item in enumerate(raw_indices)
    )
    outcomes = _numeric_tuple(draw_map.get("outcome"), "data.draws.outcome")
    if len(indices) != returned or len(outcomes) != returned:
        raise VisualizationError("data.draws arrays must have equal lengths matching returned")
    if selection == "all" and returned != population:
        raise VisualizationError("data.draws.selection 'all' requires every population row")
    if selection != "all" and returned == population:
        raise VisualizationError("data.draws.selection must be 'all' when every row is returned")
    if len(set(indices)) != len(indices):
        raise VisualizationError("data.draws.indices must be unique")
    if tuple(sorted(indices)) != indices:
        raise VisualizationError("data.draws.indices must be in ascending generation order")
    if any(index >= population for index in indices):
        raise VisualizationError("data.draws.indices must be in range for population")
    if selection == "all" and indices != tuple(range(population)):
        raise VisualizationError("data.draws.selection 'all' requires every generation index")

    provenance = _mapping(draw_map.get("provenance"), "data.draws.provenance")
    pearl_version = provenance.get("pearl_version")
    python_version = provenance.get("python_version")
    if not isinstance(pearl_version, str) or not pearl_version:
        raise VisualizationError("data.draws.provenance.pearl_version must be nonempty")
    if not isinstance(python_version, str) or not python_version:
        raise VisualizationError("data.draws.provenance.python_version must be nonempty")
    effective_request = dict(
        _mapping(provenance.get("effective_request"), "data.draws.provenance.effective_request")
    )
    declared_variables = _mapping(
        effective_request.get("variables"),
        "data.draws.provenance.effective_request.variables",
    )
    if (
        _integer(
            effective_request.get("samples"),
            "data.draws.provenance.effective_request.samples",
            minimum=1,
        )
        != population
    ):
        raise VisualizationError("effective request samples must equal data.draws.population")
    raw_input_order = _list(provenance.get("input_order"), "data.draws.provenance.input_order")
    if any(not isinstance(name, str) or not name for name in raw_input_order):
        raise VisualizationError("data.draws.provenance.input_order must contain names")
    input_order = tuple(raw_input_order)
    if len(set(input_order)) != len(input_order) or set(input_order) != set(declared_variables):
        raise VisualizationError(
            "data.draws.provenance.input_order must list every declared input once"
        )

    raw_inputs = _mapping(draw_map.get("inputs"), "data.draws.inputs")
    inputs: dict[str, tuple[float, ...]] = {}
    for name, values in raw_inputs.items():
        if name not in declared_variables:
            raise VisualizationError(f"data.draws.inputs.{name} is not a declared input")
        column = _numeric_tuple(values, f"data.draws.inputs.{name}")
        if len(column) != returned:
            raise VisualizationError("data.draws input columns must have equal lengths")
        inputs[name] = column

    return Draws(
        population,
        returned,
        selection,
        indices,
        outcomes,
        inputs,
        pearl_version,
        python_version,
        effective_request,
        input_order,
    )


def _thresholds(value: object, summary: Summary, draws: Draws | None) -> dict[str, Threshold]:
    raw = _mapping(value, "data.thresholds")
    if set(raw) != {"schema_version", "events"}:
        raise VisualizationError("data.thresholds requires only schema_version and events")
    if _integer(raw["schema_version"], "data.thresholds.schema_version") != 1:
        raise VisualizationError("data.thresholds.schema_version must be 1")
    events = _mapping(raw["events"], "data.thresholds.events")
    if not 1 <= len(events) <= 16:
        raise VisualizationError("data.thresholds.events requires 1 to 16 comparisons")
    result = {}
    for name, item in events.items():
        path = f"data.thresholds.events.{name}"
        if not isinstance(name, str) or not name.strip() or len(name) > 64:
            raise VisualizationError("thresholds identifiers must have 1 to 64 characters")
        event = _mapping(item, path)
        if set(event) != {"operator", "value", "matched", "total"}:
            raise VisualizationError(f"{path} requires operator, value, matched, and total")
        comparison = event["operator"]
        if not isinstance(comparison, str) or comparison not in {"lt", "le", "gt", "ge"}:
            raise VisualizationError(f"{path}.operator must be lt, le, gt, or ge")
        threshold = Threshold(
            comparison,
            _number(event["value"], f"{path}.value"),
            _integer(event["matched"], f"{path}.matched", minimum=0),
            _integer(event["total"], f"{path}.total", minimum=1),
        )
        if threshold.total != summary.count or threshold.matched > threshold.total:
            raise VisualizationError(f"{path} has inconsistent counts")
        endpoints = [threshold.matches(summary.minimum), threshold.matches(summary.maximum)]
        if (all(endpoints) and threshold.matched != threshold.total) or (
            not any(endpoints) and threshold.matched != 0
        ):
            raise VisualizationError(f"{path} counts contradict the full-run extrema")
        if draws is not None:
            retained_matches = sum(threshold.matches(outcome) for outcome in draws.outcomes)
            omitted = draws.population - draws.returned
            if not retained_matches <= threshold.matched <= retained_matches + omitted:
                raise VisualizationError(f"{path} counts contradict retained outcomes")
            definitions = _mapping(
                draws.effective_request.get("thresholds"), "effective_request.thresholds"
            )
            expected = {"operator": comparison, "value": threshold.value}
            definition = _mapping(definitions.get(name), f"effective_request.thresholds.{name}")
            _number(definition.get("value"), f"effective_request.thresholds.{name}.value")
            if definition != expected:
                raise VisualizationError(f"{path} contradicts effective_request.thresholds")
        result[name] = threshold
    return result


def parse_result_bytes(source: bytes, *, require_draws: bool = False) -> PearlResult:
    """Parse one Pearl result from exact source bytes."""

    if len(source) > MAX_INPUT_BYTES:
        raise VisualizationError("input exceeds the 16777216-byte limit")
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as error:
        raise VisualizationError("input must be UTF-8 JSON") from error
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_duplicate_safe_object,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as error:
        raise VisualizationError(f"input is not complete JSON: {error.msg}") from error
    envelope = _mapping(parsed, "result")
    if envelope.get("engine") != "monte_carlo":
        raise VisualizationError("result.engine must be 'monte_carlo'")
    data = _mapping(envelope.get("data"), "data")
    summary = _summary(data)
    metadata = dict(_mapping(envelope.get("metadata"), "metadata"))
    if "samples" in metadata and (
        _integer(metadata["samples"], "metadata.samples", minimum=1) != summary.count
    ):
        raise VisualizationError("metadata.samples must equal data.count")
    draws = _draws(data["draws"], summary) if "draws" in data else None
    if require_draws and draws is None:
        raise VisualizationError(
            "distribution rendering requires data.draws schema 1; rerun with return_draws=true"
        )
    return PearlResult(
        summary=summary,
        draws=draws,
        metadata=metadata,
        source_sha256=hashlib.sha256(source).hexdigest(),
        thresholds=_thresholds(data["thresholds"], summary, draws) if "thresholds" in data else {},
    )
