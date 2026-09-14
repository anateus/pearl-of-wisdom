import copy

import pytest

from pearl_of_wisdom.engines import MonteCarloEngine, MonteCarloValidationError


@pytest.mark.parametrize("value", [3, -3, 0.1])
@pytest.mark.parametrize("samples", [3, 5, 17])
def test_constant_quantiles_remain_exact_and_within_full_run_extrema(value, samples):
    result = MonteCarloEngine().analyze(
        {
            "variables": {"x": {"distribution": "constant", "value": value}},
            "expression": "x",
            "samples": samples,
            "return_draws": True,
            "thresholds": {"target": {"operator": "le", "value": value}},
        }
    )
    assert set(result.data["quantiles"].values()) == {float(value)}
    assert result.data["thresholds"]["events"]["target"]["matched"] == samples


def test_thresholds_distinguish_strict_comparisons_and_count_the_whole_run() -> None:
    result = MonteCarloEngine().analyze(
        {
            "variables": {"x": {"distribution": "constant", "value": 3}},
            "expression": "x",
            "samples": 5,
            "return_draws": True,
            "draw_limit": 1,
            "thresholds": {
                operator: {"operator": operator, "value": 3}
                for operator in ("lt", "le", "gt", "ge")
            },
        }
    )
    assert result.data["thresholds"] == {
        "schema_version": 1,
        "events": {
            operator: {"operator": operator, "value": 3.0, "matched": matched, "total": 5}
            for operator, matched in (("lt", 0), ("le", 5), ("gt", 0), ("ge", 5))
        },
    }
    assert result.data["draws"]["returned"] == 1


@pytest.mark.parametrize("export", [False, True])
def test_thresholds_preserve_outcomes_summaries_and_rng(export: bool) -> None:
    request = {
        "variables": {"x": {"distribution": "uniform", "low": -3, "high": 8}},
        "expression": "x",
        "samples": 120,
        "seed": 19,
        "return_draws": export,
    }
    thresholds = {"target": {"operator": "le", "value": 2}}
    baseline = MonteCarloEngine().analyze(request)
    counted = MonteCarloEngine().analyze({**request, "thresholds": thresholds})
    comparable = copy.deepcopy(counted.data)
    comparable.pop("thresholds")
    if export:
        assert (
            comparable["draws"]["provenance"]["effective_request"].pop("thresholds") == thresholds
        )
    assert comparable == baseline.data
    assert counted.metadata == baseline.metadata


def test_capped_draws_cannot_hide_a_full_run_threshold_match() -> None:
    request = {
        "variables": {"x": {"distribution": "bernoulli", "probability": 0.001}},
        "expression": "x",
        "samples": 10000,
        "seed": 7,
        "return_draws": True,
    }
    all_draws = MonteCarloEngine().analyze(request).data["draws"]["outcome"]
    expected = sum(value > 0 for value in all_draws)
    assert 0 < expected < 100
    result = MonteCarloEngine().analyze(
        {**request, "draw_limit": 1, "thresholds": {"rare": {"operator": "gt", "value": 0}}}
    )
    assert result.data["draws"]["outcome"] == [0.0]
    assert result.data["thresholds"]["events"]["rare"]["matched"] == expected
    assert result.data["thresholds"]["events"]["rare"]["total"] == 10000


@pytest.mark.parametrize(
    "thresholds",
    [
        None,
        [],
        {},
        {"": {"operator": "le", "value": 1}},
        {"x" * 65: {"operator": "le", "value": 1}},
        {"bad": {"operator": "eq", "value": 1}},
        {"bad": {"operator": [], "value": 1}},
        {"bad": {"operator": "le", "value": True}},
        {"bad": {"operator": "le", "value": float("inf")}},
        {"bad": {"operator": "le", "value": 10**400}},
        {"bad": {"operator": "le", "value": 1, "extra": 3}},
        {"bad": {"operator": "le"}},
        {str(i): {"operator": "le", "value": i} for i in range(17)},
    ],
)
def test_threshold_definitions_are_bounded_and_strict(thresholds: object) -> None:
    with pytest.raises(MonteCarloValidationError, match="thresholds"):
        MonteCarloEngine().analyze(
            {
                "variables": {"x": {"distribution": "constant", "value": 3}},
                "expression": "x",
                "samples": 5,
                "thresholds": thresholds,
            }
        )
