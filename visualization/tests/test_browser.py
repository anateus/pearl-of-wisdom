import json
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

from pearl_of_wisdom_viz.model import parse_result_bytes
from pearl_of_wisdom_viz.render import render_distribution, render_forest

CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def _result(outcomes: list[float], *, seed: int = 7) -> bytes:
    ordered = sorted(outcomes)
    count = len(ordered)
    data = {
        "count": count,
        "mean": sum(ordered) / count,
        "standard_deviation": 1.0,
        "minimum": ordered[0],
        "maximum": ordered[-1],
        "quantiles": {"0.05": ordered[0], "0.5": ordered[count // 2], "0.95": ordered[-1]},
        "draws": {
            "schema_version": 1,
            "population": count,
            "returned": count,
            "selection": "all",
            "indices": list(range(count)),
            "outcome": outcomes,
            "inputs": {},
            "provenance": {
                "pearl_version": "0.3.0",
                "python_version": "3.12.11",
                "effective_request": {
                    "variables": {"x": {"distribution": "constant", "value": 1}},
                    "expression": "x",
                    "samples": count,
                    "seed": seed,
                    "quantiles": [0.05, 0.5, 0.95],
                },
                "input_order": ["x"],
            },
        },
    }
    return json.dumps(
        {
            "engine": "monte_carlo",
            "capabilities": [],
            "data": data,
            "metadata": {"samples": count, "seed": seed},
        }
    ).encode()


def _open(page: Page, path: Path) -> None:
    page.goto(path.as_uri())
    page.wait_for_selector(".bk-CartesianFrame")


@pytest.mark.skipif(not CHROME.exists(), reason="Google Chrome is not installed")
def test_distribution_browser_hover_zoom_reset_and_static_fallback(tmp_path: Path) -> None:
    result = parse_result_bytes(
        _result(
            [
                0.1234567890123456,
                1.2345678901234567,
                2.345678901234567,
                3.456789012345678,
                4.567890123456789,
                5.67890123456789,
                6.789012345678901,
            ]
        ),
        require_draws=True,
    )
    path = tmp_path / "distribution.html"
    path.write_bytes(
        render_distribution(result, quantity="latency", unit="ms", resources="inline").content
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=str(CHROME), headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        _open(page, path)

        frame = page.locator(".bk-CartesianFrame").bounding_box()
        point = page.evaluate(
            """() => {
                const models = [...Bokeh.documents[0]._all_models.values()];
                const plot = models.find((model) => model.type === "Figure");
                const source = models.find(
                    (model) => model.type === "ColumnDataSource" && model.data?.outcome
                );
                return {
                    x0: plot.x_range.start, x1: plot.x_range.end,
                    y0: plot.y_range.start, y1: plot.y_range.end,
                    x: source.data.outcome[1], y: source.data.cumulative[1],
                };
            }"""
        )
        assert frame is not None
        page.mouse.move(
            frame["x"] + (point["x"] - point["x0"]) / (point["x1"] - point["x0"]) * frame["width"],
            frame["y"] + (point["y1"] - point["y"]) / (point["y1"] - point["y0"]) * frame["height"],
        )
        page.wait_for_timeout(100)
        tooltip = page.evaluate(
            "() => document.querySelector('.bk-Tooltip')?.shadowRoot?.textContent || ''"
        )
        assert "Outcome" in tooltip
        assert "Cumulative" in tooltip
        assert str(point["x"]) in tooltip
        assert str(point["y"]) in tooltip

        before = (point["x0"], point["x1"])
        page.locator(".bk-tool-icon-wheel-zoom").click()
        page.mouse.move(frame["x"] + frame["width"] / 2, frame["y"] + frame["height"] / 2)
        page.mouse.wheel(0, -600)
        after = page.evaluate(
            """() => {
                const plot = [...Bokeh.documents[0]._all_models.values()]
                    .find((model) => model.type === "Figure");
                return [plot.x_range.start, plot.x_range.end];
            }"""
        )
        assert after[1] - after[0] < before[1] - before[0]

        page.locator(".bk-tool-icon-reset").click()
        reset = page.evaluate(
            """() => {
                const plot = [...Bokeh.documents[0]._all_models.values()]
                    .find((model) => model.type === "Figure");
                return [plot.x_range.start, plot.x_range.end];
            }"""
        )
        assert reset == pytest.approx(before)
        assert errors == []

        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(100)
        dimensions = page.evaluate("() => [document.documentElement.scrollWidth, innerWidth]")
        assert dimensions == [390, 390]
        assert page.locator('td[data-label="Maximum"]').is_visible()

        static_context = browser.new_context(java_script_enabled=False)
        static_page = static_context.new_page()
        static_page.goto(path.as_uri())
        text = static_page.locator("body").inner_text()
        assert "Full-run summary" in text
        assert "Rendering doesn't establish that the inputs are calibrated" in text
        static_context.close()
        browser.close()


@pytest.mark.skipif(not CHROME.exists(), reason="Google Chrome is not installed")
def test_forest_browser_legend_click_hides_scenario(tmp_path: Path) -> None:
    results = (
        parse_result_bytes(_result([1, 2, 3, 4], seed=1)),
        parse_result_bytes(_result([5, 6, 7, 8], seed=2)),
    )
    path = tmp_path / "forest.html"
    path.write_bytes(
        render_forest(
            results,
            ("baseline", "candidate"),
            quantity="latency",
            unit="ms",
            resources="inline",
        ).content
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=str(CHROME), headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        _open(page, path)
        frame = page.locator(".bk-CartesianFrame").bounding_box()
        assert frame is not None
        page.mouse.click(frame["x"] + frame["width"] - 90, frame["y"] + 50)
        visibility = page.evaluate(
            """() => [...Bokeh.documents[0]._all_models.values()]
                .filter((model) => model.type === "GlyphRenderer")
                .map((model) => model.visible)"""
        )
        assert visibility == [False, False, True, True]
        browser.close()


@pytest.mark.skipif(not CHROME.exists(), reason="Google Chrome is not installed")
def test_shared_resources_load_from_file_while_offline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PEARL_VIZ_ASSETS_DIR", str(tmp_path / "assets with spaces"))
    result = parse_result_bytes(_result([1, 2, 3, 4]), require_draws=True)
    path = tmp_path / "shared.html"
    path.write_bytes(
        render_distribution(result, quantity="latency", unit="ms", resources="shared").content
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=str(CHROME), headless=True)
        context = browser.new_context(offline=True)
        page = context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        _open(page, path)
        assert page.locator("canvas").count() > 0
        assert errors == []
        browser.close()
