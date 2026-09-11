"""Shared contracts for probabilistic analysis engines."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]


def _json_copy(value: object, path: str = "value") -> JsonValue:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must contain finite JSON numbers")
        return value
    if isinstance(value, list | tuple):
        return [_json_copy(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, Mapping):
        copied: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} must contain only string JSON object keys")
            copied[key] = _json_copy(item, f"{path}.{key}")
        return copied
    raise TypeError(f"{path} contains a non-JSON value: {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """A transport-neutral result containing only strict JSON-compatible values."""

    engine: str
    capabilities: tuple[str, ...]
    data: dict[str, JsonValue]
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.engine, str) or not self.engine.strip():
            raise ValueError("engine must be a non-empty string")
        if any(
            not isinstance(capability, str) or not capability for capability in self.capabilities
        ):
            raise ValueError("capabilities must contain non-empty strings")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("capabilities must be unique")
        data = _json_copy(self.data, "data")
        metadata = _json_copy(self.metadata, "metadata")
        if not isinstance(data, dict) or not isinstance(metadata, dict):
            raise TypeError("data and metadata must be JSON objects")
        object.__setattr__(self, "data", data)
        object.__setattr__(self, "metadata", metadata)

    def to_dict(self) -> dict[str, JsonValue]:
        """Return a detached, JSON-compatible representation."""

        return {
            "engine": self.engine,
            "capabilities": list(self.capabilities),
            "data": _json_copy(self.data, "data"),
            "metadata": _json_copy(self.metadata, "metadata"),
        }


@runtime_checkable
class AnalysisEngine(Protocol):
    """Small capability-based interface shared by all engines."""

    name: str
    capabilities: tuple[str, ...]

    def supports(self, capability: str) -> bool:
        """Return whether the engine advertises an exact capability identifier."""

        ...

    def analyze(self, request: Mapping[str, object]) -> AnalysisResult:
        """Validate and analyze a JSON-compatible request."""

        ...
