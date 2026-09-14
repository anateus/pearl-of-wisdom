import importlib.metadata
import tomllib
from pathlib import Path

from pearl_of_wisdom_viz import __version__

ROOT = Path(__file__).parents[1]


def test_companion_metadata_keeps_backends_out_of_core_package() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]

    assert project["name"] == "pearl-of-wisdom-viz"
    assert project["version"] == __version__ == "0.1.0"
    assert project["scripts"] == {"pearl-of-wisdom-viz": "pearl_of_wisdom_viz.cli:main"}
    assert "matplotlib" not in " ".join(project["dependencies"]).lower()
    assert project["optional-dependencies"]["matplotlib"] == ["matplotlib==3.11.2"]


def test_locked_runtime_versions_match_renderer_descriptor() -> None:
    assert importlib.metadata.version("arviz-base") == "1.3.0"
    assert importlib.metadata.version("arviz-plots") == "1.3.1"
    assert importlib.metadata.version("bokeh") == "3.10.0"
