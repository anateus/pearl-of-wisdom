import json
from pathlib import Path

import pytest

from pearl_of_wisdom.cli import main


def test_cli_version_does_not_open_database(tmp_path: Path, capsys) -> None:
    database = tmp_path / "missing" / "pearl.sqlite3"
    assert main(["--db", str(database), "--version"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "pearl-of-wisdom 0.1.1\n"
    assert captured.err == ""
    assert not database.exists()


def test_cli_create_record_show_and_list_json(tmp_path: Path, capsys) -> None:
    database = tmp_path / "pearl.sqlite3"

    assert main(["--db", str(database), "create"]) == 0
    created = json.loads(capsys.readouterr().out)
    investigation_id = created["id"]

    assert (
        main(
            [
                "--db",
                str(database),
                "record-analysis",
                investigation_id,
                "--engine",
                "monte-carlo",
                "--data",
                '{"probability":0.8}',
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert main(["--db", str(database), "show", investigation_id]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["analyses"] == [
        {
            "created_at": shown["analyses"][0]["created_at"],
            "engine": "monte-carlo",
            "id": shown["analyses"][0]["id"],
            "payload": {"probability": 0.8},
        }
    ]

    assert main(["--db", str(database), "list"]) == 0
    assert [item["id"] for item in json.loads(capsys.readouterr().out)] == [investigation_id]


def test_cli_reports_structured_json_errors(tmp_path: Path, capsys) -> None:
    result = main(["--db", str(tmp_path / "pearl.sqlite3"), "show", "inv_missing"])
    captured = capsys.readouterr()

    assert result == 1
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "investigation_not_found"


def test_cli_reports_invalid_arguments_as_json(tmp_path: Path, capsys) -> None:
    result = main(
        ["--db", str(tmp_path / "pearl.sqlite3"), "record-evidence", "inv_1", "--data", "nope"]
    )
    captured = capsys.readouterr()

    assert result == 1
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "invalid_arguments"


def test_cli_reports_storage_failures_as_json(tmp_path: Path, capsys) -> None:
    database = tmp_path / "missing" / "pearl.sqlite3"

    result = main(["--db", str(database), "list"])
    captured = capsys.readouterr()

    assert result == 1
    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "storage_error"


def test_cli_reads_database_path_from_environment(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("PEARL_DB", str(tmp_path / "from-env.sqlite3"))

    assert main(["create", "--status", "durable"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "durable"


def test_cli_analyze_runs_registered_engine_without_creating_a_database(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    assert (
        main(
            [
                "analyze",
                "--engine",
                "monte-carlo",
                "--data",
                json.dumps(
                    {
                        "variables": {"x": {"distribution": "constant", "value": 7}},
                        "expression": "x * 2",
                        "samples": 3,
                        "seed": 11,
                        "quantiles": [0.5],
                    }
                ),
            ]
        )
        == 0
    )

    assert json.loads(capsys.readouterr().out) == {
        "capabilities": ["simulation.monte_carlo", "uncertainty.numeric"],
        "data": {
            "count": 3,
            "maximum": 14.0,
            "mean": 14.0,
            "minimum": 14.0,
            "quantiles": {"0.5": 14.0},
            "standard_deviation": 0.0,
        },
        "engine": "monte_carlo",
        "metadata": {"samples": 3, "seed": 11},
    }
    assert not (tmp_path / "pearl.sqlite3").exists()


def test_cli_analyze_rejects_unknown_bayes_request_field(capsys) -> None:
    request = {
        "network": {
            "variables": {
                "fault": {
                    "states": ["present", "absent"],
                    "parents": [],
                    "cpt": [
                        {
                            "when": {},
                            "probabilities": {"present": 0.2, "absent": 0.8},
                        }
                    ],
                }
            }
        },
        "query": ["fault"],
        "observations": {"fault": "present"},
    }

    result = main(["analyze", "--engine", "discrete-bayes", "--data", json.dumps(request)])
    captured = capsys.readouterr()

    assert result == 1
    assert captured.out == ""
    error = json.loads(captured.err)["error"]
    assert error["code"] == "validation_error"
    assert "request" in error["message"]
    assert "observations" in error["message"]


@pytest.mark.parametrize("engine", ["discrete-bayes", "monte-carlo"])
def test_cli_analyze_examples_are_machine_readable_and_runnable(engine: str, capsys) -> None:
    assert main(["analyze", "--engine", engine, "--example"]) == 0
    example = json.loads(capsys.readouterr().out)

    assert set(example) == {"request", "result"}
    assert main(["analyze", "--engine", engine, "--data", json.dumps(example["request"])]) == 0
    rerun = json.loads(capsys.readouterr().out)
    assert rerun == example["result"]


def test_cli_help_points_to_runnable_engine_examples(capsys) -> None:
    assert main(["analyze", "--help"]) == 0
    help_text = capsys.readouterr().out

    assert "--example" in help_text
    assert "runnable request" in help_text
