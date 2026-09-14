import json
from pathlib import Path

import pytest

from pearl_of_wisdom_viz.model import parse_result_bytes
from pearl_of_wisdom_viz.render import _ecdf, render_distribution, render_forest


def _result(
    *,
    count: int = 4,
    minimum: float = 1,
    median: float = 2.5,
    maximum: float = 4,
    low: float = 1.15,
    high: float = 3.85,
    outcomes: list[float] | None = None,
) -> bytes:
    data: dict[str, object] = {
        "count": count,
        "mean": median,
        "standard_deviation": 1.0,
        "minimum": minimum,
        "maximum": maximum,
        "quantiles": {"0.05": low, "0.5": median, "0.95": high},
    }
    if outcomes is not None:
        returned = len(outcomes)
        data["draws"] = {
            "schema_version": 1,
            "population": count,
            "returned": returned,
            "selection": "all" if returned == count else "uniform_without_replacement_v1",
            "indices": list(range(returned)),
            "outcome": outcomes,
            "inputs": {},
            "provenance": {
                "pearl_version": "0.2.0",
                "python_version": "3.12.11",
                "effective_request": {
                    "variables": {"x": {"distribution": "constant", "value": 1}},
                    "expression": "x",
                    "samples": count,
                    "seed": 7,
                    "quantiles": [0.05, 0.5, 0.95],
                },
                "input_order": ["x"],
            },
        }
    return json.dumps(
        {
            "engine": "monte_carlo",
            "capabilities": [],
            "data": data,
            "metadata": {"samples": count, "seed": 7},
        },
        separators=(",", ":"),
    ).encode()


def test_distribution_html_uses_exact_empirical_values_and_static_full_summary() -> None:
    result = parse_result_bytes(
        _result(count=5, minimum=-10, median=2, maximum=99, outcomes=[1, 1, 2, 2, 2]),
        require_draws=True,
    )

    artifact = render_distribution(
        result,
        quantity="latency </script><script>alert(1)</script>",
        unit="ms",
        resources="cdn",
        caveats=("Synthetic <check>",),
    )
    html = artifact.content.decode()

    assert artifact.media_type == "text/html"
    assert artifact.backend == "bokeh"
    assert artifact.resource_mode == "cdn"
    assert "Cumulative proportion" in html
    assert "99" in html
    assert "Retained 5 of 5 draws" in html
    assert "Synthetic &lt;check&gt;" in html
    assert "</script><script>alert(1)</script>" not in html
    assert result.source_sha256 in html
    assert '"sizing_mode":"stretch_width"' in html
    assert (
        '"tooltips":[["Outcome","@outcome{custom}"],'
        '["Cumulative","@cumulative{custom}"]]'
        in html
    )
    assert "return String(value)" in html
    assert _ecdf(result.draws.outcomes) == ([1.0, 2.0], [0.4, 1.0])


def test_capped_distribution_identifies_subset_and_preserves_full_run_extreme() -> None:
    result = parse_result_bytes(
        _result(count=100, minimum=-5, median=3, maximum=500, outcomes=[1, 2, 3])
    )

    html = render_distribution(
        result,
        quantity="duration",
        unit="ms",
        resources="cdn",
    ).content.decode()

    assert "Retained 3 of 100 draws" in html
    assert "may omit rare outcomes" in html
    assert "500" in html


def test_forest_uses_full_run_quantiles_without_draws_or_reordering() -> None:
    slow = parse_result_bytes(
        _result(count=10, minimum=0, median=80, maximum=150, low=40, high=120)
    )
    fast = parse_result_bytes(
        _result(count=40, minimum=0, median=20, maximum=50, low=10, high=30)
    )

    artifact = render_forest(
        (slow, fast),
        ("slow", "fast"),
        quantity="duration",
        unit="ms",
        resources="cdn",
    )

    assert artifact.summaries == (
        {"label": "slow", "count": 10, "seed": 7, "p05": 40.0, "p50": 80.0, "p95": 120.0},
        {"label": "fast", "count": 40, "seed": 7, "p05": 10.0, "p50": 20.0, "p95": 30.0},
    )
    html = artifact.content.decode()
    assert html.index(">slow<") < html.index(">fast<")
    assert "5th to 95th percentile range" in html
    assert "click_policy" in html
    assert "@p05{custom}" in html
    assert "@p50{custom}" in html
    assert "@p95{custom}" in html
    assert "return String(value)" in html


def test_matplotlib_distribution_and_forest_write_real_png_bytes() -> None:
    drawn = parse_result_bytes(_result(outcomes=[1, 2, 3, 4]), require_draws=True)
    summary = parse_result_bytes(_result())

    distribution = render_distribution(
        drawn,
        quantity="duration",
        unit="ms",
        backend="matplotlib",
    )
    forest = render_forest(
        (summary, summary),
        ("a", "b"),
        quantity="duration",
        unit="ms",
        backend="matplotlib",
    )

    assert distribution.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert forest.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert distribution.resource_mode is None
    assert forest.resource_mode is None


def test_shared_html_references_immutable_local_asset_and_keeps_failure_message(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("PEARL_VIZ_ASSETS_DIR", str(tmp_path / "assets with spaces"))
    result = parse_result_bytes(_result(outcomes=[1, 2, 3, 4]), require_draws=True)

    artifact = render_distribution(
        result,
        quantity="duration",
        unit="ms",
        resources="shared",
    )
    html = artifact.content.decode()

    assert artifact.shared_asset is not None
    assert artifact.shared_asset["location"].startswith(str(tmp_path))
    assert "file://" in html
    assert "%20" in html
    assert "Shared visualization library unavailable" in html


def test_inline_html_embeds_only_required_bokeh_library() -> None:
    result = parse_result_bytes(_result(outcomes=[1, 2, 3, 4]), require_draws=True)

    html = render_distribution(
        result,
        quantity="duration",
        unit="ms",
    ).content.decode()

    assert "BEGIN bokeh.min.js" in html
    assert "bokeh-widgets.min.js" not in html
    assert "cdn.bokeh.org" not in html


@pytest.mark.parametrize(
    "outcomes",
    [
        [1],
        [2, 2, 2, 2],
        [-5, -1, 0, 20],
        [0, 0, 1, 1, 10, 10],
    ],
)
def test_distribution_handles_single_constant_discrete_and_skewed_draws(
    outcomes: list[float],
) -> None:
    minimum = min(outcomes)
    maximum = max(outcomes)
    result = parse_result_bytes(
        _result(
            count=len(outcomes),
            minimum=minimum,
            median=(minimum + maximum) / 2,
            maximum=maximum,
            low=minimum,
            high=maximum,
            outcomes=outcomes,
        ),
        require_draws=True,
    )

    artifact = render_distribution(
        result,
        quantity="value",
        unit="unitless",
        resources="cdn",
    )

    assert artifact.content.startswith(b"<!doctype html>")
