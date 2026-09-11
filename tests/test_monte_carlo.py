import math

import pytest

from pearl_of_wisdom.engines import MonteCarloEngine, MonteCarloValidationError


def test_constant_model_has_independently_known_statistics() -> None:
    result = MonteCarloEngine().analyze(
        {
            "variables": {
                "price": {"distribution": "constant", "value": 12.5},
                "units": {"distribution": "constant", "value": 8},
            },
            "expression": "price * units - 10",
            "samples": 5,
            "seed": 71,
            "quantiles": [0, 0.5, 1],
        }
    )

    assert result.engine == "monte_carlo"
    assert result.data == {
        "count": 5,
        "mean": 90.0,
        "standard_deviation": 0.0,
        "minimum": 90.0,
        "maximum": 90.0,
        "quantiles": {"0": 90.0, "0.5": 90.0, "1": 90.0},
    }
    assert result.metadata == {"samples": 5, "seed": 71}


def test_seed_makes_random_model_reproducible() -> None:
    request = {
        "variables": {
            "demand": {"distribution": "normal", "mean": 100, "standard_deviation": 8},
            "price": {"distribution": "uniform", "low": 9, "high": 12},
            "sale": {"distribution": "bernoulli", "probability": 0.25},
        },
        "expression": "demand * price + sale * 25",
        "samples": 100,
        "seed": 20260831,
    }

    first = MonteCarloEngine().analyze(request)
    second = MonteCarloEngine().analyze(request)
    different_seed = MonteCarloEngine().analyze({**request, "seed": 20260832})

    assert first == second
    assert first != different_seed
    assert first.data["count"] == 100
    assert math.isfinite(first.data["mean"])


@pytest.mark.parametrize(
    "distribution",
    [
        {"distribution": "triangular", "low": 1, "high": 3, "mode": 2},
        {"distribution": "lognormal", "mean": 0, "sigma": 0.2},
        {"distribution": "randint", "low": 1, "high": 6},
        {
            "distribution": "discrete",
            "values": [10, 20],
            "probabilities": [0.75, 0.25],
        },
    ],
)
def test_common_distributions_produce_finite_results(distribution: object) -> None:
    result = MonteCarloEngine().analyze(
        {
            "variables": {"x": distribution},
            "expression": "x",
            "samples": 20,
            "seed": 4,
        }
    )

    assert result.data["count"] == 20
    assert math.isfinite(result.data["mean"])


@pytest.mark.parametrize("samples", [0, 1_000_001, True, 3.5])
def test_sample_count_is_explicitly_bounded(samples: object) -> None:
    with pytest.raises(MonteCarloValidationError, match="samples"):
        MonteCarloEngine().analyze(
            {
                "variables": {"x": {"distribution": "constant", "value": 1}},
                "expression": "x",
                "samples": samples,
                "seed": 1,
            }
        )


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').getcwd()",
        "(1).__class__",
        "[x for x in (1, 2)]",
        "2 ** 1000",
        "unknown + 1",
    ],
)
def test_expression_language_rejects_unsafe_or_unbounded_operations(expression: str) -> None:
    with pytest.raises(MonteCarloValidationError, match="expression"):
        MonteCarloEngine().analyze(
            {
                "variables": {"x": {"distribution": "constant", "value": 1}},
                "expression": expression,
                "samples": 1,
                "seed": 1,
            }
        )


@pytest.mark.parametrize("expression", ["x / 0", "1e308 * 1e308"])
def test_expression_runtime_failures_are_validation_errors(expression: str) -> None:
    with pytest.raises(MonteCarloValidationError, match="expression"):
        MonteCarloEngine().analyze(
            {
                "variables": {"x": {"distribution": "constant", "value": 1}},
                "expression": expression,
                "samples": 1,
                "seed": 1,
            }
        )


def test_expression_size_is_bounded() -> None:
    with pytest.raises(MonteCarloValidationError, match="expression"):
        MonteCarloEngine().analyze(
            {
                "variables": {"x": {"distribution": "constant", "value": 1}},
                "expression": "x+" * 2_100 + "x",
                "samples": 1,
                "seed": 1,
            }
        )
