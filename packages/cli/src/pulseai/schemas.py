"""Load JSON Schemas (engine or instance) and validate documents against them."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import (
    ValidationError,
    best_match,  # pyright: ignore[reportUnknownVariableType]
)
from jsonschema.protocols import Validator

from pulseai.paths import data_path

SCHEMA_DIR = "schema"


class SchemaNotFoundError(FileNotFoundError):
    """No schema with this name exists in the instance or the engine."""


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
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def clear_schema_cache() -> None:
    _validator.cache_clear()


def load_schema(name: str, instance_dir: Path | None = None) -> dict[str, Any]:
    return cast("dict[str, Any]", _validator(schema_file(name, instance_dir)).schema)


def _pointer(error: ValidationError) -> str:
    return "/".join(str(part) for part in error.absolute_path) or "<root>"


def validate_document(data: Any, schema_name: str, instance_dir: Path | None = None) -> list[str]:
    """Return sorted '<path>: <message>' strings; empty when the document is valid."""
    validator = _validator(schema_file(schema_name, instance_dir))
    messages: set[str] = set()
    for error in validator.iter_errors(data):
        detail = cast("ValidationError", best_match(error.context)) if error.context else error
        messages.add(f"{_pointer(detail)}: {detail.message}")
    return sorted(messages)
