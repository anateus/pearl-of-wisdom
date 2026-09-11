"""Behavior checks for the fail-open advisory hook dispatcher."""

import json
import subprocess
import sys
from pathlib import Path

DISPATCHER = Path(__file__).parents[1] / "plugins" / "pearl-of-wisdom" / "hooks" / "dispatcher.py"


def run_hook(payload: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DISPATCHER)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )


def test_hook_suggests_reasoning_without_echoing_prompt() -> None:
    prompt = "Estimate the probability of this uncertain regression."
    result = run_hook({"prompt": prompt})
    assert result.returncode == 0
    output = json.loads(result.stdout)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "$reasoning-under-uncertainty" in context
    assert prompt not in result.stdout
    assert len(context) <= 420


def test_hook_is_quiet_for_deterministic_prompt() -> None:
    result = run_hook({"prompt": "Rename this variable and run the formatter."})
    assert result.returncode == 0
    assert result.stdout == ""


def test_hook_fails_open_for_bad_or_oversized_input() -> None:
    bad = subprocess.run(
        [sys.executable, str(DISPATCHER)],
        input="not json",
        text=True,
        capture_output=True,
        check=False,
    )
    assert bad.returncode == 0
    assert bad.stdout == ""
    oversized = subprocess.run(
        [sys.executable, str(DISPATCHER)],
        input=json.dumps({"prompt": "x" * (64 * 1024)}),
        text=True,
        capture_output=True,
        check=False,
    )
    assert oversized.returncode == 0
    assert oversized.stdout == ""
