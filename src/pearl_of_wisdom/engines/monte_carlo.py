"""Deterministic Monte Carlo engine with bounded sampling."""

from __future__ import annotations

import math
import platform
import random
import statistics
from bisect import bisect_left, bisect_right
from collections.abc import Callable, Mapping

from .. import __version__
from ..json_transport import json_line_size
from .base import (
    AnalysisResult,
    compile_numeric_expression,
    evaluate_numeric_expression,
    require_only_fields,
)

MAX_SAMPLES = 1_000_000
MAX_DRAW_LIMIT = 10_000
MAX_DRAW_VARIABLES = 16
MAX_THRESHOLDS = 16
MAX_EXPORT_RESPONSE_BYTES = 16 * 1024 * 1024
REQUEST_FIELDS = {
    "draw_limit",
    "draw_variables",
    "expression",
    "quantiles",
    "return_draws",
    "samples",
    "seed",
    "thresholds",
    "variables",
}
DISTRIBUTION_FIELDS = {
    "bernoulli": {"distribution", "probability"},
    "constant": {"distribution", "value"},
    "discrete": {"distribution", "probabilities", "values"},
    "lognormal": {"distribution", "mean", "sigma"},
    "normal": {"distribution", "mean", "standard_deviation"},
    "randint": {"distribution", "high", "low"},
    "triangular": {"distribution", "high", "low", "mode"},
    "uniform": {"distribution", "high", "low"},
}


class MonteCarloValidationError(ValueError):
    """Raised when a Monte Carlo request is malformed or unsafe."""


def _require_mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise MonteCarloValidationError(f"{label} must be an object")
    return value


def _require_number(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise MonteCarloValidationError(f"{label} must be numeric")
    try:
        result = float(value)
    except OverflowError as error:
        raise MonteCarloValidationError(f"{label} must be finite") from error
    if not math.isfinite(result):
        raise MonteCarloValidationError(f"{label} must be finite")
    return result


def _require_probability(value: object, *, label: str) -> float:
    probability = _require_number(value, label=label)
    if not 0 <= probability <= 1:
        raise MonteCarloValidationError(f"{label} must be between 0 and 1")
    return probability


def _require_samples(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MonteCarloValidationError("samples must be an integer between 1 and 1000000")
    if not 1 <= value <= MAX_SAMPLES:
        raise MonteCarloValidationError("samples must be an integer between 1 and 1000000")
    return value


def _quantile(values: list[float], probability: float) -> float:
    if len(values) == 1:
        return values[0]
    index = probability * (len(values) - 1)
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper or values[lower] == values[upper]:
        return values[lower]
    weight = index - lower
    return values[lower] * (1 - weight) + values[upper] * weight


class MonteCarloEngine:
    """Sample independent input distributions and summarize the outcome."""

    name = "monte_carlo"
    capabilities = ("simulation.monte_carlo", "uncertainty.numeric")

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def analyze(self, request: dict[str, object]) -> AnalysisResult:
        request_map = _require_mapping(request, label="request")
        require_only_fields(
            request_map,
            REQUEST_FIELDS,
            label="request",
            error_type=MonteCarloValidationError,
        )
        variables_raw = _require_mapping(request_map.get("variables"), label="variables")
        variables = self._variables(variables_raw)
        expression_raw = request_map.get("expression")
        quantiles_raw = request_map.get("quantiles", [0.05, 0.5, 0.95])
        seed_raw = request_map.get("seed", 0)
        if isinstance(seed_raw, bool) or not isinstance(seed_raw, int):
            raise MonteCarloValidationError("seed must be an integer")
        samples = _require_samples(request_map.get("samples"))
        thresholds = (
            self._thresholds(request_map["thresholds"]) if "thresholds" in request_map else None
        )
        compiled = self._compile_expression(expression_raw)
        quantiles = self._quantiles(quantiles_raw)
        draw_limit, draw_variables = self._draw_export_controls(
            request_map,
            variable_names=tuple(variables),
        )
        selected_indices = (
            self._selected_indices(samples=samples, draw_limit=draw_limit, seed=seed_raw)
            if draw_limit is not None
            else None
        )
        selected_index_set = set(selected_indices) if selected_indices is not None else None
        retained_outcomes = [] if selected_indices is not None else None
        retained_inputs = (
            {name: [] for name in draw_variables} if selected_indices is not None else None
        )
        rng = random.Random(seed_raw)
        try:
            outcomes = []
            for index in range(samples):
                sampled_inputs = {name: sampler(rng) for name, sampler in variables.items()}
                outcome = evaluate_numeric_expression(compiled, sampled_inputs)
                outcomes.append(outcome)
                if selected_index_set is not None and index in selected_index_set:
                    assert retained_outcomes is not None
                    assert retained_inputs is not None
                    retained_outcomes.append(outcome)
                    for name in draw_variables:
                        retained_inputs[name].append(sampled_inputs[name])
        except (ArithmeticError, ValueError) as error:
            raise MonteCarloValidationError(str(error)) from error
        outcomes.sort()
        mean = statistics.fmean(outcomes)
        standard_deviation = statistics.pstdev(outcomes, mu=mean)
        data = {
            "count": samples,
            "mean": mean,
            "standard_deviation": standard_deviation,
            "minimum": outcomes[0],
            "maximum": outcomes[-1],
            "quantiles": {
                self._format_quantile(probability): _quantile(outcomes, probability)
                for probability in quantiles
            },
        }
        if thresholds is not None:
            events = {}
            for name, comparison in thresholds.items():
                operator, value = comparison["operator"], comparison["value"]
                left, right = bisect_left(outcomes, value), bisect_right(outcomes, value)
                matched = {"lt": left, "le": right, "gt": samples - right, "ge": samples - left}
                events[name] = {**comparison, "matched": matched[operator], "total": samples}
            data["thresholds"] = {"schema_version": 1, "events": events}
        if draw_limit is not None:
            assert selected_indices is not None
            assert retained_outcomes is not None
            assert retained_inputs is not None
            returned = len(selected_indices)
            data["draws"] = {
                "schema_version": 1,
                "population": samples,
                "returned": returned,
                "selection": ("all" if returned == samples else "uniform_without_replacement_v1"),
                "indices": selected_indices,
                "outcome": retained_outcomes,
                "inputs": retained_inputs,
                "provenance": {
                    "pearl_version": __version__,
                    "python_version": platform.python_version(),
                    "effective_request": {
                        "variables": dict(variables_raw),
                        "expression": expression_raw,
                        "samples": samples,
                        "seed": seed_raw,
                        "quantiles": quantiles,
                        **({"thresholds": thresholds} if thresholds is not None else {}),
                    },
                    "input_order": list(variables),
                },
            }
        result = AnalysisResult(
            engine=self.name,
            capabilities=self.capabilities,
            data=data,
            metadata={"samples": samples, "seed": seed_raw},
        )
        if draw_limit is not None and json_line_size(result.to_dict()) > MAX_EXPORT_RESPONSE_BYTES:
            raise MonteCarloValidationError(
                "draw export exceeds the 16777216-byte JSON response limit; "
                "reduce draw_limit or draw_variables"
            )
        return result

    def example_request(self) -> dict[str, object]:
        """Return a small request that exercises this engine's public input shape."""
        return {
            "variables": {"duration_ms": {"distribution": "uniform", "low": 40, "high": 80}},
            "expression": "duration_ms",
            "samples": 100,
            "seed": 7,
            "quantiles": [0.05, 0.5, 0.95],
        }

    def _compile_expression(self, expression: object):
        try:
            return compile_numeric_expression(expression if isinstance(expression, str) else "")
        except ValueError as error:
            raise MonteCarloValidationError(str(error)) from error

    @staticmethod
    def _thresholds(value: object) -> dict[str, dict[str, object]]:
        mapping = _require_mapping(value, label="thresholds")
        if not 1 <= len(mapping) <= MAX_THRESHOLDS:
            raise MonteCarloValidationError("thresholds must contain between 1 and 16 comparisons")
        result = {}
        for name, raw in mapping.items():
            if not isinstance(name, str) or not name.strip() or len(name) > 64:
                raise MonteCarloValidationError(
                    "thresholds identifiers must have 1 to 64 characters"
                )
            path = f"thresholds.{name}"
            comparison = _require_mapping(raw, label=path)
            require_only_fields(
                comparison,
                {"operator", "value"},
                label=path,
                error_type=MonteCarloValidationError,
            )
            operator = comparison.get("operator")
            if not isinstance(operator, str) or operator not in {"lt", "le", "gt", "ge"}:
                raise MonteCarloValidationError(f"{path}.operator must be lt, le, gt, or ge")
            result[name] = {
                "operator": operator,
                "value": _require_number(comparison.get("value"), label=f"{path}.value"),
            }
        return result

    def _draw_export_controls(
        self,
        request: Mapping[str, object],
        *,
        variable_names: tuple[str, ...],
    ) -> tuple[int | None, tuple[str, ...]]:
        return_draws = request.get("return_draws", False)
        if not isinstance(return_draws, bool):
            raise MonteCarloValidationError("return_draws must be a boolean")
        if not return_draws:
            if "draw_limit" in request:
                raise MonteCarloValidationError("draw_limit requires return_draws to be true")
            if "draw_variables" in request:
                raise MonteCarloValidationError("draw_variables requires return_draws to be true")
            return None, ()

        draw_limit = request.get("draw_limit", MAX_DRAW_LIMIT)
        if isinstance(draw_limit, bool) or not isinstance(draw_limit, int):
            raise MonteCarloValidationError("draw_limit must be an integer between 1 and 10000")
        if not 1 <= draw_limit <= MAX_DRAW_LIMIT:
            raise MonteCarloValidationError("draw_limit must be an integer between 1 and 10000")

        draw_variables = request.get("draw_variables", [])
        if not isinstance(draw_variables, list):
            raise MonteCarloValidationError("draw_variables must be a list")
        if len(draw_variables) > MAX_DRAW_VARIABLES:
            raise MonteCarloValidationError("draw_variables must contain at most 16 names")
        if any(not isinstance(name, str) for name in draw_variables):
            raise MonteCarloValidationError("draw_variables must contain variable names")
        if len(set(draw_variables)) != len(draw_variables):
            raise MonteCarloValidationError("draw_variables must contain distinct names")
        unknown = [name for name in draw_variables if name not in variable_names]
        if unknown:
            raise MonteCarloValidationError(
                f"draw_variables contains unknown variable {unknown[0]!r}"
            )
        return draw_limit, tuple(draw_variables)

    @staticmethod
    def _selected_indices(*, samples: int, draw_limit: int, seed: int) -> list[int]:
        returned = min(samples, draw_limit)
        if returned == samples:
            return list(range(samples))
        selection_rng = random.Random(f"pearl-draw-selection-v1:{seed}")
        return sorted(selection_rng.sample(range(samples), returned))

    def _variables(self, value: object) -> dict[str, Callable[[random.Random], float]]:
        mapping = _require_mapping(value, label="variables")
        if not mapping:
            raise MonteCarloValidationError("variables must not be empty")
        samplers: dict[str, Callable[[random.Random], float]] = {}
        for name, spec in mapping.items():
            if not isinstance(name, str) or not name.isidentifier():
                raise MonteCarloValidationError("variable names must be valid identifiers")
            samplers[name] = self._sampler(name, spec)
        return samplers

    def _sampler(self, name: str, spec: object) -> Callable[[random.Random], float]:
        distribution = _require_mapping(spec, label=f"variables.{name}")
        kind = distribution.get("distribution")
        if not isinstance(kind, str):
            raise MonteCarloValidationError(f"variables.{name}.distribution must be a string")
        allowed_fields = DISTRIBUTION_FIELDS.get(kind)
        if allowed_fields is None:
            raise MonteCarloValidationError(
                f"variables.{name}.distribution {kind!r} is unsupported"
            )
        require_only_fields(
            distribution,
            allowed_fields,
            label=f"variables.{name}",
            error_type=MonteCarloValidationError,
        )
        if kind == "constant":
            constant = _require_number(distribution.get("value"), label=f"variables.{name}.value")
            return lambda rng: constant
        if kind == "normal":
            mean = _require_number(distribution.get("mean"), label=f"variables.{name}.mean")
            standard_deviation = _require_number(
                distribution.get("standard_deviation"),
                label=f"variables.{name}.standard_deviation",
            )
            if standard_deviation < 0:
                raise MonteCarloValidationError(
                    f"variables.{name}.standard_deviation must be non-negative"
                )
            return lambda rng: rng.normalvariate(mean, standard_deviation)
        if kind == "uniform":
            low = _require_number(distribution.get("low"), label=f"variables.{name}.low")
            high = _require_number(distribution.get("high"), label=f"variables.{name}.high")
            if low > high:
                raise MonteCarloValidationError(f"variables.{name}.low must be <= high")
            return lambda rng: rng.uniform(low, high)
        if kind == "bernoulli":
            probability = _require_probability(
                distribution.get("probability"),
                label=f"variables.{name}.probability",
            )
            return lambda rng: 1.0 if rng.random() < probability else 0.0
        if kind == "triangular":
            low = _require_number(distribution.get("low"), label=f"variables.{name}.low")
            high = _require_number(distribution.get("high"), label=f"variables.{name}.high")
            mode = _require_number(distribution.get("mode"), label=f"variables.{name}.mode")
            if low > high or not low <= mode <= high:
                raise MonteCarloValidationError(
                    f"variables.{name} must satisfy low <= mode <= high"
                )
            return lambda rng: rng.triangular(low, high, mode)
        if kind == "lognormal":
            mean = _require_number(distribution.get("mean"), label=f"variables.{name}.mean")
            sigma = _require_number(distribution.get("sigma"), label=f"variables.{name}.sigma")
            if sigma < 0:
                raise MonteCarloValidationError(f"variables.{name}.sigma must be non-negative")
            return lambda rng: rng.lognormvariate(mean, sigma)
        if kind == "randint":
            low_raw = distribution.get("low")
            high_raw = distribution.get("high")
            if isinstance(low_raw, bool) or not isinstance(low_raw, int):
                raise MonteCarloValidationError(f"variables.{name}.low must be an integer")
            if isinstance(high_raw, bool) or not isinstance(high_raw, int):
                raise MonteCarloValidationError(f"variables.{name}.high must be an integer")
            if low_raw > high_raw:
                raise MonteCarloValidationError(f"variables.{name}.low must be <= high")
            return lambda rng: float(rng.randint(low_raw, high_raw))
        if kind == "discrete":
            values = distribution.get("values")
            probabilities = distribution.get("probabilities")
            if not isinstance(values, list) or not values:
                raise MonteCarloValidationError(f"variables.{name}.values must be a non-empty list")
            if not isinstance(probabilities, list) or len(probabilities) != len(values):
                raise MonteCarloValidationError(
                    f"variables.{name}.probabilities must align with values"
                )
            normalized_values = [
                _require_number(item, label=f"variables.{name}.values[{index}]")
                for index, item in enumerate(values)
            ]
            normalized_probabilities = [
                _require_probability(item, label=f"variables.{name}.probabilities[{index}]")
                for index, item in enumerate(probabilities)
            ]
            if not math.isclose(sum(normalized_probabilities), 1.0, rel_tol=0, abs_tol=1e-9):
                raise MonteCarloValidationError(f"variables.{name}.probabilities must sum to 1")
            return lambda rng: float(
                rng.choices(normalized_values, normalized_probabilities, k=1)[0]
            )
        raise AssertionError(f"unhandled supported distribution {kind!r}")

    def _quantiles(self, value: object) -> list[float]:
        if not isinstance(value, list) or not value:
            raise MonteCarloValidationError("quantiles must be a non-empty list")
        result: list[float] = []
        for index, probability in enumerate(value):
            normalized = _require_probability(probability, label=f"quantiles[{index}]")
            result.append(normalized)
        return result

    @staticmethod
    def _format_quantile(probability: float) -> str:
        return format(probability, ".15g")
