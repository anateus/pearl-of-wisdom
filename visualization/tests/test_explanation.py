import copy
import hashlib
import json
from pathlib import Path

import pytest

from pearl_of_wisdom_viz.cli import main
from pearl_of_wisdom_viz.model import parse_result_bytes


def make_result(*, capped: bool = False) -> dict:
    return {
        "engine": "monte_carlo",
        "data": {
            "count": 4,
            "mean": 2.25,
            "standard_deviation": 1.09,
            "minimum": 1,
            "maximum": 4,
            "quantiles": {"0.05": 1.15, "0.5": 2, "0.95": 3.7},
            "thresholds": {
                "schema_version": 1,
                "events": {
                    "deadline": {"operator": "le", "value": 3, "matched": 3, "total": 4},
                },
            },
            "draws": {
                "schema_version": 1,
                "population": 4,
                "returned": 1 if capped else 4,
                "selection": "uniform_without_replacement_v1" if capped else "all",
                "indices": [3] if capped else [0, 1, 2, 3],
                "outcome": [4] if capped else [1, 2, 2, 4],
                "inputs": {},
                "provenance": {
                    "pearl_version": "0.4.0",
                    "python_version": "3.12.13",
                    "effective_request": {
                        "variables": {"x": {"distribution": "uniform", "low": 1, "high": 4}},
                        "expression": "x",
                        "samples": 4,
                        "seed": 7,
                        "quantiles": [0.05, 0.5, 0.95],
                        "thresholds": {"deadline": {"operator": "le", "value": 3}},
                    },
                    "input_order": ["x"],
                },
            },
        },
        "metadata": {"samples": 4, "seed": 7},
    }


def write_context(tmp_path: Path, result: dict | None = None) -> tuple[Path, dict]:
    source = json.dumps(result or make_result()).encode()
    (tmp_path / "result.json").write_bytes(source)
    context = {
        "schema_version": 1,
        "illustrative": True,
        "question": "Will the project finish within three working days?",
        "outcome": {
            "label": "Completion time",
            "unit": "working days",
            "subject": "simulated projects",
        },
        "target": {"id": "deadline", "operator": "le", "value": 3},
        "model": {
            "explanation": "Completion time comes from the assumed duration.",
            "inputs": {
                "x": {
                    "label": "Duration",
                    "unit": "working days",
                    "description": "Time to finish.",
                    "evidence": {"status": "assumed", "note": "Synthetic teaching values."},
                }
            },
            "limitations": ["This synthetic model has not been calibrated to a real team."],
        },
        "scenarios": [
            {
                "id": "baseline",
                "label": "Current scope",
                "source": "result.json",
                "sha256": hashlib.sha256(source).hexdigest(),
                "changes": [],
            }
        ],
    }
    path = tmp_path / "context.json"
    path.write_text(json.dumps(context))
    return path, context


def test_explain_cli_uses_full_run_counts_when_draw_subset_has_no_matches(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path, _ = write_context(tmp_path, make_result(capped=True))
    output = tmp_path / "report.html"
    assert main(["explain", "--context", str(path), "--out", str(output)]) == 0
    descriptor = json.loads(capsys.readouterr().out)
    assert descriptor["context_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    html = output.read_text()
    assert "75 in 100" in html
    assert "3 of 4" in html
    assert "Under these assumptions" in html
    assert "Synthetic teaching values." in html
    assert "1 of 4" in html


def test_json_key_sorting_preserves_explicit_sampling_order() -> None:
    result = make_result()
    provenance = result["data"]["draws"]["provenance"]
    provenance["effective_request"]["variables"] = {
        "z": {"distribution": "constant", "value": 1},
        "a": {"distribution": "uniform", "low": 0, "high": 3},
    }
    provenance["effective_request"]["expression"] = "z + a"
    provenance["input_order"] = ["z", "a"]
    parsed = parse_result_bytes(json.dumps(result, sort_keys=True).encode(), require_draws=True)
    assert parsed.draws.input_order == ("z", "a")


def test_report_explains_interval_model_and_limits_in_static_html(tmp_path: Path, capsys) -> None:
    path, _ = write_context(tmp_path)
    output = tmp_path / "report.html"
    assert main(["explain", "--context", str(path), "--out", str(output)]) == 0
    descriptor = json.loads(capsys.readouterr().out)
    content = output.read_text()
    assert "middle 90%" in content
    assert "1.15" in content and "3.7" in content
    assert "How this model works" in content
    assert "Completion time comes from the assumed duration." in content
    assert "More simulations" in content
    assert "not been calibrated to a real team" in content
    assert "source SHA-256" in content
    assert descriptor["summaries"][0]["matched"] == 3
    assert descriptor["summaries"][0]["total"] == 4


@pytest.mark.parametrize("mutation", ["stale_hash", "missing_metric", "wrong_target", "bad_count"])
def test_explain_rejects_untraceable_claims(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], mutation: str
) -> None:
    result = make_result()
    if mutation == "missing_metric":
        del result["data"]["thresholds"]
    elif mutation == "bad_count":
        result["data"]["thresholds"]["events"]["deadline"]["matched"] = 2
    path, context = write_context(tmp_path, result)
    if mutation == "stale_hash":
        context["scenarios"][0]["sha256"] = "0" * 64
    elif mutation == "wrong_target":
        context["target"]["value"] = 2
    path.write_text(json.dumps(context))
    output = tmp_path / "report.html"
    assert main(["explain", "--context", str(path), "--out", str(output)]) == 1
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "validation_error"
    assert not output.exists()


def test_scenario_context_must_declare_actual_model_changes(tmp_path: Path, capsys) -> None:
    path, context = write_context(tmp_path)
    other = copy.deepcopy(make_result())
    other["data"]["draws"]["provenance"]["effective_request"]["expression"] = "x + 0"
    raw = json.dumps(other).encode()
    (tmp_path / "other.json").write_bytes(raw)
    context["scenarios"].append(
        {
            "id": "other",
            "label": "Other",
            "source": "other.json",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "changes": [],
        }
    )
    path.write_text(json.dumps(context))
    assert main(["explain", "--context", str(path), "--out", str(tmp_path / "a.html")]) == 1
    assert "changes" in capsys.readouterr().err
