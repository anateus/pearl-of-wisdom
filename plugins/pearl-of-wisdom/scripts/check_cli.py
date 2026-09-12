#!/usr/bin/env python3
"""Check the installed CLI without installing packages or opening a database."""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    required = json.loads((root / ".codex-plugin" / "plugin.json").read_text())["version"]
    required = required.split("+", 1)[0]
    minimum = tuple(int(part) for part in required.split("."))
    maximum = (minimum[0], minimum[1] + 1, 0)
    supported = f">={required},<{'.'.join(map(str, maximum))}"
    wheel = root / "cli" / f"pearl_of_wisdom-{required}-py3-none-any.whl"

    def fail(code: str, message: str) -> int:
        error = {"code": code, "message": message, "required": supported}
        if executable is not None:
            error["executable"] = executable
        if wheel.is_file():
            error["install_command"] = shlex.join(
                ["uv", "tool", "install", "--reinstall", str(wheel)]
            )
        else:
            error["message"] += " Reload or update the plugin: its install wheel is missing."
        print(json.dumps({"compatible": False, "error": error}), file=sys.stderr)
        return 1

    executable = shutil.which("pearl-of-wisdom")
    if executable is None:
        return fail("cli_missing", "pearl-of-wisdom is not on PATH.")
    executable = str(Path(executable).absolute())
    try:
        result = subprocess.run(
            [executable, "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return fail("cli_unavailable", "The installed CLI could not report its version.")
    match = re.fullmatch(r"pearl-of-wisdom (\d+)\.(\d+)\.(\d+)", result.stdout.strip())
    if result.returncode or match is None:
        return fail("cli_incompatible", "The installed CLI did not report a supported version.")
    version = ".".join(match.groups())
    if not minimum <= tuple(map(int, match.groups())) < maximum:
        return fail("cli_incompatible", f"Installed CLI {version} is outside {supported}.")
    print(
        json.dumps(
            {
                "compatible": True,
                "executable": executable,
                "version": version,
                "required": supported,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
