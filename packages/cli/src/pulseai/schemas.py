"""Load JSON Schemas (engine or instance) and validate documents against them."""

from __future__ import annotations

import json
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Any, Protocol, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import (
    SchemaError,
    ValidationError,
    best_match,  # pyright: ignore[reportUnknownVariableType]
)
from jsonschema.protocols import Validator
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

from pulseai.paths import data_path

SCHEMA_DIR = "schema"
ITEM_TYPE_SCHEMA_DIR = "item-types"


class SchemaNotFoundError(FileNotFoundError):
    """No schema with this name exists in the instance or the engine."""


class SchemaShapeError(ValueError):
    """A schema file is valid JSON Schema but not an object (for example a bare `true`)."""


class SchemaReadError(ValueError):
    """A schema file exists but cannot be read (permissions, a directory, and so on)."""


class SchemaRefError(ValueError):
    """A schema has a `$ref` that does not resolve."""


# What loading or applying a schema can raise; none of it is a bug in PulseAI.
SCHEMA_PROBLEMS = (SchemaNotFoundError, ValueError, SchemaError)


def schema_file(name: str, instance_dir: Path | None = None) -> Path:
    candidates = [instance_dir / SCHEMA_DIR / name] if instance_dir else []
    candidates.append(data_path(SCHEMA_DIR, name))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    searched = ", ".join(str(c.parent) for c in candidates)
    msg = f"schema {name!r} not found in {searched}"
    raise SchemaNotFoundError(msg)


@cache
def _validator(path: Path) -> Validator:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"cannot read ({exc.strerror or type(exc).__name__})"
        raise SchemaReadError(msg) from None
    schema: Any = json.loads(text)
    Draft202012Validator.check_schema(schema)
    check_references(schema)
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def clear_schema_cache() -> None:
    _validator.cache_clear()


def load_schema(name: str, instance_dir: Path | None = None) -> dict[str, Any]:
    path = schema_file(name, instance_dir)
    schema = _validator(path).schema
    if not isinstance(schema, dict):
        msg = f"schema {name!r} ({path}) must be a JSON object"
        raise SchemaShapeError(msg)
    return schema


def _pointer(error: ValidationError) -> str:
    return "/".join(str(part) for part in error.absolute_path) or "<root>"


def validate_document(data: Any, schema_name: str, instance_dir: Path | None = None) -> list[str]:
    """Return sorted '<path>: <message>' strings; empty when the document is valid."""
    validator = _validator(schema_file(schema_name, instance_dir))
    messages: set[str] = set()
    try:
        for error in validator.iter_errors(data):
            detail = cast("ValidationError", best_match(error.context)) if error.context else error
            messages.add(f"{_pointer(detail)}: {detail.message}")
    except Unresolvable as exc:
        raise SchemaRefError(_unresolvable_message(exc.ref)) from None
    return sorted(messages)


def _unresolvable_message(ref: str) -> str:
    return f"unresolvable $ref {ref!r}"


class _Resolver(Protocol):
    """The part of referencing's Resolver (not exported by the package) that is used here."""

    def in_subresource(self, subresource: Resource[Any]) -> _Resolver: ...

    def lookup(self, ref: str) -> object: ...


def _refs(node: Any, resolver: _Resolver) -> Iterator[str]:
    """Yield every `$ref` under `node` that its resolver cannot resolve."""
    if isinstance(node, list):
        for child in cast("list[Any]", node):
            yield from _refs(child, resolver)
    elif isinstance(node, dict):
        mapping = cast("dict[str, Any]", node)
        resolver = resolver.in_subresource(DRAFT202012.create_resource(mapping))
        ref = mapping.get("$ref")
        if isinstance(ref, str):
            try:
                resolver.lookup(ref)
            except Unresolvable:
                yield ref
        for child in mapping.values():
            yield from _refs(child, resolver)


def check_references(schema: Any) -> None:
    """Raise SchemaRefError when a `$ref` in `schema` does not resolve within the document.

    jsonschema resolves references lazily, so a dangling one only fails when an instance reaches
    it. Remote documents are never fetched; only the draft's own metaschema is known besides the
    document itself.
    """
    meta = Draft202012Validator.META_SCHEMA
    registry = Registry[Any]().with_resource(
        str(meta["$id"]), Resource.from_contents(meta, default_specification=DRAFT202012)
    )
    root = Resource.from_contents(schema, default_specification=DRAFT202012)
    missing = sorted(set(_refs(schema, registry.resolver_with_root(root))))
    if missing:
        raise SchemaRefError(", ".join(_unresolvable_message(ref) for ref in missing))
