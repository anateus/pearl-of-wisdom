import json
import math
from copy import deepcopy
from itertools import permutations

import pytest

from pearl_of_wisdom.engines.decision_analysis import (
    DecisionAnalysisEngine,
    DecisionAnalysisValidationError,
)
from pearl_of_wisdom.engines.protocol import AnalysisEngine


def test_expected_utility_regret_and_perfect_information() -> None:
    request = DecisionAnalysisEngine().example_request()
    request.pop("tests", None)
    result = DecisionAnalysisEngine().analyze(request)

    # Carrying costs 2 in either state; leaving costs 10 on the 1/4 wet days.
    # Knowing the weather would mean carrying only on wet days: utility -0.5.
    assert result.data["expected_utilities"] == {"carry": -2.0, "leave": -2.5}
    assert result.data["optimal_actions"] == ["carry"]
    assert result.data["expected_utility"] == -2
    assert result.data["regret"] == {
        "carry": {"wet": 0.0, "dry": 2.0},
        "leave": {"wet": 8.0, "dry": 0.0},
    }
    assert result.data["expected_regret"] == {"carry": 1.5, "leave": 2.0}
    assert result.data["expected_utility_with_perfect_information"] == -0.5
    assert result.data["evpi"] == 1.5
    assert result.data["tests"] == {}


def test_noisy_observation_changes_decision_with_explicit_cost() -> None:
    request = DecisionAnalysisEngine().example_request()
    request["tests"] = {
        "forecast": {
            "likelihoods": {
                "wet": {"rain": 0.8, "clear": 0.2},
                "dry": {"rain": 0.2, "clear": 0.8},
            },
            "cost": 0.25,
        }
    }
    result = DecisionAnalysisEngine().analyze(request).data["tests"]["forecast"]

    # P(rain)=.35. Carry when rain; leave when clear. Expected utility:
    # -.35*2 - .25*.2*10 = -1.2, hence .8 improvement before a .25 cost.
    assert result["cost"] == 0.25
    assert result["expected_utility_with_information"] == pytest.approx(-1.2)
    assert result["evsi"] == pytest.approx(0.8)
    assert result["net_evsi"] == pytest.approx(0.55)
    rain = result["observations"]["rain"]
    assert rain["probability"] == pytest.approx(0.35)
    assert rain["posterior"] == pytest.approx({"wet": 4 / 7, "dry": 3 / 7})
    assert rain["expected_utilities"] == pytest.approx({"carry": -2, "leave": -40 / 7})
    assert rain["optimal_actions"] == ["carry"]
    clear = result["observations"]["clear"]
    assert clear["optimal_actions"] == ["leave"]
    assert clear["expected_utility"] == pytest.approx(-10 / 13)


def test_perfect_useless_and_costly_tests_are_evaluated_independently() -> None:
    request = DecisionAnalysisEngine().example_request()
    perfect = {
        "wet": {"wet": 1, "dry": 0},
        "dry": {"wet": 0, "dry": 1},
    }
    request["tests"] = {
        "perfect": {"likelihoods": perfect},
        "costly": {"likelihoods": perfect, "cost": 2},
        "useless": {
            "likelihoods": {
                "wet": {"heads": 0.5, "tails": 0.5},
                "dry": {"heads": 0.5, "tails": 0.5},
            }
        },
    }
    data = DecisionAnalysisEngine().analyze(request).data

    assert data["tests"]["perfect"]["evsi"] == data["evpi"] == 1.5
    assert data["tests"]["perfect"]["net_evsi"] == 1.5
    assert data["tests"]["costly"]["net_evsi"] == -0.5
    assert data["tests"]["useless"]["evsi"] == 0


def test_impossible_observations_have_no_posterior_or_recommended_action() -> None:
    request = {
        "states": {"possible": 1, "impossible": 0},
        "actions": {"act": {"possible": 4, "impossible": 99}},
        "tests": {
            "check": {
                "likelihoods": {
                    "possible": {"yes": 1, "no": 0},
                    "impossible": {"yes": 0, "no": 1},
                }
            }
        },
    }
    observation = (
        DecisionAnalysisEngine().analyze(request).data["tests"]["check"]["observations"]["no"]
    )
    assert observation == {
        "probability": 0.0,
        "posterior": None,
        "expected_utilities": {},
        "optimal_actions": [],
        "expected_utility": None,
    }


def test_all_exact_ties_are_retained_before_and_after_observation() -> None:
    request = {
        "states": {"a": 0.5, "b": 0.5},
        "actions": {"first": {"a": 1, "b": 1}, "second": {"a": 1, "b": 1}},
        "tests": {"none": {"likelihoods": {"a": {"same": 1}, "b": {"same": 1}}}},
    }
    data = DecisionAnalysisEngine().analyze(request).data

    assert data["optimal_actions"] == ["first", "second"]
    assert data["tests"]["none"]["observations"]["same"]["optimal_actions"] == ["first", "second"]
    assert data["evpi"] == 0
    assert data["tests"]["none"]["evsi"] == 0


def test_tiny_information_value_is_preserved_against_large_baseline_utility() -> None:
    request = {
        "states": {"rare": 1e-30, "usual": 1},
        "actions": {"safe": {"rare": 1, "usual": 1}, "risky": {"rare": 2, "usual": 0}},
        "tests": {
            "perfect": {
                "likelihoods": {
                    "rare": {"rare": 1, "usual": 0},
                    "usual": {"rare": 0, "usual": 1},
                }
            }
        },
    }
    data = DecisionAnalysisEngine().analyze(request).data

    assert data["expected_utility"] == data["expected_utility_with_perfect_information"] == 1
    assert data["optimal_actions"] == ["safe"]
    assert data["evpi"] == 1e-30
    assert data["tests"]["perfect"]["evsi"] == 1e-30


def test_near_optimal_action_is_not_silently_reported_as_a_tie() -> None:
    request = {
        "states": {"certain": 1},
        "actions": {"best": {"certain": 1}, "worse": {"certain": 1 - 1e-12}},
    }
    assert DecisionAnalysisEngine().analyze(request).data["optimal_actions"] == ["best"]


def test_example_is_fresh_protocol_compatible_and_strict_json_serializable() -> None:
    engine = DecisionAnalysisEngine()
    assert isinstance(engine, AnalysisEngine)
    assert engine.supports("decision.expected_utility")
    assert engine.supports("decision.value_of_information")
    assert not engine.supports("unknown")
    request = engine.example_request()
    before = deepcopy(request)
    result = engine.analyze(request)
    assert request == before
    assert result.data["tests"]["forecast"]["evsi"] == pytest.approx(0.8)
    assert result.data["tests"]["forecast"]["net_evsi"] == pytest.approx(0.55)
    request["states"]["wet"] = 99
    request["tests"]["forecast"]["likelihoods"]["wet"]["rain"] = 99
    assert engine.example_request() == before
    serialized = json.loads(json.dumps(result.to_dict(), allow_nan=False))
    assert serialized["engine"] == "decision_analysis"


@pytest.mark.parametrize("value", [True, False, "1", None, math.nan, math.inf, -math.inf, 10**400])
@pytest.mark.parametrize("field", ["probability", "utility", "cost", "likelihood"])
def test_all_numeric_fields_reject_nonfinite_or_non_numeric_values(value, field) -> None:
    request = {
        "states": {"state": 1},
        "actions": {"act": {"state": 0}},
        "tests": {"check": {"likelihoods": {"state": {"yes": 1}}, "cost": 0}},
    }
    if field == "probability":
        request["states"]["state"] = value
    elif field == "utility":
        request["actions"]["act"]["state"] = value
    elif field == "cost":
        request["tests"]["check"]["cost"] = value
    else:
        request["tests"]["check"]["likelihoods"]["state"]["yes"] = value
    with pytest.raises(DecisionAnalysisValidationError, match="finite number"):
        DecisionAnalysisEngine().analyze(request)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        ((), [], "request must be an object"),
        (("states",), {}, "non-empty object"),
        (("states",), {"": 1}, "non-empty strings"),
        (("states",), {1: 1}, "non-empty strings"),
        (("states",), {"a": 0.2, "b": 0.2}, "sum to 1"),
        (("states", "wet"), -0.1, "between 0 and 1"),
        (("states", "wet"), 1.1, "between 0 and 1"),
        (("actions",), {}, "non-empty object"),
        (("actions", "carry"), {"wet": -2}, "exactly"),
        (("actions", "carry", "unexpected"), 0, "exactly"),
        (("unexpected",), 0, "unknown field"),
        (("tests",), [], "must be an object"),
        (("tests", "check", "unexpected"), 0, "unknown field"),
        (("tests", "check", "cost"), -1, "nonnegative"),
        (("tests", "check", "likelihoods"), {"wet": {"yes": 1}}, "exactly"),
        (("tests", "check", "likelihoods", "wet"), {}, "non-empty object"),
        (("tests", "check", "likelihoods", "wet"), {"yes": 0.4}, "sum to 1"),
        (("tests", "check", "likelihoods", "dry"), {"other": 1}, "exactly"),
        (("tests", "check", "likelihoods", "dry"), {"yes": 1, "extra": 0}, "exactly"),
    ],
)
def test_invalid_or_incomplete_tables_and_unknown_fields_are_rejected(path, value, message) -> None:
    request = DecisionAnalysisEngine().example_request()
    request["tests"] = {"check": {"likelihoods": {"wet": {"yes": 1}, "dry": {"yes": 1}}}}
    if path:
        target = request
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    else:
        request = value
    with pytest.raises(DecisionAnalysisValidationError, match=message):
        DecisionAnalysisEngine().analyze(request)


@pytest.mark.parametrize("max_cells", [0, -1, True, 1.5, "10"])
def test_invalid_work_limit_is_rejected(max_cells) -> None:
    with pytest.raises(DecisionAnalysisValidationError, match="positive integer"):
        DecisionAnalysisEngine(max_cells=max_cells)


def test_work_limit_counts_all_actions_states_tests_and_observations() -> None:
    request = DecisionAnalysisEngine().example_request()
    request.pop("tests", None)
    with pytest.raises(DecisionAnalysisValidationError, match="max_cells=3"):
        DecisionAnalysisEngine(max_cells=3).analyze(request)
    assert DecisionAnalysisEngine(max_cells=4).analyze(request).metadata["cells"] == 4
    test = {"likelihoods": {"wet": {"yes": 0.5, "no": 0.5}, "dry": {"yes": 0.5, "no": 0.5}}}
    request["tests"] = {"first": test, "second": test}
    # Four base utility cells plus two tests with 2 states * 2 actions * 2 outcomes.
    assert DecisionAnalysisEngine(max_cells=20).analyze(request).metadata["cells"] == 20
    with pytest.raises(DecisionAnalysisValidationError, match="max_cells=19"):
        DecisionAnalysisEngine(max_cells=19).analyze(request)


def test_numeric_overflow_raises_validation_error_instead_of_leaking_infinity() -> None:
    request = {
        "states": {"certain": 1},
        "actions": {"best": {"certain": 1e308}, "worst": {"certain": -1e308}},
    }
    with pytest.raises(DecisionAnalysisValidationError, match="finite numeric range"):
        DecisionAnalysisEngine().analyze(request)


@pytest.mark.parametrize("order", [("first", "dominant"), ("dominant", "first")])
def test_large_common_utility_cannot_hide_a_dominant_action_or_create_information_value(
    order,
) -> None:
    actions = {"first": {"rare": 0, "usual": 1e30}, "dominant": {"rare": 1e30, "usual": 1e30}}
    request = {
        "states": {"rare": 1e-20, "usual": 1},
        "actions": {name: actions[name] for name in order},
        "tests": {"useless": {"likelihoods": {"rare": {"same": 1}, "usual": {"same": 1}}}},
    }
    data = DecisionAnalysisEngine().analyze(request).data
    assert data["optimal_actions"] == ["dominant"]
    assert data["evpi"] == 0
    assert data["tests"]["useless"]["evsi"] == 0
    assert data["tests"]["useless"]["observations"]["same"]["optimal_actions"] == ["dominant"]


@pytest.mark.parametrize("order", [("first", "dominant"), ("dominant", "first")])
def test_centered_ranking_handles_rounding_at_ordinary_state_probabilities(order) -> None:
    actions = {
        "first": {"a": 1e16 - 2, "b": 1e16},
        "dominant": {"a": 1e16, "b": 1e16},
    }
    request = {
        "states": {"a": 0.5, "b": 0.5},
        "actions": {name: actions[name] for name in order},
        "tests": {"useless": {"likelihoods": {"a": {"same": 1}, "b": {"same": 1}}}},
    }
    data = DecisionAnalysisEngine().analyze(request).data
    assert data["expected_utilities"] == {"first": 1e16, "dominant": 1e16}
    assert data["optimal_actions"] == ["dominant"]
    assert data["evpi"] == 0
    assert data["tests"]["useless"]["evsi"] == 0
    assert data["tests"]["useless"]["observations"]["same"]["optimal_actions"] == ["dominant"]


def test_distinct_action_policies_can_tie_without_being_identical() -> None:
    request = {
        "states": {"a": 0.5, "b": 0.5},
        "actions": {"first": {"a": 1, "b": 0}, "second": {"a": 0, "b": 1}},
    }
    data = DecisionAnalysisEngine().analyze(request).data
    assert data["optimal_actions"] == ["first", "second"]
    assert data["evpi"] == 0.5


@pytest.mark.parametrize("order", list(permutations(("left", "right", "improved"))))
def test_centered_ranking_preserves_advantage_even_when_expected_regrets_also_round_equal(order):
    actions = {
        "left": {"left": 1e30, "right": 0, "rare": 0},
        "right": {"left": 0, "right": 1e30, "rare": 0},
        "improved": {"left": 1e30, "right": 0, "rare": 1e30},
    }
    request = {
        "states": {"left": 0.5, "right": 0.5, "rare": 1e-20},
        "actions": {name: actions[name] for name in order},
        "tests": {
            "useless": {"likelihoods": {state: {"same": 1} for state in ("left", "right", "rare")}}
        },
    }
    data = DecisionAnalysisEngine().analyze(request).data
    assert data["optimal_actions"] == ["improved"]
    assert data["tests"]["useless"]["evsi"] == 0
    assert data["tests"]["useless"]["observations"]["same"]["optimal_actions"] == ["improved"]


def test_positive_observation_mass_below_float_range_is_not_called_impossible() -> None:
    request = {
        "states": {"rare": 1e-200, "usual": 1},
        "actions": {"safe": {"rare": 0, "usual": 0}, "risky": {"rare": 1e308, "usual": -1e308}},
        "tests": {
            "signal": {
                "likelihoods": {
                    "rare": {"signal": 1e-200, "none": 1},
                    "usual": {"signal": 0, "none": 1},
                }
            }
        },
    }
    with pytest.raises(DecisionAnalysisValidationError, match="underflow|precision"):
        DecisionAnalysisEngine().analyze(request)


def test_subnormal_observation_mass_cannot_silently_distort_posterior() -> None:
    request = {
        "states": {"a": 0.3, "b": 0.7},
        "actions": {"act": {"a": 0, "b": 0}},
        "tests": {
            "signal": {
                "likelihoods": {
                    "a": {"signal": 1e-323, "none": 1},
                    "b": {"signal": 1e-323, "none": 1},
                }
            }
        },
    }
    with pytest.raises(DecisionAnalysisValidationError, match="underflow|precision"):
        DecisionAnalysisEngine().analyze(request)


@pytest.mark.parametrize("order", list(permutations(("neutral", "base", "better"))))
def test_exact_ranking_handles_cancellation_inside_centered_differences(order) -> None:
    actions = {
        "neutral": {"a": 1, "b": -1},
        "base": {"a": 1e16, "b": -1e16},
        "better": {"a": 1e16 + 2, "b": -1e16},
    }
    request = {
        "states": {"a": 0.5, "b": 0.5},
        "actions": {name: actions[name] for name in order},
        "tests": {
            "useless": {
                "likelihoods": {
                    "a": {"heads": 0.5, "tails": 0.5},
                    "b": {"heads": 0.5, "tails": 0.5},
                }
            }
        },
    }
    data = DecisionAnalysisEngine().analyze(request).data
    assert data["expected_utilities"] == {"neutral": 0, "base": 0, "better": 1}
    assert data["optimal_actions"] == ["better"]
    assert data["tests"]["useless"]["evsi"] == 0
    for observation in data["tests"]["useless"]["observations"].values():
        assert observation["optimal_actions"] == ["better"]
        assert observation["expected_utility"] == 1
