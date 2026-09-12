import json
from copy import deepcopy

import pytest

from pearl_of_wisdom.engines.causal import CausalEngine, CausalValidationError
from pearl_of_wisdom.engines.discrete_bayes import DiscreteBayesEngine
from pearl_of_wisdom.engines.protocol import AnalysisEngine


def confounded_network() -> dict[str, object]:
    # Baseline affects treatment assignment and outcome. Treatment has no effect.
    return {
        "variables": {
            "baseline": {
                "states": ["high", "low"],
                "parents": [],
                "cpt": [{"when": {}, "probabilities": {"high": 0.5, "low": 0.5}}],
            },
            "treatment": {
                "states": ["yes", "no"],
                "parents": ["baseline"],
                "cpt": [
                    {
                        "when": {"baseline": "high"},
                        "probabilities": {"yes": 0.9, "no": 0.1},
                    },
                    {
                        "when": {"baseline": "low"},
                        "probabilities": {"yes": 0.1, "no": 0.9},
                    },
                ],
            },
            "outcome": {
                "states": ["good", "bad"],
                "parents": ["baseline", "treatment"],
                "cpt": [
                    {
                        "when": {"baseline": baseline, "treatment": treatment},
                        "probabilities": {"good": good, "bad": 1 - good},
                    }
                    for baseline, good in [("high", 0.8), ("low", 0.2)]
                    for treatment in ["yes", "no"]
                ],
            },
        }
    }


def causal_request() -> dict[str, object]:
    return {
        "network": confounded_network(),
        "query": ["outcome"],
        "interventions": {"treatment": "yes"},
        "assumptions": [
            "Baseline includes the relevant common causes of treatment and outcome.",
            "Outcome mechanisms remain unchanged under intervention on treatment.",
        ],
    }


def test_intervention_removes_confounding_instead_of_conditioning_on_treatment() -> None:
    # Observation selects 90% high-baseline cases: 0.9 * 0.8 + 0.1 * 0.2 = 0.74.
    # Setting treatment preserves the baseline mix: 0.5 * 0.8 + 0.5 * 0.2 = 0.5.
    observed = DiscreteBayesEngine().analyze(
        {
            "network": confounded_network(),
            "query": ["outcome"],
            "evidence": {"treatment": "yes"},
        }
    )
    result = CausalEngine().analyze(causal_request())

    assert observed.data["distribution"][0]["probability"] == pytest.approx(0.74)
    assert result.data.get("distribution") == [
        {"assignment": {"outcome": "good"}, "probability": pytest.approx(0.5)},
        {"assignment": {"outcome": "bad"}, "probability": pytest.approx(0.5)},
    ]


def test_multiple_interventions_and_intervened_query_variables() -> None:
    request = causal_request()
    request["interventions"] = {"baseline": "low", "treatment": "yes"}
    request["query"] = ["baseline", "treatment", "outcome"]
    result = CausalEngine().analyze(request)

    # Setting baseline low leaves a 20% good-outcome probability, regardless of treatment.
    rows = result.data["distribution"]
    probabilities = {tuple(row["assignment"].values()): row["probability"] for row in rows}
    assert len(probabilities) == 8
    assert probabilities[("low", "yes", "good")] == pytest.approx(0.2)
    assert probabilities[("low", "yes", "bad")] == pytest.approx(0.8)
    assert all(value == 0 for key, value in probabilities.items() if key[:2] != ("low", "yes"))
    assert result.data["evidence_probability"] == pytest.approx(1)


def test_do_can_set_a_state_that_has_zero_observational_probability() -> None:
    request = causal_request()
    for row in request["network"]["variables"]["treatment"]["cpt"]:
        row["probabilities"] = {"yes": 0.0, "no": 1.0}

    result = CausalEngine().analyze(request)
    assert result.data["distribution"][0]["probability"] == pytest.approx(0.5)
    assert result.data["evidence_probability"] == pytest.approx(1)
    request["query"] = ["treatment"]
    result = CausalEngine().analyze(request)
    assert result.data["distribution"] == [
        {"assignment": {"treatment": "yes"}, "probability": 1.0},
        {"assignment": {"treatment": "no"}, "probability": 0.0},
    ]


def test_evidence_is_conditioned_on_in_the_intervened_model() -> None:
    request = causal_request()
    request["query"] = ["baseline"]
    request["evidence"] = {"outcome": "good", "treatment": "yes"}
    result = CausalEngine().analyze(request)

    # Under do(treatment=yes), P(high, good)=0.4 and P(low, good)=0.1.
    assert result.data["distribution"][0]["probability"] == pytest.approx(0.8)
    assert result.data["distribution"][1]["probability"] == pytest.approx(0.2)
    assert result.data["evidence_probability"] == pytest.approx(0.5)
    assert result.metadata["evidence_probability_semantics"] == "P(evidence | do(interventions))"


@pytest.mark.parametrize("contradiction", ["intervention", "zero_likelihood"])
def test_impossible_evidence_is_rejected(contradiction: str) -> None:
    request = causal_request()
    if contradiction == "intervention":
        request["evidence"] = {"treatment": "no"}
    else:
        for row in request["network"]["variables"]["outcome"]["cpt"]:
            row["probabilities"] = {"good": 1.0, "bad": 0.0}
        request["evidence"] = {"outcome": "bad"}
    with pytest.raises(CausalValidationError, match="impossible evidence"):
        CausalEngine().analyze(request)


def test_intervention_does_not_hide_an_original_cycle() -> None:
    request = causal_request()
    treatment = request["network"]["variables"]["treatment"]
    treatment["parents"] = ["outcome"]
    treatment["cpt"] = [
        {"when": {"outcome": state}, "probabilities": {"yes": 0.5, "no": 0.5}}
        for state in ["good", "bad"]
    ]
    with pytest.raises(CausalValidationError, match="cycle"):
        CausalEngine().analyze(request)


def test_intervention_does_not_hide_a_malformed_original_cpt() -> None:
    request = causal_request()
    request["network"]["variables"]["treatment"]["cpt"].pop()
    with pytest.raises(CausalValidationError, match="CPT"):
        CausalEngine().analyze(request)


def test_original_state_space_is_checked_before_intervening() -> None:
    request = causal_request()
    request["interventions"] = {"baseline": "low", "treatment": "yes", "outcome": "good"}
    with pytest.raises(CausalValidationError, match="state space"):
        CausalEngine(max_states=4).analyze(request)


def test_variable_limit_bounds_even_single_state_networks() -> None:
    request = causal_request()
    request["network"] = {
        "variables": {
            f"node_{index}": {
                "states": ["only"],
                "cpt": [{"when": {}, "probabilities": {"only": 1.0}}],
            }
            for index in range(129)
        }
    }
    request["query"] = ["node_0"]
    request["interventions"] = {"node_1": "only"}
    with pytest.raises(CausalValidationError, match="at most 128 variables"):
        CausalEngine().analyze(request)


@pytest.mark.parametrize("max_states", [True, 3.5, 0, -1])
def test_max_states_requires_a_positive_integer(max_states: object) -> None:
    with pytest.raises(CausalValidationError, match="max_states"):
        CausalEngine(max_states=max_states)


@pytest.mark.parametrize(
    "assumptions",
    [None, [], "assumed causal", [""], ["  "], [True], [42], ["a"] * 101, ["a" * 4097]],
)
def test_explicit_bounded_causal_assumptions_are_required(assumptions: object) -> None:
    request = causal_request()
    request["assumptions"] = assumptions
    with pytest.raises(CausalValidationError, match="assumption"):
        CausalEngine().analyze(request)


@pytest.mark.parametrize(
    ("location", "unknown_field"),
    [
        ("request", "counterfactual"),
        ("network", "edges"),
        ("variable", "distribution"),
        ("cpt", "condition"),
    ],
)
def test_unknown_fields_are_rejected(location: str, unknown_field: str) -> None:
    request = causal_request()
    if location == "request":
        request[unknown_field] = {}
    elif location == "network":
        request["network"][unknown_field] = {}
    elif location == "variable":
        request["network"]["variables"]["treatment"][unknown_field] = []
    else:
        request["network"]["variables"]["treatment"]["cpt"][0][unknown_field] = {}
    with pytest.raises(CausalValidationError, match=unknown_field):
        CausalEngine().analyze(request)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("interventions", None),
        ("interventions", []),
        ("interventions", {}),
        ("interventions", {"missing": "yes"}),
        ("interventions", {"treatment": "maybe"}),
        ("interventions", {"treatment": True}),
        ("interventions", {"treatment": 1}),
        ("interventions", {"treatment": []}),
        ("evidence", None),
        ("evidence", {"missing": "yes"}),
        ("evidence", {"treatment": False}),
        ("query", []),
        ("query", "outcome"),
        ("query", ["missing"]),
        ("query", ["outcome", "outcome"]),
        ("query", [True]),
    ],
)
def test_invalid_query_evidence_or_intervention_is_rejected(field: str, value: object) -> None:
    request = causal_request()
    request[field] = value
    with pytest.raises(CausalValidationError, match=field):
        CausalEngine().analyze(request)


@pytest.mark.parametrize("state", [True, 0, "", []])
def test_invalid_network_states_are_rejected(state: object) -> None:
    request = causal_request()
    request["network"]["variables"]["treatment"]["states"] = [state, "no"]
    with pytest.raises(CausalValidationError, match="states"):
        CausalEngine().analyze(request)


@pytest.mark.parametrize("probability", [True, "0.9", float("nan"), float("inf"), -1, 2, 10**1000])
def test_invalid_original_probabilities_are_rejected_even_under_do(probability: object) -> None:
    request = causal_request()
    request["network"]["variables"]["treatment"]["cpt"][0]["probabilities"]["yes"] = probability
    with pytest.raises(CausalValidationError, match="numeric|between 0 and 1"):
        CausalEngine().analyze(request)


@pytest.mark.parametrize("engine_type", [CausalEngine, DiscreteBayesEngine])
def test_positive_joint_probability_underflow_is_not_called_impossible(engine_type: type) -> None:
    request = {
        "network": {
            "variables": {
                name: {
                    "states": ["yes", "no"],
                    "cpt": [{"probabilities": {"yes": 1e-200, "no": 1.0}}],
                }
                for name in ["a", "b", "c"]
            }
        },
        "query": ["a"],
        "evidence": {"a": "yes", "b": "yes"},
    }
    if engine_type is CausalEngine:
        request.update(
            interventions={"c": "yes"}, assumptions=["Independent causal root mechanisms."]
        )
    # P(a=yes, b=yes)=1e-400 is positive, below the float range, not impossible.
    with pytest.raises(ValueError, match="underflow"):
        engine_type().analyze(request)


@pytest.mark.parametrize("engine_type", [CausalEngine, DiscreteBayesEngine])
def test_subnormal_joint_probabilities_cannot_distort_a_conditional_query(
    engine_type: type,
) -> None:
    request = {
        "network": {
            "variables": {
                "rare": {
                    "states": ["yes", "no"],
                    "cpt": [{"probabilities": {"yes": 1e-323, "no": 1.0}}],
                },
                "choice": {
                    "states": ["left", "right"],
                    "cpt": [{"probabilities": {"left": 0.3, "right": 0.7}}],
                },
                "policy": {
                    "states": ["on", "off"],
                    "cpt": [{"probabilities": {"on": 1.0, "off": 0.0}}],
                },
            }
        },
        "query": ["choice"],
        "evidence": {"rare": "yes"},
    }
    if engine_type is CausalEngine:
        request.update(
            interventions={"policy": "on"}, assumptions=["Independent causal root mechanisms."]
        )
    # Independence requires 0.3/0.7. Rounded subnormal products instead yield 0.5/0.5.
    with pytest.raises(ValueError, match="underflow"):
        engine_type().analyze(request)


@pytest.mark.parametrize("request_value", [None, [], True, "request"])
def test_request_must_be_an_object(request_value: object) -> None:
    with pytest.raises(CausalValidationError, match="request must be an object"):
        CausalEngine().analyze(request_value)


def test_public_contract_example_and_result_metadata() -> None:
    engine = CausalEngine()
    assert isinstance(engine, AnalysisEngine)
    assert engine.supports("inference.causal")
    assert engine.supports("inference.intervention")
    assert not engine.supports("inference.counterfactual")

    request = engine.example_request()
    original = deepcopy(request)
    result = engine.analyze(request)
    assert request == original
    assert result.engine == "causal"
    assert result.data["distribution"][0] == {
        "assignment": {"alarm": "positive"},
        "probability": pytest.approx(0.8),
    }
    assert result.metadata["method"] == "truncated_factorization"
    assert result.metadata["assumptions"] == request["assumptions"]
    assert result.metadata["interventions"] == {"fault": "present"}
    assert result.metadata["evidence"] == {}
    assert "supplied causal model" in result.metadata["interpretation"]
    assert "not identified from arbitrary datasets" in result.metadata["interpretation"]
    json.dumps(result.to_dict(), allow_nan=False)

    request["assumptions"].clear()
    request["interventions"]["fault"] = "absent"
    request["network"]["variables"].clear()
    assert engine.example_request() == original
    assert result.metadata["assumptions"] == original["assumptions"]
    assert result.metadata["interventions"] == {"fault": "present"}
