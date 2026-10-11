"""Load registries: engine defaults combined, instance overrides merged, result validated."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, cast

import yaml

from pulseai.models.registries import RegistriesCatalog, RegistrySpec
from pulseai.paths import data_path, engine_root
from pulseai.registry.merge import ID_KEY, merge
from pulseai.schemas import validate_document

CATALOG_PARTS = ("defaults", "registries.yaml")
CATALOG_SCHEMA = "registries.schema.json"
YAML_SUFFIXES = frozenset({".yaml", ".yml"})
GLOB_CHARS = frozenset("*?[")
UNSAFE_VARIABLE_PARTS = ("/", "\\", "..")
LOCALE_REGISTRY = "locale"
LOCALE_VARIABLE = "language"


class RegistryError(Exception):
    """A registry could not be loaded or is invalid."""


@dataclass(frozen=True)
class LoadedRegistry:
    id: str
    data: dict[str, Any]
    files: tuple[Path, ...]


def _bullets(lines: Sequence[str]) -> str:
    return "\n".join(f"  - {line}" for line in lines)


def read_document(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        msg = f"{path}: not valid UTF-8 ({exc.reason})"
        raise RegistryError(msg) from None
    except OSError as exc:
        msg = f"{path}: cannot read ({exc.strerror or type(exc).__name__})"
        raise RegistryError(msg) from None
    if not text.strip():
        msg = f"{path}: file is empty"
        raise RegistryError(msg)
    try:
        if path.suffix in YAML_SUFFIXES:
            return yaml.safe_load(text)
        if path.suffix == ".json":
            return json.loads(text)
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        msg = f"{path}: cannot parse ({exc})"
        raise RegistryError(msg) from None
    msg = f"{path}: unsupported file type {path.suffix!r}; use .yaml, .yml or .json"
    raise RegistryError(msg)


@cache
def load_catalog() -> RegistriesCatalog:
    path = data_path(*CATALOG_PARTS)
    doc = read_document(path)
    errors = validate_document(doc, CATALOG_SCHEMA)
    if errors:
        msg = f"{path}: invalid registry catalog\n{_bullets(errors)}"
        raise RegistryError(msg)
    return RegistriesCatalog.model_validate(doc)


def registry_spec(registry_id: str) -> RegistrySpec:
    catalog = load_catalog()
    for spec in catalog.registries:
        if spec.id == registry_id:
            return spec
    known = ", ".join(spec.id for spec in catalog.registries)
    msg = f"unknown registry {registry_id!r}; known: {known}"
    raise RegistryError(msg)


def _check_variables(variables: Mapping[str, str]) -> None:
    """Reject values that could widen a glob or climb out of the directory they are used in."""
    for name, value in variables.items():
        if GLOB_CHARS & set(value) or any(part in value for part in UNSAFE_VARIABLE_PARTS):
            msg = f"variable {name!r} has an unsafe value {value!r}"
            raise RegistryError(msg)


def _expand(root: Path, patterns: Sequence[str], variables: Mapping[str, str]) -> list[Path]:
    found: list[Path] = []
    for pattern in patterns:
        try:
            relative = pattern.format_map(variables)
        except KeyError as exc:
            msg = f"path {pattern!r} needs variable {exc.args[0]!r}"
            raise RegistryError(msg) from None
        except (ValueError, IndexError, AttributeError) as exc:
            msg = f"path {pattern!r} is not a valid template ({exc})"
            raise RegistryError(msg) from None
        if GLOB_CHARS & set(pattern):
            found.extend(sorted(p for p in root.glob(relative) if p.is_file()))
        elif (root / relative).is_file():
            found.append(root / relative)
    return found


def _require_mapping(doc: Any, path: Path) -> dict[str, Any]:
    if not isinstance(doc, dict):
        msg = f"{path}: top level must be a mapping"
        raise RegistryError(msg)
    return cast("dict[str, Any]", doc)


def _dict_items(doc: dict[str, Any], list_key: str) -> list[dict[str, Any]]:
    items: list[Any] = doc.get(list_key, [])
    return [cast("dict[str, Any]", item) for item in items if isinstance(item, dict)]


def _combine(
    acc: dict[str, Any] | None, doc: dict[str, Any], path: Path, list_key: str | None
) -> dict[str, Any]:
    if acc is None:
        return dict(doc)
    if list_key is None:
        combined: dict[str, Any] = merge(acc, doc)
        return combined
    existing = {item.get(ID_KEY) for item in _dict_items(acc, list_key)}
    for item in _dict_items(doc, list_key):
        if item.get(ID_KEY) in existing:
            msg = f"{path}: duplicate id {item.get(ID_KEY)!r} across engine registry files"
            raise RegistryError(msg)
    return {**acc, list_key: [*acc.get(list_key, []), *doc.get(list_key, [])]}


def load_registry(
    registry_id: str,
    instance_dir: Path | None = None,
    variables: Mapping[str, str] | None = None,
) -> LoadedRegistry:
    """Load one registry: combine engine files, merge instance overrides, validate the result."""
    spec = registry_spec(registry_id)
    values = dict(variables or {})
    _check_variables(values)
    engine_files = _expand(engine_root(), spec.paths, values)
    if not engine_files:
        msg = f"{registry_id}: no engine files match {', '.join(spec.paths)}"
        raise RegistryError(msg)

    data: dict[str, Any] | None = None
    for path in engine_files:
        data = _combine(data, _require_mapping(read_document(path), path), path, spec.list_key)

    instance_files: list[Path] = []
    if instance_dir is not None:
        instance_files = _expand(instance_dir, spec.instance_paths or spec.paths, values)
        for path in instance_files:
            data = merge(data, _require_mapping(read_document(path), path))

    if data is None:
        msg = f"{registry_id}: nothing was loaded"
        raise RegistryError(msg)
    files = (*engine_files, *instance_files)
    errors = validate_document(data, spec.schema_)
    if errors:
        sources = ", ".join(str(f) for f in files)
        msg = f"{registry_id} ({sources}): invalid after merging\n{_bullets(errors)}"
        raise RegistryError(msg)
    return LoadedRegistry(registry_id, data, files)


def load_locale(language: str, instance_dir: Path | None = None) -> dict[str, str]:
    """Strings for a language, with its fallback chain applied (fallback first, language last)."""
    chain: list[dict[str, str]] = []
    seen: list[str] = []
    current: str | None = language
    while current is not None:
        if current in seen:
            msg = f"locale fallback cycle: {' -> '.join([*seen, current])}"
            raise RegistryError(msg)
        seen.append(current)
        doc = load_registry(LOCALE_REGISTRY, instance_dir, {LOCALE_VARIABLE: current}).data
        chain.append(doc["strings"])
        current = doc["fallback"]
    strings: dict[str, str] = {}
    for layer in reversed(chain):
        strings.update(layer)
    return strings
