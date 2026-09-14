import hashlib
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

from test_render import _result

from pearl_of_wisdom_viz import cli as cli_module
from pearl_of_wisdom_viz.cli import _publish, main
from pearl_of_wisdom_viz.model import VisualizationError


def test_dist_reads_stdin_writes_html_and_emits_truthful_descriptor(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    source = _result(outcomes=[1, 2, 3, 4])
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(source)))
    output = tmp_path / "duration.html"

    assert (
        main(
            [
                "dist",
                "--quantity",
                "duration",
                "--unit",
                "ms",
                "--resources",
                "cdn",
                "--out",
                str(output),
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    descriptor = json.loads(captured.out)

    assert captured.err == ""
    assert output.read_bytes().startswith(b"<!doctype html>")
    assert descriptor["artifact_path"] == str(output.resolve())
    assert descriptor["media_type"] == "text/html"
    assert descriptor["resource_mode"] == "cdn"
    assert descriptor["source_sha256"] == [hashlib.sha256(source).hexdigest()]
    assert descriptor["artifact_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert descriptor["summaries"][0]["count"] == 4
    assert "draws" not in descriptor


def test_forest_reads_files_and_requires_matching_unique_labels(tmp_path: Path, capsys) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_bytes(_result(count=4, median=2, low=1, high=3))
    second.write_bytes(_result(count=4, median=3, low=2, high=4))
    output = tmp_path / "compare.html"

    assert (
        main(
            [
                "forest",
                "--input",
                str(first),
                "--input",
                str(second),
                "--label",
                "first",
                "--label",
                "second",
                "--quantity",
                "latency",
                "--unit",
                "ms",
                "--resources",
                "cdn",
                "--out",
                str(output),
            ]
        )
        == 0
    )
    descriptor = json.loads(capsys.readouterr().out)

    assert [item["label"] for item in descriptor["summaries"]] == ["first", "second"]
    assert len(descriptor["source_sha256"]) == 2

    assert (
        main(
            [
                "forest",
                "--input",
                str(first),
                "--input",
                str(second),
                "--label",
                "same",
                "--label",
                "same",
                "--quantity",
                "latency",
                "--unit",
                "ms",
                "--out",
                str(tmp_path / "invalid.html"),
            ]
        )
        == 1
    )
    error = json.loads(capsys.readouterr().err)["error"]
    assert error["code"] == "validation_error"
    assert "unique" in error["message"]


def test_failures_are_json_and_do_not_publish_partial_artifacts(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(b"not json")))
    output = tmp_path / "missing.html"

    assert (
        main(
            [
                "dist",
                "--quantity",
                "duration",
                "--unit",
                "ms",
                "--out",
                str(output),
            ]
        )
        == 1
    )
    captured = capsys.readouterr()

    assert captured.out == ""
    assert json.loads(captured.err)["error"]["code"] == "validation_error"
    assert not output.exists()


def test_existing_output_requires_overwrite_and_failed_attempt_preserves_it(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    source = _result(outcomes=[1, 2, 3, 4])
    output = tmp_path / "duration.html"
    output.write_text("keep me")
    arguments = [
        "dist",
        "--quantity",
        "duration",
        "--unit",
        "ms",
        "--resources",
        "cdn",
        "--out",
        str(output),
    ]
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(source)))

    assert main(arguments) == 1
    assert output.read_text() == "keep me"
    assert "--overwrite" in json.loads(capsys.readouterr().err)["error"]["message"]

    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(source)))
    assert main([*arguments, "--overwrite"]) == 0
    capsys.readouterr()
    assert output.read_bytes().startswith(b"<!doctype html>")


def test_backend_suffix_and_resource_contracts_are_explicit(tmp_path: Path, capsys) -> None:
    source = tmp_path / "result.json"
    source.write_bytes(_result(outcomes=[1, 2, 3, 4]))

    cases = [
        (["--backend", "matplotlib", "--out", str(tmp_path / "wrong.html")], ".png"),
        (["--backend", "bokeh", "--out", str(tmp_path / "wrong.png")], ".html"),
        (
            [
                "--backend",
                "matplotlib",
                "--resources",
                "inline",
                "--out",
                str(tmp_path / "wrong.png"),
            ],
            "resources",
        ),
    ]
    for options, message in cases:
        assert (
            main(
                [
                    "dist",
                    "--input",
                    str(source),
                    "--quantity",
                    "duration",
                    "--unit",
                    "ms",
                    *options,
                ]
            )
            == 1
        )
        assert message in json.loads(capsys.readouterr().err)["error"]["message"]


def test_shared_resource_environment_and_flag_precedence(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    source = tmp_path / "result.json"
    source.write_bytes(_result(outcomes=[1, 2, 3, 4]))
    monkeypatch.setenv("PEARL_VIZ_RESOURCES", "shared")
    monkeypatch.setenv("PEARL_VIZ_ASSETS_DIR", str(tmp_path / "assets"))

    shared = tmp_path / "shared.html"
    assert (
        main(
            [
                "dist",
                "--input",
                str(source),
                "--quantity",
                "duration",
                "--unit",
                "ms",
                "--out",
                str(shared),
            ]
        )
        == 0
    )
    shared_descriptor = json.loads(capsys.readouterr().out)
    assert shared_descriptor["resource_mode"] == "shared"
    assert shared_descriptor["shared_asset"]["location"].startswith(str(tmp_path))

    cdn = tmp_path / "cdn.html"
    assert (
        main(
            [
                "dist",
                "--input",
                str(source),
                "--quantity",
                "duration",
                "--unit",
                "ms",
                "--resources",
                "cdn",
                "--out",
                str(cdn),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["resource_mode"] == "cdn"


def test_concurrent_non_overwriting_publish_has_one_winner(tmp_path: Path) -> None:
    output = tmp_path / "artifact.html"

    def publish(value: bytes) -> str:
        try:
            _publish(output, value, overwrite=False)
        except VisualizationError:
            return "lost"
        return "won"

    values = tuple(f"value-{index}".encode() for index in range(8))
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(publish, values))

    assert outcomes.count("won") == 1
    assert output.read_bytes() in values
    assert not list(tmp_path.glob("*.tmp"))


def test_stdin_limit_is_checked_before_json_parsing(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.setattr(cli_module, "MAX_INPUT_BYTES", 4)
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(b"12345")))

    assert (
        main(
            [
                "dist",
                "--quantity",
                "value",
                "--unit",
                "unitless",
                "--out",
                str(tmp_path / "result.html"),
            ]
        )
        == 1
    )
    assert "input limit" in json.loads(capsys.readouterr().err)["error"]["message"]


def test_forest_rejects_more_than_eight_inputs_before_reading_them(
    tmp_path: Path, capsys
) -> None:
    arguments = ["forest", "--quantity", "value", "--unit", "unitless"]
    for index in range(9):
        arguments.extend(["--input", str(tmp_path / f"missing-{index}.json")])
        arguments.extend(["--label", str(index)])
    arguments.extend(["--out", str(tmp_path / "result.html")])

    assert main(arguments) == 1
    error = json.loads(capsys.readouterr().err)["error"]
    assert "two and eight" in error["message"]
    assert "cannot read" not in error["message"]


def test_closed_stdout_reports_publication_delivery_failure(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source.json"
    source.write_bytes(_result(outcomes=[1, 2, 3, 4]))
    output = tmp_path / "result.html"
    error_stream = io.StringIO()

    class ClosedOutput:
        def write(self, value: str) -> int:
            raise BrokenPipeError

        def flush(self) -> None:
            return None

    monkeypatch.setattr(sys, "stdout", ClosedOutput())
    monkeypatch.setattr(sys, "stderr", error_stream)

    assert (
        main(
            [
                "dist",
                "--input",
                str(source),
                "--quantity",
                "value",
                "--unit",
                "unitless",
                "--resources",
                "cdn",
                "--out",
                str(output),
            ]
        )
        == 1
    )
    assert output.is_file()
    assert json.loads(error_stream.getvalue())["error"]["code"] == "stdout_closed"
