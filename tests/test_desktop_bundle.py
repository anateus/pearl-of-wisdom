"""Packaging contract checks, including an actual official MCPB build."""

from __future__ import annotations

import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "desktop_builder", ROOT / "scripts/build_desktop_bundle.py"
)
assert SPEC is not None and SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)
TOOL_NAMES = {
    "pearl_status",
    "pearl_analyze",
    "pearl_example",
    "pearl_create_investigation",
    "pearl_list_investigations",
    "pearl_show_investigation",
    "pearl_record",
    "pearl_promote_investigation",
}


@pytest.fixture(scope="module")
def artifact(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("desktop output with spaces")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_desktop_bundle.py"), "--out-dir", str(out)],
        cwd=out,
        check=True,
    )
    return out / "pearl-of-wisdom-0.4.0.mcpb"


def test_manifest_paths_and_launch_contract() -> None:
    manifest = json.loads((ROOT / "desktop/manifest.json").read_text())
    assert manifest["manifest_version"] == "0.4"
    assert manifest["server"] == {
        "type": "uv",
        "entry_point": "server.py",
        "mcp_config": {
            "command": "uv",
            "args": ["run", "--directory", "${__dirname}", "--locked", "server.py"],
            "env": {"PEARL_DB": "${user_config.data_directory}/pearl.sqlite3"},
        },
    }
    data = manifest["user_config"]["data_directory"]
    assert data["type"] == "directory"
    assert data["required"] is True
    assert data["default"] == "${HOME}/.pearl-of-wisdom"
    assert {tool["name"] for tool in manifest["tools"]} == TOOL_NAMES


def test_versions_and_local_source() -> None:
    root = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    project = tomllib.loads((ROOT / "desktop/pyproject.toml").read_text())
    manifest = json.loads((ROOT / "desktop/manifest.json").read_text())
    assert root["version"] == project["project"]["version"] == manifest["version"] == "0.4.0"
    assert root["dependencies"] == []
    assert project["project"]["dependencies"] == ["mcp>=2,<3", "pearl-of-wisdom==0.4.0"]
    assert project["tool"]["uv"]["sources"]["pearl-of-wisdom"] == {
        "path": "wheels/pearl_of_wisdom-0.4.0-py3-none-any.whl"
    }
    lock = tomllib.loads((ROOT / "desktop/uv.lock").read_text())
    core = next(package for package in lock["package"] if package["name"] == "pearl-of-wisdom")
    assert core["source"] == {"path": "wheels/pearl_of_wisdom-0.4.0-py3-none-any.whl"}
    mcp = next(package for package in lock["package"] if package["name"] == "mcp")
    assert mcp["version"].startswith("2.")
    assert BUILDER.MCPB_COMMAND == ["npx", "--yes", "@anthropic-ai/mcpb@2.1.2"]


def test_actual_artifact_allowlist_and_no_private_paths(artifact: Path) -> None:
    with zipfile.ZipFile(artifact) as archive:
        names = {name for name in archive.namelist() if not name.endswith("/")}
        expected = {
            "manifest.json",
            "server.py",
            "pyproject.toml",
            "uv.lock",
            "LICENSE",
            "pearl.png",
            "wheels/pearl_of_wisdom-0.4.0-py3-none-any.whl",
        }
        assert expected <= names <= expected | {".mcpbignore"}
        assert archive.read("uv.lock") == (ROOT / "desktop/uv.lock").read_bytes()
        for name in ("manifest.json", "server.py", "pyproject.toml", "uv.lock"):
            data = archive.read(name)
            assert b"/Users/" not in data
            assert b"file://" not in data
            assert b"initial_base" not in data
        wheel = archive.read("wheels/pearl_of_wisdom-0.4.0-py3-none-any.whl")
        assert (
            wheel
            == (
                ROOT / "plugins/pearl-of-wisdom/cli/pearl_of_wisdom-0.4.0-py3-none-any.whl"
            ).read_bytes()
        )
        with zipfile.ZipFile(io.BytesIO(wheel)) as core:
            assert all(
                name.startswith(("pearl_of_wisdom/", "pearl_of_wisdom-0.4.0.dist-info/"))
                for name in core.namelist()
            )


@pytest.fixture
def synthetic_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "desktop").mkdir(parents=True)
    for name in (*BUILDER.TEMPLATE_FILES, "uv.lock"):
        shutil.copyfile(ROOT / "desktop" / name, root / "desktop" / name)
    for name in ("LICENSE", "pearl.png", "pyproject.toml"):
        shutil.copyfile(ROOT / name, root / name)
    wheel_dir = root / "plugins/pearl-of-wisdom/cli"
    wheel_dir.mkdir(parents=True)
    shutil.copyfile(
        ROOT / "plugins/pearl-of-wisdom/cli/pearl_of_wisdom-0.4.0-py3-none-any.whl",
        wheel_dir / "pearl_of_wisdom-0.4.0-py3-none-any.whl",
    )
    return root


def test_staging_excludes_planted_private_inputs(synthetic_root: Path, tmp_path: Path) -> None:
    marker = "PACKAGING_PRIVATE_SENTINEL"
    for name in (".env", "initial_base.md", "customer-transcript.json", "pearl.sqlite3"):
        (synthetic_root / "desktop" / name).write_text(marker)
        (synthetic_root / name).write_text(marker)
    (synthetic_root / "desktop/.venv").mkdir()
    (synthetic_root / "desktop/.venv/private.txt").write_text(marker)
    staging = tmp_path / "staging"
    staging.mkdir()
    BUILDER.stage_bundle(synthetic_root, staging)
    assert not any(
        marker.encode() in path.read_bytes() for path in staging.rglob("*") if path.is_file()
    )
    assert not (staging / ".venv").exists()


def test_version_mismatch_is_rejected(synthetic_root: Path, tmp_path: Path) -> None:
    manifest = synthetic_root / "desktop/manifest.json"
    data = json.loads(manifest.read_text())
    data["version"] = "9.0.0"
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="versions must match"):
        BUILDER.stage_bundle(synthetic_root, tmp_path)


def test_private_wheel_member_is_rejected(synthetic_root: Path, tmp_path: Path) -> None:
    wheel = synthetic_root / "plugins/pearl-of-wisdom/cli/pearl_of_wisdom-0.4.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr("pearl_of_wisdom/private-transcript.json", "PRIVATE_SENTINEL")
    with pytest.raises(ValueError, match="Unexpected core runtime file"):
        BUILDER.stage_bundle(synthetic_root, tmp_path)


def test_private_wheel_metadata_is_rejected(synthetic_root: Path, tmp_path: Path) -> None:
    wheel = synthetic_root / "plugins/pearl-of-wisdom/cli/pearl_of_wisdom-0.4.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr("pearl_of_wisdom-0.4.0.dist-info/private.txt", "PRIVATE_SENTINEL")
    with pytest.raises(ValueError, match="Unexpected wheel metadata file"):
        BUILDER.stage_bundle(synthetic_root, tmp_path)


def test_repository_source_is_rejected(synthetic_root: Path, tmp_path: Path) -> None:
    project = synthetic_root / "desktop/pyproject.toml"
    project.write_text(
        project.read_text().replace(
            "wheels/pearl_of_wisdom-0.4.0-py3-none-any.whl", "/private/repo/core.whl"
        )
    )
    with pytest.raises(ValueError, match="bundled local wheel"):
        BUILDER.stage_bundle(synthetic_root, tmp_path)
