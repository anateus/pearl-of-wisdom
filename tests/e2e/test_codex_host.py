"""Opt-in, real-session coverage for the Codex host integration.

Run with ``PEARL_RUN_HOST_E2E=1 uv run pytest tests/e2e/test_codex_host.py``.
The test makes networked model requests and is therefore off by default.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
PLUGIN = ROOT / "plugins" / "pearl-of-wisdom"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
BUNDLED_WHEEL = PLUGIN / "cli" / f"pearl_of_wisdom-{VERSION}-py3-none-any.whl"
SESSION_TIMEOUT_SECONDS = 240


def _codex() -> str:
    if not os.environ.get("PEARL_RUN_HOST_E2E"):
        pytest.skip("Codex host E2E is opt-in; set PEARL_RUN_HOST_E2E=1")
    executable = shutil.which("codex")
    if executable is None:
        pytest.skip("Codex host E2E requires the `codex` CLI on PATH")
    return executable


def _without_pearl_cli(environment: dict[str, str]) -> dict[str, str]:
    """Keep host tooling available while removing every bare Pearl CLI from PATH."""
    clean = environment.copy()
    clean["PATH"] = os.pathsep.join(
        directory
        for directory in environment.get("PATH", "").split(os.pathsep)
        if directory and not (Path(directory) / "pearl-of-wisdom").is_file()
    )
    return clean


def test_environment_without_pearl_cli_removes_cli_directories(tmp_path: Path) -> None:
    with_cli = tmp_path / "with-cli"
    with_cli.mkdir()
    (with_cli / "pearl-of-wisdom").write_text("placeholder")
    other = tmp_path / "other"
    other.mkdir()

    environment = _without_pearl_cli({"PATH": os.pathsep.join((str(with_cli), str(other)))})

    assert environment["PATH"] == str(other)
    assert shutil.which("pearl-of-wisdom", path=environment["PATH"]) is None


def _run(
    command: list[str], environment: dict[str, str], *, timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        pytest.fail(f"Codex command timed out after {timeout}s: {command!r} ({error})")
    return completed


def _prepare_installed_plugin(codex: str, tmp_path: Path) -> dict[str, str]:
    """Install this checkout through a disposable real Codex marketplace."""
    source_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir(parents=True, mode=0o700)

    source_auth = source_home / "auth.json"
    if source_auth.is_file():
        copied_auth = codex_home / "auth.json"
        shutil.copy2(source_auth, copied_auth)
        copied_auth.chmod(0o600)

    environment = _without_pearl_cli(os.environ.copy())
    environment["CODEX_HOME"] = str(codex_home)
    assert shutil.which("pearl-of-wisdom", path=environment["PATH"]) is None

    auth = _run([codex, "login", "status"], environment)
    if auth.returncode and not environment.get("OPENAI_API_KEY"):
        detail = (auth.stdout + "\n" + auth.stderr).strip()
        pytest.skip(f"Codex host E2E authentication unavailable: {detail[:300]}")

    marketplace = tmp_path / "marketplace"
    manifest_dir = marketplace / ".agents" / "plugins"
    manifest_dir.mkdir(parents=True)
    plugins_dir = marketplace / "plugins"
    plugins_dir.mkdir()
    (plugins_dir / "pearl-of-wisdom").symlink_to(PLUGIN, target_is_directory=True)
    (manifest_dir / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "pearl-e2e",
                "interface": {"displayName": "Pearl E2E"},
                "plugins": [
                    {
                        "name": "pearl-of-wisdom",
                        "source": {
                            "source": "local",
                            "path": "./plugins/pearl-of-wisdom",
                        },
                        "policy": {
                            "installation": "AVAILABLE",
                            "authentication": "ON_INSTALL",
                        },
                        "category": "Developer Tools",
                    }
                ],
            }
        )
    )

    marketplace_add = _run(
        [codex, "plugin", "marketplace", "add", str(marketplace), "--json"],
        environment,
    )
    assert marketplace_add.returncode == 0, (
        "Codex rejected the temporary local marketplace: "
        f"{(marketplace_add.stdout + marketplace_add.stderr)[:1000]}"
    )

    plugin_add = _run(
        [codex, "plugin", "add", "pearl-of-wisdom@pearl-e2e", "--json"],
        environment,
    )
    assert plugin_add.returncode == 0, (
        "Codex failed to install the checkout plugin: "
        f"{(plugin_add.stdout + plugin_add.stderr)[:1000]}"
    )

    installed = _run([codex, "plugin", "list", "--json"], environment)
    assert installed.returncode == 0, installed.stderr[:1000]
    installed_payload = json.loads(installed.stdout)
    matching_plugins = [
        plugin
        for plugin in installed_payload["installed"]
        if plugin["pluginId"] == "pearl-of-wisdom@pearl-e2e"
    ]
    assert len(matching_plugins) == 1
    installed_plugin = matching_plugins[0]
    assert installed_plugin["installed"] is True
    assert installed_plugin["enabled"] is True
    assert Path(installed_plugin["source"]["path"]).resolve() == PLUGIN.resolve()
    tool_bin = tmp_path / "tool-bin"
    install_environment = environment.copy()
    install_environment.update(
        {
            "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
            "UV_TOOL_DIR": str(tmp_path / "uv-tools"),
            "UV_TOOL_BIN_DIR": str(tool_bin),
        }
    )
    installed_cli = _run(["uv", "tool", "install", str(BUNDLED_WHEEL)], install_environment)
    assert installed_cli.returncode == 0, installed_cli.stderr
    (tool_bin / "python3").symlink_to(sys.executable)
    environment["PATH"] = os.pathsep.join((str(tool_bin), "/usr/bin", "/bin"))
    assert shutil.which("uv", path=environment["PATH"]) is None
    assert shutil.which("uvx", path=environment["PATH"]) is None
    assert shutil.which("pearl-of-wisdom", path=environment["PATH"]) is not None
    configuration = codex_home / "config.toml"
    configuration.write_text("allow_login_shell = false\n" + configuration.read_text())
    return environment


def _session(
    codex: str,
    prompt: str,
    case_dir: Path,
    environment: dict[str, str],
    *,
    sandbox: str = "read-only",
) -> tuple[str, list[dict[str, object]]]:
    """Run a fresh model session and return its final answer and JSONL evidence."""
    case_dir.mkdir(parents=True)
    workspace = case_dir / "workspace"
    workspace.mkdir()
    final_message = case_dir / "final.txt"
    command_contract = (
        "You may use shell commands to read skill instructions and to perform the requested "
        "durable workflow. "
        if sandbox == "workspace-write"
        else (
            "You may use shell commands only to read relevant skill instructions; "
            "do not edit files. "
        )
    )
    routing_contract = (
        "Consider only the installed pearl-of-wisdom and reasoning-under-uncertainty skills. "
        "Use one when its description matches this request. Report none when neither matches, "
        "even if unrelated skills are available. Only report a Pearl skill after actually "
        "loading its SKILL.md. " + command_contract + "Start the final response "
        "with exactly `SKILL_USED: <skill-name>` or `SKILL_USED: none`.\n\n"
    )
    completed = _run(
        [
            codex,
            "exec",
            "--ephemeral",
            "--json",
            "--skip-git-repo-check",
            "--sandbox",
            sandbox,
            "--output-last-message",
            str(final_message),
            "-C",
            str(workspace),
            routing_contract + prompt,
        ],
        environment,
        timeout=SESSION_TIMEOUT_SECONDS,
    )
    combined = (completed.stdout + "\n" + completed.stderr).strip()
    if completed.returncode:
        lowered = combined.casefold()
        if any(term in lowered for term in ("unauthorized", "authentication", "log in", "api key")):
            pytest.skip(f"Codex host E2E authentication unavailable: {combined[:300]}")
        pytest.fail(f"Codex model session failed ({completed.returncode}): {combined[:1200]}")

    try:
        events = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    except json.JSONDecodeError as error:
        pytest.fail(f"Codex did not emit valid JSONL: {completed.stdout[:1000]!r} ({error})")
    assert events, "Codex session emitted no JSONL events"
    assert final_message.is_file(), "Codex did not write its final model message"
    answer = final_message.read_text(errors="replace").strip()
    assert answer, "Codex session returned an empty final model message"
    return answer, events


def _commands(events: list[dict[str, object]]) -> list[str]:
    commands = []
    for event in events:
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "command_execution":
            commands.append(str(item.get("command", "")))
    return commands


def _remove_installed_plugin(codex: str, environment: dict[str, str]) -> None:
    removed = _run([codex, "plugin", "remove", "pearl-of-wisdom@pearl-e2e", "--json"], environment)
    assert removed.returncode == 0, (removed.stdout + removed.stderr)[:1000]
    listed = _run([codex, "plugin", "list", "--json"], environment)
    assert listed.returncode == 0, listed.stderr[:1000]
    installed = json.loads(listed.stdout)["installed"]
    assert all(plugin["pluginId"] != "pearl-of-wisdom@pearl-e2e" for plugin in installed)


def test_codex_routes_positive_prompt_and_leaves_negative_prompt_outside_pearl(
    tmp_path: Path,
) -> None:
    codex = _codex()
    environment = _prepare_installed_plugin(codex, tmp_path)

    positive_answer, positive_events = _session(
        codex,
        "Calculate the exact failure probability from these finite counts: "
        "7 failures in 100 independent trials. Explain the uncertainty method briefly.",
        tmp_path / "positive",
        environment,
    )
    negative_answer, negative_events = _session(
        codex,
        "Rename a private function and update its callers. Explain the mechanical steps briefly.",
        tmp_path / "negative",
        environment,
    )
    ambiguous_answer, ambiguous_events = _session(
        codex,
        "The latest deploy may have caused the regression. What should we check?",
        tmp_path / "ambiguous",
        environment,
    )

    positive_commands = _commands(positive_events)
    negative_commands = _commands(negative_events)
    positive_marker = positive_answer.splitlines()[0]
    assert positive_marker.startswith("SKILL_USED: ")
    assert positive_marker.endswith("reasoning-under-uncertainty")
    assert any(
        "skills/reasoning-under-uncertainty/SKILL.md" in command for command in positive_commands
    ), positive_commands
    assert negative_answer.startswith("SKILL_USED: none")
    assert not any("reasoning-under-uncertainty" in command for command in negative_commands)
    assert not any("pearl-of-wisdom" in command for command in negative_commands)

    ambiguous_marker = ambiguous_answer.splitlines()[0]
    assert ambiguous_marker.startswith("SKILL_USED: ")
    reported_skill = ambiguous_marker.removeprefix("SKILL_USED: ")
    selected_skill = reported_skill.rsplit(":", 1)[-1]
    assert selected_skill in {"reasoning-under-uncertainty", "pearl-of-wisdom", "none"}
    ambiguous_commands = _commands(ambiguous_events)
    if selected_skill != "none":
        assert any(f"skills/{selected_skill}/SKILL.md" in command for command in ambiguous_commands)

    database = tmp_path / "durable" / "workspace" / "pearl.sqlite3"
    durable_answer, durable_events = _session(
        codex,
        "Use the pearl-of-wisdom skill and its installed CLI. "
        f"Create one durable investigation in {database}. Record one context entry whose JSON "
        'is exactly {"question":"Will the release queue exceed capacity?"}, then show the record.',
        tmp_path / "durable",
        environment,
        sandbox="workspace-write",
    )
    assert durable_answer.startswith("SKILL_USED: pearl-of-wisdom")
    durable_commands = _commands(durable_events)
    assert any("skills/pearl-of-wisdom/SKILL.md" in command for command in durable_commands)
    assert any(
        "pearl-of-wisdom" in command and "record-context" in command for command in durable_commands
    )
    assert any("check_cli.py" in command for command in durable_commands)
    assert not any(
        "uv tool " in command or "uv run " in command or "uvx " in command
        for command in durable_commands
    )

    installed_cli = [shutil.which("pearl-of-wisdom", path=environment["PATH"])]
    listed = _run([*installed_cli, "--db", str(database), "list"], environment)
    assert listed.returncode == 0, listed.stderr[:1000]
    investigations = json.loads(listed.stdout)
    assert len(investigations) == 1
    shown = _run(
        [*installed_cli, "--db", str(database), "show", investigations[0]["id"]], environment
    )
    assert shown.returncode == 0, shown.stderr[:1000]
    record = json.loads(shown.stdout)
    assert record["status"] == "durable"
    assert [entry["payload"] for entry in record["context"]] == [
        {"question": "Will the release queue exceed capacity?"}
    ]

    _remove_installed_plugin(codex, environment)
