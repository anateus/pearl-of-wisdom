import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1]
PLUGIN = ROOT / "plugins" / "pearl-of-wisdom"
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
WHEEL = PLUGIN / "cli" / f"pearl_of_wisdom-{VERSION}-py3-none-any.whl"


def test_installed_cli_and_check_run_without_uv_or_installation_writes(tmp_path: Path) -> None:
    installation = tmp_path / "installation"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    environment = os.environ.copy()
    environment.pop("VIRTUAL_ENV", None)
    environment.update(
        {
            "UV_CACHE_DIR": str(installation / "cache"),
            "UV_TOOL_DIR": str(installation / "tools"),
            "UV_TOOL_BIN_DIR": str(installation / "bin"),
            "UV_OFFLINE": "1",
            "UV_PYTHON_DOWNLOADS": "never",
        }
    )
    installed = subprocess.run(
        ["uv", "tool", "install", str(WHEEL)],
        cwd=workspace,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert installed.returncode == 0, installed.stderr
    environment["PATH"] = str(installation / "bin")
    assert shutil.which("uv", path=environment["PATH"]) is None
    prefix = []
    if sys.platform == "darwin":
        profile = "(version 1) (allow default) (deny file-write* (subpath "
        profile += json.dumps(str(installation.resolve())) + "))"
        prefix = ["/usr/bin/sandbox-exec", "-p", profile]
        # Prove that this sandbox actually blocks the writes the old runner needed.
        denied = subprocess.run(
            [
                *prefix,
                sys.executable,
                "-c",
                "from pathlib import Path; "
                f"Path({str(installation / 'cache' / 'known-write')!r}).touch()",
            ],
            cwd=workspace,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert denied.returncode != 0
        assert "PermissionError" in denied.stderr
    checked = subprocess.run(
        [*prefix, sys.executable, str(PLUGIN / "scripts" / "check_cli.py")],
        cwd=workspace,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked.returncode == 0, checked.stderr
    info = json.loads(checked.stdout)
    assert info["version"] == VERSION
    database = workspace / "pearl.sqlite3"
    created = subprocess.run(
        [*prefix, info["executable"], "--db", str(database), "create", "--status", "durable"],
        cwd=workspace,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT status FROM investigations").fetchall() == [("durable",)]


def test_durable_skill_links_to_the_active_plugins_check() -> None:
    skill = (PLUGIN / "skills" / "pearl-of-wisdom" / "SKILL.md").read_text()
    assert "(../../scripts/check_cli.py)" in skill
    assert "install_command" in skill


def test_package_and_both_plugins_agree_on_the_installed_version() -> None:
    from pearl_of_wisdom import __version__

    assert VERSION == __version__
    for manifest in (".claude-plugin", ".codex-plugin"):
        assert json.loads((PLUGIN / manifest / "plugin.json").read_text())["version"] == VERSION
