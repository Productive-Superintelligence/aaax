from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any


def copy_boundary_value(value: Any) -> Any:
    """Return an owned copy of data crossing an AAAX boundary."""
    if isinstance(value, Mapping):
        return {key: copy_boundary_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [copy_boundary_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(copy_boundary_value(item) for item in value)
    if isinstance(value, set):
        return {copy_boundary_value(item) for item in value}
    if isinstance(value, frozenset):
        return frozenset(copy_boundary_value(item) for item in value)
    return copy.deepcopy(value)


def copy_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    return copy_boundary_value(value)
