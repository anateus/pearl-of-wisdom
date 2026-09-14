import json

import pytest

from pearl_of_wisdom_viz.model import VisualizationError, parse_result_bytes


def _result(*, include_draws: bool = True) -> dict[str, object]:
    data: dict[str, object] = {
        "count": 4,
        "mean": 2.5,
        "standard_deviation": 1.118033988749895,
        "minimum": 1.0,
        "maximum": 4.0,
        "quantiles": {"0.05": 1.15, "0.5": 2.5, "0.95": 3.85},
    }
    if include_draws:
        data["draws"] = {
            "schema_version": 1,
            "population": 4,
            "returned": 4,
            "selection": "all",
            "indices": [0, 1, 2, 3],
            "outcome": [1.0, 2.0, 3.0, 4.0],
            "inputs": {"x": [1.0, 2.0, 3.0, 4.0]},
            "provenance": {
                "pearl_version": "0.2.0",
                "python_version": "3.12.11",
                "effective_request": {
                    "variables": {"x": {"distribution": "uniform", "low": 1, "high": 4}},
                    "expression": "x",
                    "samples": 4,
                    "seed": 7,
                    "quantiles": [0.05, 0.5, 0.95],
                },
                "input_order": ["x"],
            },
        }
    return {
        "engine": "monte_carlo",
        "capabilities": ["simulation.monte_carlo", "uncertainty.numeric"],
        "data": data,
        "metadata": {"samples": 4, "seed": 7},
    }


def _bytes(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode()


def test_parse_exported_result_preserves_summary_draws_and_source_hash() -> None:
    source = _bytes(_result())

    result = parse_result_bytes(source, require_draws=True)

    assert result.summary.count == 4
    assert result.summary.quantiles == {0.05: 1.15, 0.5: 2.5, 0.95: 3.85}
    assert result.draws.population == 4
    assert result.draws.outcomes == (1.0, 2.0, 3.0, 4.0)
    assert result.draws.inputs == {"x": (1.0, 2.0, 3.0, 4.0)}
    assert len(result.source_sha256) == 64


def test_summary_only_result_is_valid_until_draws_are_required() -> None:
    source = _bytes(_result(include_draws=False))

    assert parse_result_bytes(source).draws is None
    with pytest.raises(VisualizationError, match="requires data.draws"):
        parse_result_bytes(source, require_draws=True)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(engine="decision_analysis"), "engine"),
        (lambda value: value["data"].update(count=True), "data.count"),
        (lambda value: value["data"].update(minimum=5), "summary ordering"),
        (lambda value: value["data"]["draws"].update(schema_version=2), "schema_version"),
        (lambda value: value["data"]["draws"].update(population=5), "population"),
        (lambda value: value["data"]["draws"].update(returned=3), "equal lengths"),
        (lambda value: value["data"]["draws"].update(indices=[0, 1, 1, 3]), "unique"),
        (lambda value: value["data"]["draws"].update(indices=[0, 1, 2, 4]), "in range"),
        (
            lambda value: value["data"]["draws"]["inputs"].update(y=[1, 2, 3, 4]),
            "declared input",
        ),
    ],
)
def test_result_validation_rejects_inconsistent_consumed_fields(mutation, message: str) -> None:
    value = _result()
    mutation(value)

    with pytest.raises(VisualizationError, match=message):
        parse_result_bytes(_bytes(value))


@pytest.mark.parametrize(
    "source",
    [
        b'{"engine":"monte_carlo","engine":"monte_carlo"}',
        b'{"engine":"monte_carlo","data":{"mean":NaN}}',
        b'{"engine":"monte_carlo"',
    ],
)
def test_strict_json_rejects_duplicate_keys_nonfinite_constants_and_truncation(
    source: bytes,
) -> None:
    with pytest.raises(VisualizationError):
        parse_result_bytes(source)


def test_summary_reports_a_missing_required_quantile_by_probability() -> None:
    value = _result()
    value["data"]["quantiles"].pop("0.5")

    summary = parse_result_bytes(_bytes(value)).summary

    with pytest.raises(VisualizationError, match="quantile 0.5"):
        summary.require_quantile(0.5)
