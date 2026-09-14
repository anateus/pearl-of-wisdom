import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).parents[1] / "plugins" / "pearl-of-wisdom"
CHECK = PLUGIN / "scripts" / "check_cli.py"


def _check(
    tmp_path: Path,
    output: str | None,
    *,
    status: int = 0,
    check: Path = CHECK,
    relative_path: bool = False,
):
    binaries = tmp_path / "bin"
    binaries.mkdir()
    if output is not None:
        cli = binaries / "pearl-of-wisdom"
        cli.write_text(
            f"#!{sys.executable}\nimport sys\n"
            "assert sys.argv[1:] == ['--version']\n"
            f"print({output!r})\nsys.exit({status})\n"
        )
        cli.chmod(0o755)
    environment = os.environ.copy()
    environment["PATH"] = "bin" if relative_path else str(binaries)
    return subprocess.run(
        [sys.executable, str(check)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("version", ["0.4.0", "0.4.1", "0.4.99"])
def test_compatible_patch_does_not_need_uv(tmp_path: Path, version: str) -> None:
    result = _check(tmp_path, f"pearl-of-wisdom {version}")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "compatible": True,
        "executable": str(tmp_path / "bin" / "pearl-of-wisdom"),
        "version": version,
        "required": ">=0.4.0,<0.5.0",
    }
    assert result.stderr == ""
    assert sorted(path.name for path in tmp_path.iterdir()) == ["bin"]


@pytest.mark.parametrize(
    "version", ["0.3.99", "0.3.0", "0.2.0", "0.1.0", "0.5.0", "1.0.0", "0.4.0rc1"]
)
def test_rejects_incompatible_versions(tmp_path: Path, version: str) -> None:
    result = _check(tmp_path, f"pearl-of-wisdom {version}")
    assert result.returncode == 1
    assert result.stdout == ""
    error = json.loads(result.stderr)["error"]
    assert error["code"] == "cli_incompatible"
    assert error["required"] == ">=0.4.0,<0.5.0"


@pytest.mark.parametrize(
    "output,status", [(None, 0), ("unsupported --version", 1), ("other 0.3.0", 0)]
)
def test_missing_or_unrecognized_cli_stops_with_install_hint(
    tmp_path: Path, output: str | None, status: int
) -> None:
    result = _check(tmp_path, output, status=status)
    assert result.returncode == 1
    assert result.stdout == ""
    error = json.loads(result.stderr)["error"]
    assert error["code"] == ("cli_missing" if output is None else "cli_incompatible")
    assert shlex.split(error["install_command"]) == [
        "uv",
        "tool",
        "install",
        "--reinstall",
        str(PLUGIN / "cli" / "pearl_of_wisdom-0.4.0-py3-none-any.whl"),
    ]


def test_install_hint_uses_the_loaded_plugin_and_quotes_spaces(tmp_path: Path) -> None:
    plugin = tmp_path / "installed plugin"
    shutil.copytree(PLUGIN, plugin)
    result = _check(tmp_path, None, check=plugin / "scripts" / "check_cli.py")
    assert result.returncode == 1
    command = json.loads(result.stderr)["error"]["install_command"]
    assert shlex.split(command)[-1] == str(
        plugin / "cli" / "pearl_of_wisdom-0.4.0-py3-none-any.whl"
    )


@pytest.mark.parametrize("version", [None, "0.3.0", "0.4.0"])
def test_codex_cachebuster_preserves_cli_requirement(tmp_path: Path, version: str | None) -> None:
    plugin = tmp_path / "installed plugin"
    shutil.copytree(PLUGIN, plugin)
    manifest_path = plugin / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["version"] = "0.4.0+codex.20260914000000"
    manifest_path.write_text(json.dumps(manifest))
    result = _check(
        tmp_path,
        f"pearl-of-wisdom {version}" if version else None,
        check=plugin / "scripts" / "check_cli.py",
    )
    if version == "0.4.0":
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["required"] == ">=0.4.0,<0.5.0"
    else:
        assert result.returncode == 1
        error = json.loads(result.stderr)["error"]
        assert error["code"] == ("cli_missing" if version is None else "cli_incompatible")
        assert error["required"] == ">=0.4.0,<0.5.0"
        assert shlex.split(error["install_command"])[-1] == str(
            plugin / "cli" / "pearl_of_wisdom-0.4.0-py3-none-any.whl"
        )


def test_relative_path_entry_returns_an_absolute_executable(tmp_path: Path) -> None:
    result = _check(tmp_path, "pearl-of-wisdom 0.4.0", relative_path=True)
    assert result.returncode == 0, result.stderr
    executable = json.loads(result.stdout)["executable"]
    assert Path(executable).is_absolute()
    assert executable == str(tmp_path / "bin" / "pearl-of-wisdom")


def test_missing_install_wheel_requests_plugin_repair(tmp_path: Path) -> None:
    plugin = tmp_path / "incomplete-plugin"
    shutil.copytree(PLUGIN, plugin, ignore=shutil.ignore_patterns("*.whl"))
    result = _check(tmp_path, None, check=plugin / "scripts" / "check_cli.py")
    assert result.returncode == 1
    error = json.loads(result.stderr)["error"]
    assert "install_command" not in error
    assert "install wheel is missing" in error["message"]
