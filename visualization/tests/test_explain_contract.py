import copy
import hashlib
import json
from pathlib import Path

import pytest
from test_explanation import make_result, write_context

from pearl_of_wisdom_viz.cli import main
from pearl_of_wisdom_viz.explain_render import _plots, render_explanation
from pearl_of_wisdom_viz.explanation import frequency, load_explanation
from pearl_of_wisdom_viz.model import Threshold, VisualizationError, parse_result_bytes


def add_scenario(tmp_path: Path, context: dict) -> None:
    result = make_result()
    data = result["data"]
    data.update(count=5, mean=2, minimum=1, maximum=4)
    data["thresholds"]["events"]["deadline"]["matched"] = 4
    data["thresholds"]["events"]["deadline"]["total"] = 5
    draws = data["draws"]
    draws.update(population=5, returned=5, indices=list(range(5)), outcome=[1, 1, 2, 2, 4])
    draws["provenance"]["effective_request"].update(samples=5, expression="x + 0")
    result["metadata"]["samples"] = 5
    source = json.dumps(result).encode()
    (tmp_path / "second.json").write_bytes(source)
    context["scenarios"].append(
        {
            "id": "second",
            "label": "Another saved scenario",
            "source": "second.json",
            "sha256": hashlib.sha256(source).hexdigest(),
            "changes": [{"path": "expression", "description": "Add zero to the duration."}],
        }
    )


@pytest.mark.parametrize(
    ("matched", "total", "expected"),
    [
        (0, 100, "None"),
        (100, 100, "All"),
        (1, 10000, "Fewer than 1"),
        (9999, 10000, "More than 99"),
        (4568, 10000, "About 46"),
    ],
)
def test_frequency_preserves_rare_events(matched, total, expected):
    assert frequency(Threshold("le", 30, matched, total)).startswith(expected)


def test_scenarios_use_own_denominators_and_share_interval_scale(tmp_path):
    path, context = write_context(tmp_path)
    add_scenario(tmp_path, context)
    path.write_text(json.dumps(context))
    report = load_explanation(path)
    rendered = render_explanation(report)
    content = rendered.content.decode()
    assert "about 75 in 100" in content
    assert "about 80 in 100" in content
    assert "5.0 percentage points higher" in content
    assert "before the scenario's formula is applied" in content
    assert "samples one value for each uncertain input" in content
    assert "keeps fixed inputs at their specified values" in content
    assert rendered.summaries[1]["total"] == 5
    plot = _plots(report)["interval"]
    source = plot.select_one({"name": "pearl-interval-data"})
    assert source.data["low"] == [1.15, 1.15]
    assert source.data["high"] == [3.7, 3.7]
    assert plot.x_range.start < 1.15 < 3 < 3.7 < plot.x_range.end


@pytest.mark.parametrize("mutation", ["id", "label", "changes", "units", "evidence", "input"])
def test_invalid_context_contract(tmp_path, mutation):
    path, context = write_context(tmp_path)
    add_scenario(tmp_path, context)
    if mutation in {"id", "label"}:
        context["scenarios"][1][mutation] = context["scenarios"][0][mutation]
    elif mutation == "changes":
        context["scenarios"][1]["changes"][0]["path"] = "variables.x.low"
    elif mutation == "units":
        context["scenarios"][1]["unit"] = "hours"
    elif mutation == "evidence":
        context["model"]["inputs"]["x"]["evidence"]["status"] = "observed"
    else:
        context["model"]["inputs"]["y"] = context["model"]["inputs"]["x"]
    path.write_text(json.dumps(context))
    with pytest.raises(VisualizationError):
        load_explanation(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("matched", True),
        ("matched", -1),
        ("matched", 5),
        ("total", 3),
        ("value", True),
        ("value", 10**400),
        ("operator", "eq"),
    ],
)
def test_rejects_bad_threshold_metrics(field, value):
    result = make_result()
    result["data"]["thresholds"]["events"]["deadline"][field] = value
    with pytest.raises(VisualizationError):
        parse_result_bytes(json.dumps(result).encode())


def test_rejects_boolean_in_threshold_provenance():
    result = make_result()
    event = result["data"]["thresholds"]["events"]["deadline"]
    event.update(value=1, matched=1)
    definition = result["data"]["draws"]["provenance"]["effective_request"]["thresholds"]
    definition["deadline"]["value"] = True
    with pytest.raises(VisualizationError):
        parse_result_bytes(json.dumps(result).encode())


@pytest.mark.parametrize(
    ("operator", "value", "matched"), [("ge", 2, 3), ("gt", 9, 0), ("le", 9, 4)]
)
def test_comparators_and_outside_targets(tmp_path, operator, value, matched):
    result = make_result()
    result["data"]["thresholds"]["events"]["deadline"].update(
        operator=operator, value=value, matched=matched
    )
    result["data"]["draws"]["provenance"]["effective_request"]["thresholds"]["deadline"].update(
        operator=operator, value=value
    )
    path, context = write_context(tmp_path, result)
    context["target"].update(operator=operator, value=value)
    path.write_text(json.dumps(context))
    report = load_explanation(path)
    content = render_explanation(report).content.decode()
    assert "guaranteed" not in content
    assert "impossible" not in content
    assert ("at or above 2" if operator == "ge" else "in this run") in content
    plot = _plots(report)["interval"]
    assert plot.x_range.start < value < plot.x_range.end


def test_negative_constant_interval_and_exact_boundary(tmp_path):
    result = make_result()
    data = result["data"]
    data.update(mean=-2, minimum=-2, maximum=-2, standard_deviation=0)
    data["quantiles"] = {"0.05": -2, "0.5": -2, "0.95": -2}
    data["draws"]["outcome"] = [-2] * 4
    value = -2.00001234
    data["thresholds"]["events"]["deadline"].update(value=value, matched=0)
    data["draws"]["provenance"]["effective_request"]["thresholds"]["deadline"]["value"] = value
    path, context = write_context(tmp_path, result)
    context["target"]["value"] = value
    path.write_text(json.dumps(context))
    rendered = render_explanation(load_explanation(path))
    assert b"at or below -2.00001234" in rendered.content
    assert b"Tied values" in rendered.content
    assert rendered.summaries[0]["p05"] == rendered.summaries[0]["p95"] == -2


def test_context_text_is_not_executable_and_output_is_not_overwritten(tmp_path, capsys):
    path, context = write_context(tmp_path)
    payload = "</script><script>window.contextExecuted = true</script>"
    context["question"] = payload
    context["outcome"]["unit"] = payload
    context["model"]["inputs"]["x"]["evidence"]["reference"] = payload
    path.write_text(json.dumps(context))
    output = tmp_path / "report.html"
    args = ["explain", "--context", str(path), "--out", str(output)]
    assert main(args) == 0
    descriptor = json.loads(capsys.readouterr().out)
    original = output.read_bytes()
    assert payload.encode() not in original
    assert b"&lt;/script&gt;" in original
    assert descriptor["artifact_sha256"] == hashlib.sha256(original).hexdigest()
    assert main(args) != 0
    assert output.read_bytes() == original


def test_bounded_context_and_duplicate_keys(tmp_path):
    path, _ = write_context(tmp_path)
    for source in (b" " * (256 * 1024 + 1), b'{"schema_version":1,"schema_version":1}'):
        path.write_bytes(source)
        with pytest.raises(VisualizationError):
            load_explanation(path)


def test_missing_scenario_metric_never_falls_back_to_draws(tmp_path):
    result = copy.deepcopy(make_result())
    del result["data"]["thresholds"]
    path, _ = write_context(tmp_path, result)
    with pytest.raises(VisualizationError, match="threshold"):
        load_explanation(path)
