"""Canonical JSON serialization shared by Pearl's transport boundaries."""

from __future__ import annotations

import json
from typing import Any


def dumps_json(value: Any) -> str:
    """Serialize one strict, deterministic JSON value without a trailing newline."""

    return json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True)


def json_line_size(value: Any) -> int:
    """Return the UTF-8 size emitted by the line-oriented CLI transport."""

    return len(dumps_json(value).encode("utf-8")) + 1
