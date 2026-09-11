import json
from typing import Any

from pearl_of_wisdom.engines import AnalysisEngine, AnalysisResult, MonteCarloEngine


def accepts_engine(engine: AnalysisEngine) -> AnalysisEngine:
    return engine


def test_analysis_result_is_json_serializable_and_engine_matches_protocol() -> None:
    engine = accepts_engine(MonteCarloEngine())

    result = AnalysisResult(
        engine="example",
        capabilities=("example.capability",),
        data={"answer": 42, "nested": [True, None, "value"]},
        metadata={"source": "worked-example"},
    )

    encoded = json.loads(json.dumps(result.to_dict()))
    assert engine.name == "monte_carlo"
    assert engine.supports("simulation.monte_carlo")
    assert not engine.supports("inference.causal")
    assert encoded == {
        "engine": "example",
        "capabilities": ["example.capability"],
        "data": {"answer": 42, "nested": [True, None, "value"]},
        "metadata": {"source": "worked-example"},
    }


def test_analysis_result_rejects_non_json_values() -> None:
    non_json_value: dict[str, Any] = {"bad": object()}

    try:
        AnalysisResult(engine="example", capabilities=(), data=non_json_value)
    except (TypeError, ValueError) as error:
        assert "JSON" in str(error)
    else:
        raise AssertionError("non-JSON result was accepted")


def test_analysis_result_requires_a_string_engine_name() -> None:
    try:
        AnalysisResult(engine=1, capabilities=(), data={})  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        assert "engine" in str(error)
    else:
        raise AssertionError("non-string engine name was accepted")
