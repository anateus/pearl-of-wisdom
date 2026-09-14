from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from pearl_of_wisdom_viz.assets import publish_shared_assets
from pearl_of_wisdom_viz.model import VisualizationError


def test_shared_assets_publish_immutably_into_paths_with_spaces(tmp_path: Path) -> None:
    base = tmp_path / "shared assets"

    published = publish_shared_assets(base)

    assert published.location.parent == base.resolve()
    assert published.location.name.startswith("bokeh-3.10.0-")
    assert len(published.identity) == 64
    assert published.javascript.is_file()
    assert "Copyright" in published.javascript.read_text()[:1000]
    assert published.javascript.as_uri() in published.resource_html


def test_concurrent_shared_asset_publishers_resolve_to_same_verified_bundle(
    tmp_path: Path,
) -> None:
    base = tmp_path / "assets"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: publish_shared_assets(base), range(8)))

    assert len({result.identity for result in results}) == 1
    assert len({result.location for result in results}) == 1
    assert len(list(base.iterdir())) == 1


def test_existing_shared_asset_is_verified_and_never_overwritten(tmp_path: Path) -> None:
    published = publish_shared_assets(tmp_path)
    published.javascript.write_text("tampered")

    with pytest.raises(VisualizationError, match="hash mismatch"):
        publish_shared_assets(tmp_path)

    assert published.javascript.read_text() == "tampered"
