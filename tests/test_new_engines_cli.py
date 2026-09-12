"""Public CLI coverage for the three additional reasoning engines."""

import json
from pathlib import Path

import pytest

from pearl_of_wisdom.cli import main

NEW_ENGINES = ("decision-analysis", "causal", "system-simulation")


@pytest.mark.parametrize("engine", NEW_ENGINES)
def test_new_engine_example_runs_without_database(engine: str, tmp_path: Path, capsys) -> None:
    database = tmp_path / "missing-directory" / "pearl.sqlite3"
    prefix = ["--db", str(database), "analyze", "--engine", engine]

    assert main([*prefix, "--example"]) == 0
    example = json.loads(capsys.readouterr().out)
    assert example["result"]["engine"] == engine.replace("-", "_")
    assert example["result"]["capabilities"]
    assert main([*prefix, "--data", json.dumps(example["request"])]) == 0
    rerun = capsys.readouterr()
    assert rerun.err == ""
    assert json.loads(rerun.out) == example["result"]
    assert not database.exists()


@pytest.mark.parametrize("engine", NEW_ENGINES)
def test_new_engine_results_can_be_recorded_and_read(engine: str, tmp_path: Path, capsys) -> None:
    database = tmp_path / "pearl.sqlite3"
    prefix = ["--db", str(database)]
    assert main([*prefix, "create"]) == 0
    investigation_id = json.loads(capsys.readouterr().out)["id"]
    assert main(["analyze", "--engine", engine, "--example"]) == 0
    example = json.loads(capsys.readouterr().out)

    assert (
        main(
            [
                *prefix,
                "record-analysis",
                investigation_id,
                "--engine",
                engine,
                "--data",
                json.dumps(example),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert main([*prefix, "show", investigation_id]) == 0
    analyses = json.loads(capsys.readouterr().out)["analyses"]
    assert len(analyses) == 1
    assert analyses[0]["engine"] == engine
    assert analyses[0]["payload"] == example


@pytest.mark.parametrize("engine", NEW_ENGINES)
def test_new_engine_misspelled_field_is_a_json_validation_error(engine: str, capsys) -> None:
    assert main(["analyze", "--engine", engine, "--example"]) == 0
    request = json.loads(capsys.readouterr().out)["request"]
    request["unknown_setting"] = 1
    assert main(["analyze", "--engine", engine, "--data", json.dumps(request)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    error = json.loads(captured.err)["error"]
    assert error["code"] == "validation_error"
    assert "unknown_setting" in error["message"]


def test_decision_cli_evaluates_a_noisy_test(capsys) -> None:
    request = {
        "states": {"good": 0.4, "bad": 0.6},
        "actions": {"launch": {"good": 100, "bad": -40}, "wait": {"good": 0, "bad": 0}},
        "tests": {
            "pilot": {
                "cost": 2,
                "likelihoods": {
                    "good": {"positive": 0.8, "negative": 0.2},
                    "bad": {"positive": 0.2, "negative": 0.8},
                },
            }
        },
    }
    assert main(["analyze", "--engine", "decision-analysis", "--data", json.dumps(request)]) == 0
    data = json.loads(capsys.readouterr().out)["data"]
    assert data["optimal_actions"] == ["launch"]
    assert data["expected_utility"] == pytest.approx(16)
    assert data["evpi"] == pytest.approx(24)
    assert data["tests"]["pilot"]["evsi"] == pytest.approx(11.2)
    assert data["tests"]["pilot"]["net_evsi"] == pytest.approx(9.2)
