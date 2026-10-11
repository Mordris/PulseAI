"""Generic deep merge for registry and config documents.

Rules:
- mappings merge key by key, recursively;
- lists whose items are all mappings with an ``id`` merge by id (base order kept, new ids appended);
  an override item with ``_remove: true`` deletes the base item with that id, and an id added
  again after its removal goes to the end;
- duplicate ids inside one base list collapse to a single entry holding the last occurrence;
- every other value (scalars, plain lists, empty lists) is replaced by the override;
- ``_remove`` keys never appear in a result (whatever their value), items marked ``_remove: true``
  are dropped wherever they occur, and a result never shares mutable objects with its inputs.
"""

from __future__ import annotations

import copy
from typing import Any, cast

REMOVE_KEY = "_remove"
ID_KEY = "id"


def _as_dict(value: Any) -> dict[str, Any] | None:
    return cast("dict[str, Any]", value) if isinstance(value, dict) else None


def _as_list(value: Any) -> list[Any] | None:
    return cast("list[Any]", value) if isinstance(value, list) else None


def _is_removed(item: Any) -> bool:
    mapping = _as_dict(item)
    return mapping is not None and mapping.get(REMOVE_KEY) is True


def _is_id_list(value: Any) -> bool:
    items = _as_list(value)
    return (
        items is not None
        and len(items) > 0
        and all(isinstance(item, dict) and ID_KEY in item for item in items)
    )


def _clean(value: Any) -> Any:
    """Deep copy of ``value`` without ``_remove`` keys or items marked ``_remove: true``."""
    mapping = _as_dict(value)
    if mapping is not None:
        return {k: _clean(v) for k, v in mapping.items() if k != REMOVE_KEY}
    items = _as_list(value)
    if items is not None:
        return [_clean(item) for item in items if not _is_removed(item)]
    return copy.deepcopy(value)


def _merge_by_id(base: list[Any], override: list[Any]) -> list[Any]:
    merged: dict[str, Any] = {}
    for item in _clean(base):
        merged[str(item[ID_KEY])] = item
    for item in override:
        key = str(item[ID_KEY])
        if item.get(REMOVE_KEY) is True:
            merged.pop(key, None)
        elif key in merged:
            merged[key] = merge(merged[key], item)
        else:
            merged[key] = _clean(item)
    return list(merged.values())


def merge(base: Any, override: Any) -> Any:
    """Return a new document with ``override`` merged over ``base``; inputs are not mutated."""
    base_map, override_map = _as_dict(base), _as_dict(override)
    if base_map is not None and override_map is not None:
        result: dict[str, Any] = _clean(base_map)
        for key, value in override_map.items():
            if key == REMOVE_KEY:
                continue
            result[key] = merge(base_map[key], value) if key in base_map else _clean(value)
        return result
    if _is_id_list(base) and _is_id_list(override):
        return _merge_by_id(base, override)
    return _clean(override)
