"""Finite decision analysis and the expected value of information."""

from __future__ import annotations

import math
import sys
from collections.abc import Mapping
from fractions import Fraction

from .base import require_only_fields
from .protocol import AnalysisResult, JsonValue


class DecisionAnalysisValidationError(ValueError):
    """Raised when a finite decision model is invalid or exceeds its bounds."""


def _mapping(value: object, label: str, *, nonempty: bool = True) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise DecisionAnalysisValidationError(f"{label} must be an object")
    if nonempty and not value:
        raise DecisionAnalysisValidationError(f"{label} must be a non-empty object")
    if any(not isinstance(key, str) or not key.strip() for key in value):
        raise DecisionAnalysisValidationError(f"{label} keys must be non-empty strings")
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DecisionAnalysisValidationError(f"{label} must be a finite number")
    try:
        number = float(value)
    except OverflowError as error:
        raise DecisionAnalysisValidationError(f"{label} must be a finite number") from error
    if not math.isfinite(number):
        raise DecisionAnalysisValidationError(f"{label} must be a finite number")
    return number


def _distribution(value: Mapping[str, object], label: str) -> dict[str, float]:
    probabilities = {key: _number(item, f"{label}.{key}") for key, item in value.items()}
    if any(not 0 <= probability <= 1 for probability in probabilities.values()):
        raise DecisionAnalysisValidationError(f"{label} probabilities must be between 0 and 1")
    total = math.fsum(probabilities.values())
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise DecisionAnalysisValidationError(f"{label} probabilities must sum to 1")
    # Correct accepted floating-point normalization error before computing utilities.
    return {key: probability / total for key, probability in probabilities.items()}


def _complete(value: Mapping[str, object], keys: Mapping[str, object], label: str) -> None:
    if value.keys() != keys.keys():
        raise DecisionAnalysisValidationError(f"{label} must contain exactly the expected keys")


def _as_float(value: Fraction) -> float:
    try:
        result = float(value)
    except OverflowError as error:
        raise DecisionAnalysisValidationError("calculation exceeds finite numeric range") from error
    if not math.isfinite(result):
        raise DecisionAnalysisValidationError("calculation exceeds finite numeric range")
    if value != 0 and abs(result) < sys.float_info.min:
        raise DecisionAnalysisValidationError(
            "calculation underflow exceeds floating-point precision"
        )
    return result


def _scores(
    actions: Mapping[str, Mapping[str, Fraction]], weights: Mapping[str, Fraction]
) -> dict[str, Fraction]:
    # Input floats have power-of-two denominators, so exact weighted sums keep
    # bounded bit widths. Do not round joint weights before comparing policies.
    return {
        name: sum((weight * utilities[state] for state, weight in weights.items()), Fraction())
        for name, utilities in actions.items()
    }


def _optimal(scores: Mapping[str, Fraction]) -> list[str]:
    best = max(scores.values())
    return [name for name, score in scores.items() if score == best]


class DecisionAnalysisEngine:
    """Compare decisions under a supplied utility and observation model."""

    name = "decision_analysis"
    capabilities = ("decision.expected_utility", "decision.value_of_information")

    def __init__(self, *, max_cells: int = 1_000_000) -> None:
        if isinstance(max_cells, bool) or not isinstance(max_cells, int) or max_cells < 1:
            raise DecisionAnalysisValidationError("max_cells must be a positive integer")
        self.max_cells = max_cells

    def _bound(self, cells: int) -> None:
        if cells > self.max_cells:
            raise DecisionAnalysisValidationError(
                f"decision model exceeds max_cells={self.max_cells}"
            )

    def _tests(
        self, value: object, states: dict[str, float], actions: int, cells: int
    ) -> tuple[dict[str, tuple[dict[str, dict[str, float]], float]], int]:
        raw_tests = _mapping(value, "tests", nonempty=False)
        self._bound(cells * (1 + len(raw_tests)))
        tests: dict[str, tuple[dict[str, dict[str, float]], float]] = {}
        for name, raw_test in raw_tests.items():
            label = f"tests.{name}"
            test = _mapping(raw_test, label)
            require_only_fields(
                test,
                {"likelihoods", "cost"},
                label=label,
                error_type=DecisionAnalysisValidationError,
            )
            cost = _number(test.get("cost", 0), f"{label}.cost")
            if cost < 0:
                raise DecisionAnalysisValidationError(f"{label}.cost must be nonnegative")
            raw_likelihoods = _mapping(test.get("likelihoods"), f"{label}.likelihoods")
            _complete(raw_likelihoods, states, f"{label}.likelihoods")
            likelihoods: dict[str, dict[str, float]] = {}
            outcomes: Mapping[str, object] | None = None
            for state, raw_row in raw_likelihoods.items():
                row_label = f"{label}.likelihoods.{state}"
                row = _mapping(raw_row, row_label)
                if outcomes is None:
                    outcomes = row
                    cells += len(states) * actions * len(row)
                    self._bound(cells)
                else:
                    _complete(row, outcomes, row_label)
                likelihoods[state] = _distribution(row, row_label)
            tests[name] = (likelihoods, cost)
        return tests, cells

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def example_request(self) -> dict[str, object]:
        return {
            "states": {"wet": 0.25, "dry": 0.75},
            "actions": {
                "carry": {"wet": -2, "dry": -2},
                "leave": {"wet": -10, "dry": 0},
            },
            "tests": {
                "forecast": {
                    "likelihoods": {
                        "wet": {"rain": 0.8, "clear": 0.2},
                        "dry": {"rain": 0.2, "clear": 0.8},
                    },
                    "cost": 0.25,
                }
            },
        }

    def analyze(self, request: Mapping[str, object]) -> AnalysisResult:
        request = _mapping(request, "request")
        require_only_fields(
            request,
            {"states", "actions", "tests"},
            label="request",
            error_type=DecisionAnalysisValidationError,
        )
        raw_states = _mapping(request.get("states"), "states")
        raw_actions = _mapping(request.get("actions"), "actions")
        cells = len(raw_states) * len(raw_actions)
        self._bound(cells)
        states = _distribution(raw_states, "states")
        actions: dict[str, dict[str, Fraction]] = {}
        for name, raw_action in raw_actions.items():
            action = _mapping(raw_action, f"actions.{name}")
            _complete(action, states, f"actions.{name}")
            actions[name] = {
                state: Fraction.from_float(_number(action[state], f"actions.{name}.{state}"))
                for state in states
            }
        tests, cells = self._tests(request.get("tests", {}), states, len(actions), cells)

        states = {state: Fraction.from_float(probability) for state, probability in states.items()}
        scores = _scores(actions, states)
        expected = {name: _as_float(score) for name, score in scores.items()}
        optimal_actions = _optimal(scores)
        best_by_state = {
            state: max(action[state] for action in actions.values()) for state in states
        }
        regret = {
            name: {state: _as_float(best_by_state[state] - utilities[state]) for state in states}
            for name, utilities in actions.items()
        }
        perfect_score = sum((states[state] * best_by_state[state] for state in states), Fraction())
        expected_regret = {name: _as_float(perfect_score - score) for name, score in scores.items()}
        evpi = _as_float(perfect_score - scores[optimal_actions[0]])
        test_results = {
            name: self._test_result(states, actions, optimal_actions[0], likelihoods, cost)
            for name, (likelihoods, cost) in tests.items()
        }
        return AnalysisResult(
            engine=self.name,
            capabilities=self.capabilities,
            data={
                "expected_utilities": expected,
                "optimal_actions": optimal_actions,
                "expected_utility": expected[optimal_actions[0]],
                "regret": regret,
                "expected_regret": expected_regret,
                "expected_utility_with_perfect_information": _as_float(perfect_score),
                "evpi": evpi,
                "tests": test_results,
            },
            metadata={
                "states": len(states),
                "actions": len(actions),
                "tests": len(tests),
                "cells": cells,
                "max_cells": self.max_cells,
                "utility_convention": "larger is better; test costs use the same utility scale",
            },
        )

    @staticmethod
    def _test_result(
        states: dict[str, Fraction],
        actions: dict[str, dict[str, Fraction]],
        baseline: str,
        likelihoods: dict[str, dict[str, float]],
        cost: float,
    ) -> dict[str, JsonValue]:
        observations: dict[str, JsonValue] = {}
        gains: list[Fraction] = []
        informed_utilities: list[Fraction] = []
        for outcome in next(iter(likelihoods.values())):
            joint = {
                state: prior * Fraction.from_float(likelihoods[state][outcome])
                for state, prior in states.items()
            }
            probability = sum(joint.values(), Fraction())
            if probability == 0:
                observations[outcome] = {
                    "probability": 0.0,
                    "posterior": None,
                    "expected_utilities": {},
                    "optimal_actions": [],
                    "expected_utility": None,
                }
                continue
            posterior = {state: _as_float(mass / probability) for state, mass in joint.items()}
            scores = _scores(actions, joint)
            expected = {name: _as_float(score / probability) for name, score in scores.items()}
            optimal_actions = _optimal(scores)
            observations[outcome] = {
                "probability": _as_float(probability),
                "posterior": posterior,
                "expected_utilities": expected,
                "optimal_actions": optimal_actions,
                "expected_utility": expected[optimal_actions[0]],
            }
            informed_utilities.append(scores[optimal_actions[0]])
            gains.append(scores[optimal_actions[0]] - scores[baseline])
        evsi = sum(gains, Fraction())
        return {
            "cost": cost,
            "expected_utility_with_information": _as_float(sum(informed_utilities, Fraction())),
            "evsi": _as_float(evsi),
            "net_evsi": _as_float(evsi - Fraction.from_float(cost)),
            "observations": observations,
        }
