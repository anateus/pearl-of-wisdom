"""Immutable shared browser assets for compact offline HTML."""

from __future__ import annotations

import hashlib
import html
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from bokeh import __version__ as bokeh_version
from bokeh.resources import Resources

from .model import VisualizationError


@dataclass(frozen=True, slots=True)
class SharedAssets:
    identity: str
    location: Path
    javascript: Path
    resource_html: str


def _default_base() -> Path:
    configured = os.environ.get("PEARL_VIZ_ASSETS_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    data_home = os.environ.get("XDG_DATA_HOME")
    root = Path(data_home).expanduser() if data_home else Path.home() / ".local" / "share"
    return (root / "pearl-of-wisdom" / "viz" / "assets").resolve()


def _source_bundle() -> tuple[Path, bytes, str]:
    resources = Resources(mode="absolute", components=["bokeh"])
    if len(resources.js_files) != 1:
        raise VisualizationError("installed Bokeh distribution has an unexpected asset bundle")
    source = Path(resources.js_files[0])
    try:
        content = source.read_bytes()
    except OSError as error:
        raise VisualizationError(f"cannot read installed Bokeh asset: {error.strerror}") from error
    digest = hashlib.sha256(source.name.encode() + b"\0" + content).hexdigest()
    return source, content, digest


def _verify(location: Path, *, filename: str, digest: str, file_hash: str) -> None:
    manifest_path = location / "manifest.json"
    javascript = location / filename
    try:
        manifest = json.loads(manifest_path.read_text())
        actual_hash = hashlib.sha256(javascript.read_bytes()).hexdigest()
        entries = {path.name for path in location.iterdir()}
    except (OSError, json.JSONDecodeError) as error:
        raise VisualizationError(f"shared asset directory is incomplete: {location}") from error
    expected = {
        "bokeh_version": bokeh_version,
        "bundle_sha256": digest,
        "files": {filename: file_hash},
    }
    if manifest != expected or entries != {filename, "manifest.json"}:
        raise VisualizationError(f"shared asset manifest conflicts with bundle: {location}")
    if actual_hash != file_hash:
        raise VisualizationError(f"shared asset hash mismatch; refusing to overwrite {javascript}")


def publish_shared_assets(base_directory: Path | str | None = None) -> SharedAssets:
    source, content, digest = _source_bundle()
    file_hash = hashlib.sha256(content).hexdigest()
    base = Path(base_directory).expanduser().resolve() if base_directory else _default_base()
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise VisualizationError(
            f"cannot create shared asset directory: {error.strerror}"
        ) from error
    location = base / f"bokeh-{bokeh_version}-{digest}"
    if location.exists():
        _verify(location, filename=source.name, digest=digest, file_hash=file_hash)
    else:
        temporary = Path(tempfile.mkdtemp(dir=base, prefix=".publish-"))
        try:
            javascript = temporary / source.name
            with javascript.open("wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            manifest = {
                "bokeh_version": bokeh_version,
                "bundle_sha256": digest,
                "files": {source.name: file_hash},
            }
            (temporary / "manifest.json").write_text(
                json.dumps(manifest, separators=(",", ":"), sort_keys=True)
            )
            try:
                temporary.rename(location)
            except OSError:
                if not location.exists():
                    raise
                shutil.rmtree(temporary)
            _verify(location, filename=source.name, digest=digest, file_hash=file_hash)
        except VisualizationError:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise
        except OSError as error:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise VisualizationError(
                f"cannot publish shared Bokeh assets: {error.strerror}"
            ) from error
    javascript = location / source.name
    source_url = html.escape(javascript.as_uri(), quote=True)
    resource_html = (
        f'<script src="{source_url}" '
        'onerror="document.getElementById(\'pearl-shared-error\').hidden=false"></script>'
    )
    return SharedAssets(digest, location, javascript, resource_html)
