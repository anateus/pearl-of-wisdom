import json
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright
from test_browser import CHROME
from test_explain_contract import add_scenario
from test_explanation import write_context

from pearl_of_wisdom_viz.cli import main

pytestmark = pytest.mark.skipif(not CHROME.exists(), reason="Google Chrome is not installed")


def report_path(tmp_path: Path, *, resources: str = "inline") -> Path:
    path, context = write_context(tmp_path)
    add_scenario(tmp_path, context)
    context["question"] = "Will a project with a very long but readable title finish on time?"
    path.write_text(json.dumps(context))
    output = tmp_path / "report.html"
    assert (
        main(["explain", "--context", str(path), "--out", str(output), "--resources", resources])
        == 0
    )
    return output


def test_keyboard_switch_synchronizes_answer_formula_inputs_and_interval(tmp_path):
    path = report_path(tmp_path)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=str(CHROME), headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors, external = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "request",
            lambda request: (
                external.append(request.url) if request.url.startswith("http") else None
            ),
        )
        page.goto(path.as_uri())
        page.wait_for_selector(".bk-CartesianFrame")
        source = "Bokeh.documents[0].get_model_by_name('pearl-interval-data')"
        original_bounds = page.evaluate(f"{source}.data.low.concat({source}.data.high)")
        page.get_by_role("radio", name="Current scope").focus()
        page.keyboard.press("ArrowRight")
        assert page.get_by_role("radio", name="Another saved scenario").is_checked()
        assert "about 80 in 100" in page.locator(".scenario-answer.is-active").inner_text()
        assert "4 of 5" in page.locator(".scenario-answer.is-active").inner_text()
        assert (
            "5.0 percentage points higher"
            in page.locator(".scenario-answer.is-active").inner_text()
        )
        assert "x + 0" in page.locator(".formula .is-active").inner_text()
        assert page.locator(".assumptions:visible").count() == 1
        assert "about 80 in 100" in page.get_by_role("status").inner_text()
        assert page.evaluate(f"{source}.data.color") == ["#53606c", "#2257a6"]
        assert page.evaluate(
            "Bokeh.documents[0].get_model_by_name('pearl-ecdf-second').line_color.value"
        ) == "#2257a6"
        assert page.evaluate(
            "Bokeh.documents[0].get_model_by_name('pearl-ecdf-baseline').line_color.value"
        ) == "#53606c"
        assert page.evaluate(f"{source}.data.low.concat({source}.data.high)") == original_bounds
        for width in (1440, 390):
            page.set_viewport_size({"width": width, "height": 900})
            page.locator(".audit > summary").click()
            page.wait_for_function("document.documentElement.scrollWidth === innerWidth")
            assert page.evaluate("document.documentElement.scrollWidth") == width
            assert "exact fraction 0.8" in page.locator(".audit").inner_text()
            page.locator(".audit > summary").click()
        assert errors == []
        assert external == []
        browser.close()


@pytest.mark.parametrize("resources", ["inline", "shared", "cdn"])
def test_without_javascript_every_scenario_remains_readable(tmp_path, resources):
    path = report_path(tmp_path, resources=resources)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=str(CHROME), headless=True)
        page = browser.new_page(java_script_enabled=False, viewport={"width": 390, "height": 844})
        page.goto(path.as_uri())
        assert page.locator(".scenario-answer:visible").count() == 2
        assert page.locator(".assumptions:visible").count() == 2
        assert "about 75 in 100" in page.locator("body").inner_text()
        assert "about 80 in 100" in page.locator("body").inner_text()
        page.locator(".audit > summary").click()
        assert "exact fraction 0.8" in page.locator(".audit").inner_text()
        assert page.evaluate("document.documentElement.scrollWidth") == 390
        browser.close()


def test_missing_shared_assets_leave_answers_and_controls_usable(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "missing-assets"))
    path = report_path(tmp_path, resources="shared")
    (tmp_path / "missing-assets").rename(tmp_path / "detached-assets")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=str(CHROME), headless=True)
        page = browser.new_page()
        page.goto(path.as_uri())
        assert page.locator("#pearl-shared-error").is_visible()
        assert "Shared visualization library unavailable" in page.locator("body").inner_text()
        page.get_by_role("radio", name="Another saved scenario").check()
        assert "about 80 in 100" in page.locator(".scenario-answer.is-active").inner_text()
        assert page.locator(".limitations").is_visible()
        browser.close()
