"""Validate the committed plugin archive used when coworkers cannot fetch the repo."""

from __future__ import annotations

import json
import re
import stat
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).parents[1]
PLUGIN_TREE = "HEAD:plugins/pearl-of-wisdom"


def test_committed_plugin_archive_meets_upload_structure(tmp_path: Path) -> None:
    artifact = tmp_path / "pearl-of-wisdom-0.4.0.plugin"
    subprocess.run(
        ["git", "archive", "--format=zip", PLUGIN_TREE, f"--output={artifact}"],
        cwd=ROOT,
        check=True,
    )
    expected = set(
        subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", PLUGIN_TREE], cwd=ROOT, text=True
        ).splitlines()
    )
    with zipfile.ZipFile(artifact) as archive:
        files = [item for item in archive.infolist() if not item.is_dir()]
        assert {item.filename for item in files} == expected
        assert archive.testzip() is None
        assert len(files) < 5_000
        assert sum(item.file_size for item in files) < 200 * 1024 * 1024
        assert [
            item.filename for item in files if item.filename.endswith(".claude-plugin/plugin.json")
        ] == [".claude-plugin/plugin.json"]
        for item in files:
            path = Path(item.filename)
            assert not path.is_absolute() and ".." not in path.parts
            assert re.fullmatch(r"[A-Za-z0-9_ .\-/(),]+", item.filename)
            assert len(path.parts) <= 12
            assert not stat.S_ISLNK(item.external_attr >> 16)
            assert not item.flag_bits & 1
            assert item.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
            assert not item.filename.endswith(".zip")
            assert not item.filename.startswith("bin/")
        manifest = json.loads(archive.read(".claude-plugin/plugin.json"))
        assert manifest["name"] == "pearl-of-wisdom"
        assert manifest["skills"] == "./skills/"
        for name in ("pearl-of-wisdom", "reasoning-under-uncertainty"):
            skill = archive.read(f"skills/{name}/SKILL.md").decode()
            assert "pearl_status" in skill
            assert "pearl_analyze" in skill
            assert "Do not offer the Code CLI as an ordinary Chat solution" in skill
