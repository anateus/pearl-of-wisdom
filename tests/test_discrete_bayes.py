import math
from copy import deepcopy

import pytest

from pearl_of_wisdom.engines import DiscreteBayesEngine, DiscreteBayesValidationError


def rain_network() -> dict[str, object]:
    return {
        "variables": {
            "rain": {
                "states": ["yes", "no"],
                "parents": [],
                "cpt": [
                    {"when": {}, "probabilities": {"yes": 0.2, "no": 0.8}},
                ],
            },
            "wet": {
                "states": ["yes", "no"],
                "parents": ["rain"],
                "cpt": [
                    {
                        "when": {"rain": "yes"},
                        "probabilities": {"yes": 0.9, "no": 0.1},
                    },
                    {
                        "when": {"rain": "no"},
                        "probabilities": {"yes": 0.1, "no": 0.9},
                    },
                ],
            },
        }
    }


def test_exact_posterior_matches_bayes_rule_worked_example() -> None:
    # P(rain | wet) = (0.9 * 0.2) / ((0.9 * 0.2) + (0.1 * 0.8)) = 9/13.
    result = DiscreteBayesEngine().analyze(
        {"network": rain_network(), "query": ["rain"], "evidence": {"wet": "yes"}}
    )

    distribution = result.data["distribution"]
    assert result.engine == "discrete_bayes"
    assert distribution[0]["assignment"] == {"rain": "yes"}
    assert distribution[0]["probability"] == pytest.approx(9 / 13)
    assert distribution[1]["assignment"] == {"rain": "no"}
    assert distribution[1]["probability"] == pytest.approx(4 / 13)
    assert math.fsum(row["probability"] for row in distribution) == pytest.approx(1.0)
    assert result.data["evidence_probability"] == pytest.approx(0.26)


def test_joint_query_distribution_is_exact_and_normalized() -> None:
    result = DiscreteBayesEngine().analyze(
        {"network": rain_network(), "query": ["rain", "wet"], "evidence": {}}
    )

    probabilities = {
        tuple(row["assignment"].values()): row["probability"] for row in result.data["distribution"]
    }
    assert probabilities == pytest.approx(
        {("yes", "yes"): 0.18, ("yes", "no"): 0.02, ("no", "yes"): 0.08, ("no", "no"): 0.72}
    )


def test_cycle_is_rejected() -> None:
    network = rain_network()
    variables = network["variables"]
    assert isinstance(variables, dict)
    rain = variables["rain"]
    assert isinstance(rain, dict)
    rain["parents"] = ["wet"]
    rain["cpt"] = [
        {"when": {"wet": "yes"}, "probabilities": {"yes": 0.2, "no": 0.8}},
        {"when": {"wet": "no"}, "probabilities": {"yes": 0.2, "no": 0.8}},
    ]

    with pytest.raises(DiscreteBayesValidationError, match="cycle"):
        DiscreteBayesEngine().analyze({"network": network, "query": ["rain"], "evidence": {}})


@pytest.mark.parametrize(
    "mutation, message",
    [
        ("unnormalized", "sum to 1"),
        ("missing_row", "CPT"),
        ("invalid_state", "state"),
    ],
)
def test_malformed_cpts_and_states_are_rejected(mutation: str, message: str) -> None:
    network = rain_network()
    variables = network["variables"]
    assert isinstance(variables, dict)
    wet = variables["wet"]
    assert isinstance(wet, dict)
    cpt = wet["cpt"]
    assert isinstance(cpt, list)
    if mutation == "unnormalized":
        cpt[0]["probabilities"] = {"yes": 0.7, "no": 0.1}
    elif mutation == "missing_row":
        cpt.pop()
    else:
        cpt[0]["when"] = {"rain": "maybe"}

    with pytest.raises(DiscreteBayesValidationError, match=message):
        DiscreteBayesEngine().analyze({"network": network, "query": ["rain"], "evidence": {}})


def test_invalid_evidence_and_impossible_evidence_are_rejected() -> None:
    engine = DiscreteBayesEngine()
    with pytest.raises(DiscreteBayesValidationError, match="state"):
        engine.analyze({"network": rain_network(), "query": ["rain"], "evidence": {"wet": "maybe"}})

    network = rain_network()
    variables = network["variables"]
    assert isinstance(variables, dict)
    rain = variables["rain"]
    assert isinstance(rain, dict)
    rain["cpt"] = [{"when": {}, "probabilities": {"yes": 1.0, "no": 0.0}}]
    with pytest.raises(DiscreteBayesValidationError, match="impossible evidence"):
        engine.analyze({"network": network, "query": ["wet"], "evidence": {"rain": "no"}})


def test_state_space_limit_is_checked_before_enumeration() -> None:
    with pytest.raises(DiscreteBayesValidationError, match="state space"):
        DiscreteBayesEngine(max_states=3).analyze(
            {"network": rain_network(), "query": ["rain"], "evidence": {}}
        )


@pytest.mark.parametrize("max_states", [True, 3.5, 0])
def test_state_space_limit_must_be_a_positive_integer(max_states: object) -> None:
    with pytest.raises(DiscreteBayesValidationError, match="max_states"):
        DiscreteBayesEngine(max_states=max_states)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("location", "unknown_field"),
    [
        ("request", "observations"),
        ("network", "nodes"),
        ("variable", "state"),
        ("cpt", "condition"),
    ],
)
def test_unknown_fields_are_rejected_at_typed_boundaries(location: str, unknown_field: str) -> None:
    request = {"network": rain_network(), "query": ["rain"], "evidence": {"wet": "yes"}}
    if location == "request":
        request[unknown_field] = {"wet": "yes"}
    elif location == "network":
        request["network"][unknown_field] = {}  # type: ignore[index]
    elif location == "variable":
        request["network"]["variables"]["wet"][unknown_field] = []  # type: ignore[index]
    else:
        request["network"]["variables"]["wet"]["cpt"][0][unknown_field] = {}  # type: ignore[index]

    with pytest.raises(DiscreteBayesValidationError, match=rf"{location}.*{unknown_field}"):
        DiscreteBayesEngine().analyze(request)


def test_dynamic_node_condition_and_state_maps_remain_valid() -> None:
    network = deepcopy(rain_network())
    variables = network["variables"]
    assert isinstance(variables, dict)
    variables["rain reading"] = variables.pop("rain")
    variables["wet reading"] = variables.pop("wet")
    wet = variables["wet reading"]
    assert isinstance(wet, dict)
    wet["parents"] = ["rain reading"]
    for row in wet["cpt"]:  # type: ignore[union-attr]
        row["when"] = {"rain reading": row["when"].pop("rain")}

    result = DiscreteBayesEngine().analyze(
        {
            "network": network,
            "query": ["rain reading"],
            "evidence": {"wet reading": "yes"},
        }
    )

    assert result.data["evidence_probability"] == pytest.approx(0.26)
