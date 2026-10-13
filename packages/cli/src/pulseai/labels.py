"""Enums whose values readers see, as the schemas declare them.

A schema marks such an enum with `x-pulse-label` (the locale key prefix: value `v` reads
`<prefix>.<v lowercased>`) and, when each value also has a color, `x-pulse-tone` (the token
prefix: `<prefix>.<v lowercased>`). Instance schemas declare their own enums the same way, so
`pulse registry check` and `pulse tokens check` cover them too.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from pulseai.schemas import ITEM_TYPE_SCHEMA_DIR, SCHEMA_PROBLEMS, load_schema

LABEL_KEYWORD = "x-pulse-label"
TONE_KEYWORD = "x-pulse-tone"
# The engine schemas whose enums the frame shows; item-type schemas come from the registry.
FRAME_SCHEMAS = ("report.schema.json", "config.schema.json")


@dataclass(frozen=True)
class LabelledEnum:
    where: str
    label: str
    tone: str | None
    values: tuple[str, ...]

    def label_key(self, value: str) -> str:
        return f"{self.label}.{value.lower()}"

    def tone_token(self, value: str) -> str | None:
        return None if self.tone is None else f"{self.tone}.{value.lower()}"


def _escape(key: str) -> str:
    # JSON Pointer (RFC 6901) escaping.
    return key.replace("~", "~0").replace("/", "~1")


def _walk(node: Any, pointer: str) -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(node, dict):
        mapping = cast("dict[str, Any]", node)
        yield pointer, mapping
        for key, value in mapping.items():
            yield from _walk(value, f"{pointer}/{_escape(key)}")
    elif isinstance(node, list):
        for index, value in enumerate(cast("list[Any]", node)):
            yield from _walk(value, f"{pointer}/{index}")


def schema_enums(name: str, schema: dict[str, Any]) -> Iterator[LabelledEnum]:
    """The labelled enums in one schema, located as `<name>#<JSON pointer>`."""
    for pointer, node in _walk(schema, ""):
        label = node.get(LABEL_KEYWORD)
        values = node.get("enum")
        if isinstance(label, str) and isinstance(values, list):
            tone = node.get(TONE_KEYWORD)
            yield LabelledEnum(
                where=f"{name}#{pointer}",
                label=label,
                tone=tone if isinstance(tone, str) else None,
                values=tuple(str(value) for value in cast("list[Any]", values)),
            )


def labelled_enums(
    item_types: list[dict[str, Any]], instance_dir: Path | None = None
) -> Iterator[LabelledEnum]:
    """Labelled enums in the frame's schemas and in every item type's schema.

    A schema that fails to load is skipped: the registry check reports it on its own.
    """
    names = [*FRAME_SCHEMAS, *(f"{ITEM_TYPE_SCHEMA_DIR}/{t['schema']}" for t in item_types)]
    for name in dict.fromkeys(names):
        try:
            schema = load_schema(name, instance_dir)
        except SCHEMA_PROBLEMS:
            continue
        yield from schema_enums(name, schema)
