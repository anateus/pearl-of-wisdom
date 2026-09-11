"""Deterministic Monte Carlo engine with bounded sampling."""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Callable, Mapping

from .base import AnalysisResult, compile_numeric_expression, evaluate_numeric_expression

MAX_SAMPLES = 1_000_000


class MonteCarloValidationError(ValueError):
    """Raised when a Monte Carlo request is malformed or unsafe."""


def _require_mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise MonteCarloValidationError(f"{label} must be an object")
    return value


def _require_number(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise MonteCarloValidationError(f"{label} must be numeric")
    if not math.isfinite(value):
        raise MonteCarloValidationError(f"{label} must be finite")
    return float(value)


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
    if lower == upper:
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
        variables = self._variables(request_map.get("variables"))
        expression_raw = request_map.get("expression")
        quantiles_raw = request_map.get("quantiles", [0.05, 0.5, 0.95])
        seed_raw = request_map.get("seed", 0)
        if isinstance(seed_raw, bool) or not isinstance(seed_raw, int):
            raise MonteCarloValidationError("seed must be an integer")
        samples = _require_samples(request_map.get("samples"))
        compiled = self._compile_expression(expression_raw)
        quantiles = self._quantiles(quantiles_raw)
        rng = random.Random(seed_raw)
        try:
            outcomes = sorted(
                evaluate_numeric_expression(
                    compiled,
                    {name: sampler(rng) for name, sampler in variables.items()},
                )
                for _ in range(samples)
            )
        except (ArithmeticError, ValueError) as error:
            raise MonteCarloValidationError(str(error)) from error
        mean = statistics.fmean(outcomes)
        standard_deviation = statistics.pstdev(outcomes, mu=mean)
        return AnalysisResult(
            engine=self.name,
            capabilities=self.capabilities,
            data={
                "count": samples,
                "mean": mean,
                "standard_deviation": standard_deviation,
                "minimum": outcomes[0],
                "maximum": outcomes[-1],
                "quantiles": {
                    self._format_quantile(probability): _quantile(outcomes, probability)
                    for probability in quantiles
                },
            },
            metadata={"samples": samples, "seed": seed_raw},
        )

    def _compile_expression(self, expression: object):
        try:
            return compile_numeric_expression(expression if isinstance(expression, str) else "")
        except ValueError as error:
            raise MonteCarloValidationError(str(error)) from error

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
        raise MonteCarloValidationError(f"variables.{name}.distribution {kind!r} is unsupported")

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
