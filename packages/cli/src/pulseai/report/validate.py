"""Validate report.json: JSON Schema, item-type detail schemas, and cross-reference rules."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from pulseai.config import ConfigError, load_config
from pulseai.issues import Issue
from pulseai.models.config import PulseConfig
from pulseai.registry.loader import RegistryError, load_registry
from pulseai.schemas import (
    ITEM_TYPE_SCHEMA_DIR,
    SchemaNotFoundError,
    SchemaShapeError,
    validate_document,
)

REPORT_SCHEMA = "report.schema.json"
PRIMARY_TIERS = frozenset({"T1", "T1-data"})
VEGA_LITE_KIND = "vega-lite"
TABLE_KIND = "table"


@dataclass(frozen=True)
class _Context:
    cfg: PulseConfig
    instance_dir: Path | None
    section_ids: set[str]
    item_types: dict[str, dict[str, Any]]
    featured_slots: dict[str, dict[str, Any]]


def _error(where: str, message: str) -> Issue:
    return Issue("error", where, message)


def _items(report: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for key in ("items", "signals"):
        for index, item in enumerate(report[key]):
            yield f"{key}/{index}", item


def _visuals(report: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for index, visual in enumerate(report["front_page"]):
        yield f"front_page/{index}", visual
    for where, item in _items(report):
        for index, visual in enumerate(item["visuals"]):
            yield f"{where}/visuals/{index}", visual


def _remote_data(node: Any, path: str) -> str | None:
    if isinstance(node, dict):
        mapping = cast("dict[str, Any]", node)
        data = mapping.get("data")
        if isinstance(data, dict) and "url" in data:
            return f"{path}/data/url"
        for key, value in mapping.items():
            found = _remote_data(value, f"{path}/{key}")
            if found:
                return found
    elif isinstance(node, list):
        for index, value in enumerate(cast("list[Any]", node)):
            found = _remote_data(value, f"{path}/{index}")
            if found:
                return found
    return None


def _check_registry_refs(report: dict[str, Any], ctx: _Context) -> Iterator[Issue]:
    for where, item in _items(report):
        if item["section"] not in ctx.section_ids:
            yield _error(f"{where}/section", f"unknown section {item['section']!r}")
        item_type = ctx.item_types.get(item["type"])
        if item_type is None:
            yield _error(f"{where}/type", f"unknown item type {item['type']!r}")
            continue
        schema = f"{ITEM_TYPE_SCHEMA_DIR}/{item_type['schema']}"
        try:
            messages = validate_document(item["detail"], schema, ctx.instance_dir)
        except (SchemaNotFoundError, SchemaShapeError) as exc:
            messages = [str(exc)]
        for message in messages:
            yield _error(f"{where}/detail", message)


def _check_unique_ids(report: dict[str, Any]) -> Iterator[Issue]:
    item_ids = Counter(item["id"] for _, item in _items(report))
    for item_id, count in sorted(item_ids.items()):
        if count > 1:
            yield _error("items", f"duplicate item id {item_id!r}")
    visual_ids = Counter(visual["id"] for _, visual in _visuals(report))
    for visual_id, count in sorted(visual_ids.items()):
        if count > 1:
            yield _error("visuals", f"duplicate visual id {visual_id!r}")


def _check_references(report: dict[str, Any]) -> Iterator[Issue]:
    known = {item["id"] for _, item in _items(report)}
    for key in ("tldr", "adoption_radar", "action_list"):
        for index, entry in enumerate(report[key]):
            ref = entry.get("item_id")
            if ref is not None and ref not in known:
                yield _error(f"{key}/{index}/item_id", f"unknown item {ref!r}")


def _check_sources(report: dict[str, Any]) -> Iterator[Issue]:
    for where, item in _items(report):
        sources = item["sources"]
        has_primary = any(s["kind"] == "primary" and s["tier"] in PRIMARY_TIERS for s in sources)
        if item["confidence"] == "confirmed" and not has_primary:
            yield _error(where, "confirmed items need a primary T1 or T1-data source")
        for index, fact in enumerate(item["facts"]):
            if fact["source_ref"] >= len(sources):
                yield _error(
                    f"{where}/facts/{index}/source_ref",
                    f"{fact['source_ref']} points past the {len(sources)} sources",
                )


def _check_confidence_routing(report: dict[str, Any], ctx: _Context) -> Iterator[Issue]:
    reported, rumor = ctx.cfg.confidence.reported, ctx.cfg.confidence.rumor
    for index, item in enumerate(report["items"]):
        where = f"items/{index}"
        if item["confidence"] == "rumor":
            yield _error(where, "rumors never go in items")
        elif item["confidence"] == "reported" and reported == "signals_box":
            yield _error(where, "reported items go in signals (confidence.reported = signals_box)")
        elif item["confidence"] == "reported" and reported == "exclude":
            yield _error(where, "reported items are excluded (confidence.reported = exclude)")
    for index, item in enumerate(report["signals"]):
        where = f"signals/{index}"
        if item["confidence"] == "confirmed":
            yield _error(where, "confirmed items belong in items, not signals")
        elif item["confidence"] == "rumor" and rumor == "exclude":
            yield _error(where, "rumors are excluded (confidence.rumor = exclude)")
        elif item["confidence"] == "reported" and reported == "exclude":
            yield _error(where, "reported items are excluded (confidence.reported = exclude)")


def _check_featured(report: dict[str, Any], ctx: _Context) -> Iterator[Issue]:
    by_id = {item["id"]: item for _, item in _items(report)}
    for slot, item_id in report["featured"].items():
        where = f"featured/{slot}"
        group = ctx.featured_slots.get(slot)
        if group is None:
            yield _error(where, "no section group declares this featured slot")
            continue
        item = by_id.get(item_id)
        if item is None:
            yield _error(where, f"unknown item {item_id!r}")
            continue
        types = group["match"].get("types")
        if types and item["type"] not in types:
            yield _error(where, f"item {item_id!r} has type {item['type']!r}; slot accepts {types}")
        if item["section"] != group["section"]:
            yield _error(where, f"item {item_id!r} is not in section {group['section']!r}")


def _check_visuals(report: dict[str, Any]) -> Iterator[Issue]:
    for where, visual in _visuals(report):
        if visual["kind"] == VEGA_LITE_KIND:
            remote = _remote_data(visual["spec"], "spec")
            if remote:
                yield _error(
                    where, f"remote chart data ({remote}) is not allowed; embed data.values"
                )
        elif visual["kind"] == TABLE_KIND:
            width = len(visual["columns"])
            for index, row in enumerate(visual["rows"]):
                if len(row) != width:
                    yield _error(f"{where}/rows/{index}", f"{len(row)} cells, expected {width}")


def _check_section_config(report: dict[str, Any], ctx: _Context) -> Iterator[Issue]:
    counts = Counter(item["section"] for item in report["items"])
    for section_id, count in sorted(counts.items()):
        toggle = ctx.cfg.sections.get(section_id)
        if toggle is None or not toggle.enabled:
            yield _error("items", f"section {section_id!r} is disabled but has {count} items")
        elif count > toggle.max_items:
            yield Issue(
                "warning",
                "items",
                f"section {section_id!r} has {count} items; max_items is {toggle.max_items}",
            )


def _context(instance_dir: Path | None) -> _Context:
    cfg = load_config(instance_dir)
    sections = load_registry("sections", instance_dir).data["sections"]
    item_types = load_registry("item-types", instance_dir).data["item_types"]
    slots: dict[str, dict[str, Any]] = {}
    for section in sections:
        for group in section["groups"]:
            featured = group["match"].get("featured")
            if featured:
                slots[featured] = {**group, "section": section["id"]}
    return _Context(
        cfg=cfg,
        instance_dir=instance_dir,
        section_ids={s["id"] for s in sections},
        item_types={t["id"]: t for t in item_types},
        featured_slots=slots,
    )


def validate_report(data: Any, instance_dir: Path | None = None) -> list[Issue]:
    """All problems with a report; schema problems stop further checks."""
    schema_errors = validate_document(data, REPORT_SCHEMA)
    if schema_errors:
        return [_error("schema", message) for message in schema_errors]
    try:
        ctx = _context(instance_dir)
    except (ConfigError, RegistryError) as exc:
        return [_error("load", str(exc))]
    report: dict[str, Any] = data
    issues = [
        *_check_registry_refs(report, ctx),
        *_check_unique_ids(report),
        *_check_references(report),
        *_check_sources(report),
        *_check_confidence_routing(report, ctx),
        *_check_featured(report, ctx),
        *_check_visuals(report),
        *_check_section_config(report, ctx),
    ]
    return sorted(issues)


def validate_report_file(path: Path, instance_dir: Path | None = None) -> list[Issue]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return [_error("file", f"{path}: {exc}")]
    return validate_report(data, instance_dir)
