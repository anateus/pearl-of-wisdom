"""Opt-in, real-session coverage for the Claude Code host integration.

Run with ``PEARL_RUN_HOST_E2E=1 uv run pytest tests/e2e/test_claude_host.py``.
The tests intentionally make networked model requests and are therefore off by
default in normal unit-test runs.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
PLUGIN = ROOT / "plugins" / "pearl-of-wisdom"
ROUTING_CASES = json.loads((PLUGIN / "evals" / "routing-cases.json").read_text())["cases"]
SESSION_TIMEOUT_SECONDS = int(os.environ.get("PEARL_HOST_E2E_TIMEOUT_SECONDS", "180"))


def _claude() -> str:
    if not os.environ.get("PEARL_RUN_HOST_E2E"):
        pytest.skip("Claude host E2E is opt-in; set PEARL_RUN_HOST_E2E=1")
    executable = shutil.which("claude")
    if executable is None:
        pytest.skip("Claude host E2E requires the `claude` CLI on PATH")
    auth = subprocess.run(
        [executable, "auth", "status"], capture_output=True, text=True, timeout=15, check=False
    )
    if auth.returncode and not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("Claude host E2E authentication unavailable: `claude auth status` failed")
    return executable


def _routing_case(label: str) -> dict[str, object]:
    return next(case for case in ROUTING_CASES if case["label"] == label)


def _session(
    claude: str, prompt: str, tmp_path: Path, *, load_plugin: bool
) -> tuple[list[dict[str, object]], str]:
    """Run one noninteractive Claude session and expose host debug evidence."""
    debug_log = tmp_path / ("with-plugin.debug" if load_plugin else "without-plugin.debug")
    command = [
        claude,
        "--print",
        "--no-session-persistence",
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-hook-events",
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--debug-file",
        str(debug_log),
        "--permission-mode",
        "dontAsk",
        "--max-turns",
        "3",
    ]
    if load_plugin:
        command.extend(["--plugin-dir", str(PLUGIN)])
    command.append(prompt)

    environment = os.environ.copy()
    # API-key authentication can use a disposable config directory. OAuth stays
    # in its existing read-only location, while --setting-sources disables caller
    # settings and --no-session-persistence prevents session writes.
    if environment.get("ANTHROPIC_API_KEY"):
        environment["CLAUDE_CONFIG_DIR"] = str(tmp_path / "claude-config")

    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=SESSION_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        debug = debug_log.read_text(errors="replace") if debug_log.exists() else ""
        loaded = "Loaded inline plugin from path: pearl-of-wisdom" in debug
        advised = "Advisory: use $reasoning-under-uncertainty" in debug
        pytest.fail(
            f"Claude model session timed out after {SESSION_TIMEOUT_SECONDS}s "
            f"(plugin_loaded={loaded}, uncertainty_advisory={advised})"
        )
    try:
        events = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    except json.JSONDecodeError as error:
        pytest.fail(f"Claude did not return JSONL output: {completed.stdout[:1000]!r} ({error})")
    if completed.returncode:
        failures = [event for event in events if event.get("type") == "result"]
        details = [
            str(value)
            for event in failures
            for key in ("terminal_reason", "errors")
            if (value := event.get(key))
        ]
        detail = "; ".join(details) or completed.stderr[-1000:].strip() or "no error detail"
        pytest.fail(f"Claude noninteractive session failed ({completed.returncode}): {detail}")

    results = [event for event in events if event.get("type") == "result"]
    assert len(results) == 1, "Claude session did not emit exactly one result event"
    result = results[0].get("result")
    assert isinstance(result, str) and result.strip(), "Claude session returned no model result"
    return events, debug_log.read_text(errors="replace") if debug_log.exists() else ""


def _skill_uses(events: list[dict[str, object]]) -> list[str]:
    uses: list[str] = []
    for event in events:
        message = event.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("name") != "Skill":
                continue
            skill_input = block.get("input")
            if isinstance(skill_input, dict) and isinstance(skill_input.get("skill"), str):
                uses.append(skill_input["skill"])
    return uses


def test_skill_use_parser_requires_a_real_skill_tool_block() -> None:
    events = [
        {"type": "system", "tools": ["Skill"]},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Skill",
                        "input": {"skill": "pearl-of-wisdom:reasoning-under-uncertainty"},
                    }
                ]
            },
        },
    ]
    assert _skill_uses(events) == ["pearl-of-wisdom:reasoning-under-uncertainty"]


def test_claude_plugin_routes_positive_prompt_and_leaves_negative_prompt_unrouted(
    tmp_path: Path,
) -> None:
    """The installed host must execute the hook only for the matching prompt."""
    claude = _claude()
    positive_case = _routing_case("positive")
    negative_case = _routing_case("negative")
    positive_prompt = f"{positive_case['prompt']} Use any applicable installed skill first."
    negative_prompt = f"{negative_case['prompt']} Use any applicable installed skill first."

    positive, positive_debug = _session(claude, positive_prompt, tmp_path, load_plugin=True)
    negative, negative_debug = _session(claude, negative_prompt, tmp_path, load_plugin=True)

    positive_skills = _skill_uses(positive)
    negative_skills = _skill_uses(negative)
    assert any(skill.endswith("reasoning-under-uncertainty") for skill in positive_skills)
    assert not any(
        skill.endswith(("reasoning-under-uncertainty", "pearl-of-wisdom"))
        for skill in negative_skills
    )
    assert "Loaded inline plugin from path: pearl-of-wisdom" in positive_debug
    assert "UserPromptSubmit" in positive_debug
    assert "Advisory: use $reasoning-under-uncertainty" in positive_debug
    assert "Loaded inline plugin from path: pearl-of-wisdom" in negative_debug
    assert "Advisory: use $reasoning-under-uncertainty" not in negative_debug
