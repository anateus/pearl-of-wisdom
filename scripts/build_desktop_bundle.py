"""Build the Desktop extension from an allowlist, using the official MCPB CLI."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MCPB_PACKAGE = "@anthropic-ai/mcpb"
MCPB_VERSION = "2.1.2"
MCPB_COMMAND = ["npx", "--yes", f"{MCPB_PACKAGE}@{MCPB_VERSION}"]
TEMPLATE_FILES = ("manifest.json", "pyproject.toml", ".mcpbignore", "server.py")


def stage_bundle(root: Path, staging: Path, *, refresh_lock: bool = False) -> str:
    """Copy only runtime inputs. Never copy a repository tree or environment."""
    manifest = json.loads((root / "desktop/manifest.json").read_text())
    version = manifest["version"]
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    desktop = tomllib.loads((root / "desktop/pyproject.toml").read_text())["project"]
    if project["version"] != version or desktop["version"] != version:
        raise ValueError("Root, Desktop project and manifest versions must match")
    if f"pearl-of-wisdom=={version}" not in desktop["dependencies"]:
        raise ValueError("Desktop must pin the matching core wheel version")
    wheel_name = f"pearl_of_wisdom-{version}-py3-none-any.whl"
    wheel = root / "plugins/pearl-of-wisdom/cli" / wheel_name
    source = tomllib.loads((root / "desktop/pyproject.toml").read_text())["tool"]["uv"]["sources"]
    if source["pearl-of-wisdom"] != {"path": f"wheels/{wheel_name}"}:
        raise ValueError("Core dependency must resolve from the bundled local wheel")
    # An exact wheel allowlist also prevents accidental inclusion of private build inputs.
    with zipfile.ZipFile(wheel) as archive:
        metadata_dir = f"pearl_of_wisdom-{version}.dist-info"
        metadata = Parser().parsestr(archive.read(f"{metadata_dir}/METADATA").decode())
        if metadata["Name"] != "pearl-of-wisdom" or metadata["Version"] != version:
            raise ValueError("Bundled wheel metadata must match the core version")
        allowed_metadata = {
            f"{metadata_dir}/{name}"
            for name in ("METADATA", "WHEEL", "RECORD", "entry_points.txt", "licenses/LICENSE")
        }
        for name in archive.namelist():
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"Unsafe wheel member: {name}")
            if not (
                name.startswith("pearl_of_wisdom/")
                or name.startswith(f"pearl_of_wisdom-{version}.dist-info/")
            ):
                raise ValueError(f"Unexpected wheel member: {name}")
            if name.endswith("/"):
                continue
            if name.startswith("pearl_of_wisdom/") and not name.endswith(".py"):
                raise ValueError(f"Unexpected core runtime file: {name}")
            if name.startswith(f"{metadata_dir}/") and name not in allowed_metadata:
                raise ValueError(f"Unexpected wheel metadata file: {name}")
    for name in TEMPLATE_FILES:
        shutil.copyfile(root / "desktop" / name, staging / name)
    for name in ("LICENSE", "pearl.png"):
        shutil.copyfile(root / name, staging / name)
    (staging / "wheels").mkdir()
    shutil.copyfile(wheel, staging / "wheels" / wheel_name)
    if not refresh_lock:
        shutil.copyfile(root / "desktop/uv.lock", staging / "uv.lock")
    return version


def build_bundle(root: Path, out_dir: Path, *, refresh_lock: bool = False) -> Path:
    """Validate the lock and pack a clean, portable extension with pinned tooling."""
    out_dir.mkdir(parents=True, exist_ok=True)
    scratch = os.environ.get("JCODE_SCRATCH_DIR") or None
    with (
        tempfile.TemporaryDirectory(prefix="pearl-desktop-", dir=scratch) as directory,
        tempfile.TemporaryDirectory(prefix=".pearl-output-", dir=out_dir) as output_directory,
    ):
        staging = Path(directory)
        version = stage_bundle(root, staging, refresh_lock=refresh_lock)
        if refresh_lock:
            subprocess.run(["uv", "lock", "--directory", str(staging)], check=True)
        subprocess.run(["uv", "lock", "--check", "--directory", str(staging)], check=True)
        # Resolve/install the actual local wheel, not Pearl from an index. The environment
        # is only for validation and the official packer must not ship it.
        subprocess.run(["uv", "sync", "--locked", "--directory", str(staging)], check=True)
        lock = (staging / "uv.lock").read_text()
        if str(root) in lock or str(staging) in lock or "file://" in lock:
            raise ValueError("Lock contains a non-portable local path")
        if refresh_lock:
            shutil.copyfile(staging / "uv.lock", root / "desktop/uv.lock")
        subprocess.run([*MCPB_COMMAND, "validate", str(staging / "manifest.json")], check=True)
        artifact = out_dir / f"pearl-of-wisdom-{version}.mcpb"
        pending = Path(output_directory) / artifact.name
        subprocess.run([*MCPB_COMMAND, "pack", str(staging), str(pending)], check=True)
        with zipfile.ZipFile(pending) as archive:
            expected = {
                *TEMPLATE_FILES,
                "uv.lock",
                "LICENSE",
                "pearl.png",
                f"wheels/pearl_of_wisdom-{version}-py3-none-any.whl",
            }
            # Some CLI releases omit .mcpbignore itself, which is not a runtime input.
            required = expected - {".mcpbignore"}
            names = {name for name in archive.namelist() if not name.endswith("/")}
            if not required <= names or not names <= expected:
                raise ValueError(f"Unexpected bundle content: {sorted(names ^ required)}")
        # Pending output lives on the same filesystem, so a failed build never
        # replaces an existing usable artifact and successful publication is atomic.
        os.replace(pending, artifact)
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "dist")
    parser.add_argument(
        "--refresh-lock",
        action="store_true",
        help="Regenerate desktop/uv.lock from clean staging before packing",
    )
    args = parser.parse_args()
    artifact = build_bundle(ROOT, args.out_dir.resolve(), refresh_lock=args.refresh_lock)
    print(f"Built {artifact} with {MCPB_PACKAGE}@{MCPB_VERSION}")


if __name__ == "__main__":
    main()
