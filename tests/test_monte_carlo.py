import math
import platform

import pytest

from pearl_of_wisdom import __version__
from pearl_of_wisdom.engines import MonteCarloEngine, MonteCarloValidationError
from pearl_of_wisdom.engines import monte_carlo as monte_carlo_module


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


@pytest.mark.parametrize(
    "payload",
    [
        {
            "variables": {"x": {"distribution": "constant", "value": 1}},
            "expression": "x",
            "samples": 1,
            "sampls": 100,
        },
        {
            "variables": {"x": {"distribution": "constant", "value": 1, "vale": 100}},
            "expression": "x",
            "samples": 1,
        },
    ],
)
def test_unknown_fields_are_rejected_at_typed_boundaries(payload: dict[str, object]) -> None:
    with pytest.raises(MonteCarloValidationError, match="unknown field"):
        MonteCarloEngine().analyze(payload)


def test_draw_export_preserves_generation_alignment_and_full_run_summary() -> None:
    request = {
        "variables": {
            "x": {"distribution": "uniform", "low": -2, "high": 3},
            "y": {"distribution": "randint", "low": 1, "high": 6},
        },
        "expression": "x * 10 + y",
        "samples": 250,
        "seed": 812,
        "quantiles": [0.05, 0.5, 0.95],
    }

    summary_only = MonteCarloEngine().analyze(request)
    exported = MonteCarloEngine().analyze(
        {**request, "return_draws": True, "draw_variables": ["x", "y"]}
    )
    draws = exported.data["draws"]

    assert {key: value for key, value in exported.data.items() if key != "draws"} == (
        summary_only.data
    )
    assert exported.metadata == summary_only.metadata
    assert draws["schema_version"] == 1
    assert draws["population"] == 250
    assert draws["returned"] == 250
    assert draws["selection"] == "all"
    assert draws["indices"] == list(range(250))
    assert list(draws["inputs"]) == ["x", "y"]
    for x, y, outcome in zip(
        draws["inputs"]["x"],
        draws["inputs"]["y"],
        draws["outcome"],
        strict=True,
    ):
        assert outcome == pytest.approx(x * 10 + y)
    assert draws["provenance"] == {
        "pearl_version": __version__,
        "python_version": platform.python_version(),
        "effective_request": request,
        "input_order": ["x", "y"],
    }


def test_capped_draw_export_is_deterministic_and_does_not_change_engine_rng() -> None:
    request = {
        "variables": {"x": {"distribution": "normal", "mean": 5, "standard_deviation": 2}},
        "expression": "x",
        "samples": 200,
        "seed": 77,
    }

    summary_only = MonteCarloEngine().analyze(request)
    first = MonteCarloEngine().analyze({**request, "return_draws": True, "draw_limit": 11})
    second = MonteCarloEngine().analyze({**request, "return_draws": True, "draw_limit": 11})
    draws = first.data["draws"]

    assert first == second
    assert {key: value for key, value in first.data.items() if key != "draws"} == summary_only.data
    assert draws["returned"] == 11
    assert draws["selection"] == "uniform_without_replacement_v1"
    assert draws["indices"] == sorted(set(draws["indices"]))
    assert len(draws["indices"]) == 11
    assert len(draws["outcome"]) == 11
    assert draws["inputs"] == {}


@pytest.mark.parametrize(
    ("controls", "message"),
    [
        ({"return_draws": 1}, "return_draws must be a boolean"),
        ({"draw_limit": 10}, "draw_limit requires return_draws"),
        ({"draw_variables": []}, "draw_variables requires return_draws"),
        ({"return_draws": True, "draw_limit": True}, "draw_limit"),
        ({"return_draws": True, "draw_limit": 0}, "draw_limit"),
        ({"return_draws": True, "draw_limit": 10_001}, "draw_limit"),
        ({"return_draws": True, "draw_variables": "x"}, "draw_variables must be a list"),
        (
            {"return_draws": True, "draw_variables": ["x", "x"]},
            "draw_variables must contain distinct names",
        ),
        (
            {"return_draws": True, "draw_variables": ["unknown"]},
            "draw_variables contains unknown variable",
        ),
    ],
)
def test_draw_export_controls_are_strict(controls: dict[str, object], message: str) -> None:
    request = {
        "variables": {"x": {"distribution": "constant", "value": 1}},
        "expression": "x",
        "samples": 1,
        **controls,
    }

    with pytest.raises(MonteCarloValidationError, match=message):
        MonteCarloEngine().analyze(request)


def test_false_draw_export_preserves_existing_result_shape() -> None:
    request = {
        "variables": {"x": {"distribution": "constant", "value": 1}},
        "expression": "x",
        "samples": 1,
    }

    assert MonteCarloEngine().analyze({**request, "return_draws": False}) == (
        MonteCarloEngine().analyze(request)
    )


def test_draw_export_supports_contract_boundaries() -> None:
    variables = {
        f"x{index}": {"distribution": "constant", "value": index} for index in range(16)
    }
    result = MonteCarloEngine().analyze(
        {
            "variables": variables,
            "expression": "x0 + x15",
            "samples": 10_001,
            "seed": 4,
            "return_draws": True,
            "draw_variables": list(variables),
        }
    )
    draws = result.data["draws"]

    assert draws["population"] == 10_001
    assert draws["returned"] == 10_000
    assert len(draws["indices"]) == 10_000
    assert all(len(values) == 10_000 for values in draws["inputs"].values())


def test_draw_export_rejects_more_than_sixteen_input_columns() -> None:
    variables = {
        f"x{index}": {"distribution": "constant", "value": index} for index in range(17)
    }
    with pytest.raises(MonteCarloValidationError, match="at most 16"):
        MonteCarloEngine().analyze(
            {
                "variables": variables,
                "expression": "x0",
                "samples": 1,
                "return_draws": True,
                "draw_variables": list(variables),
            }
        )


def test_draw_export_rejects_response_above_json_transport_limit(monkeypatch) -> None:
    monkeypatch.setattr(monte_carlo_module, "MAX_EXPORT_RESPONSE_BYTES", 128)

    with pytest.raises(MonteCarloValidationError, match="JSON response limit"):
        MonteCarloEngine().analyze(
            {
                "variables": {"x": {"distribution": "constant", "value": 1}},
                "expression": "x",
                "samples": 1,
                "return_draws": True,
                "draw_variables": ["x"],
            }
        )


def test_draw_export_stays_bounded_at_maximum_engine_population() -> None:
    result = MonteCarloEngine().analyze(
        {
            "variables": {"x": {"distribution": "constant", "value": 2}},
            "expression": "x",
            "samples": 1_000_000,
            "seed": 3,
            "return_draws": True,
            "draw_limit": 3,
            "draw_variables": ["x"],
        }
    )

    assert result.data["count"] == 1_000_000
    assert result.data["draws"]["population"] == 1_000_000
    assert result.data["draws"]["returned"] == 3
    assert result.data["draws"]["inputs"] == {"x": [2.0, 2.0, 2.0]}
