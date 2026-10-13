"""Validate report.json: JSON Schema, item-type detail schemas, and cross-reference rules."""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jsonschema.exceptions import SchemaError

from pulseai.config import ConfigError, load_config
from pulseai.issues import Issue, unusable_issue
from pulseai.models.config import PulseConfig
from pulseai.paths import EngineDataError
from pulseai.registry.loader import RegistryError, load_registry
from pulseai.schemas import (
    ITEM_TYPE_SCHEMA_DIR,
    SCHEMA_PROBLEMS,
    SchemaNotFoundError,
    schema_file,
    validate_document,
)

REPORT_SCHEMA = "report.schema.json"
VEGA_LITE_KIND = "vega-lite"
# Charts carry their data inline: no key may name a URL to load, except inside the inline rows,
# where a URL is just a value.
URL_KEY = "url"
INLINE_ROW_KEYS = frozenset({"values", "datasets"})
VEGA_LITE_SCHEMA_MARK = "/schema/vega-lite/"
TABLE_KIND = "table"
DASHBOARD_KIND = "dashboard"
VISUAL_TILE = "visual"


@dataclass(frozen=True)
class _Context:
    cfg: PulseConfig
    instance_dir: Path | None
    section_ids: set[str]
    section_groups: dict[str, set[str]]
    item_types: dict[str, dict[str, Any]]
    featured_slots: dict[str, dict[str, Any]]


def _error(where: str, message: str) -> Issue:
    return Issue("error", where, message)


def _items(report: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for key in ("items", "signals"):
        for index, item in enumerate(report[key]):
            yield f"{key}/{index}", item


def _with_nested(where: str, visual: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """A visual followed by the leaf visuals in its dashboard tiles, if it is a dashboard."""
    yield where, visual
    if visual["kind"] == DASHBOARD_KIND:
        for index, tile in enumerate(visual["tiles"]):
            if tile["tile"] == VISUAL_TILE:
                yield f"{where}/tiles/{index}/visual", tile["visual"]


def _visuals(report: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for index, visual in enumerate(report["front_page"]):
        yield from _with_nested(f"front_page/{index}", visual)
    for where, item in _items(report):
        for index, visual in enumerate(item["visuals"]):
            yield from _with_nested(f"{where}/visuals/{index}", visual)


def _remote_data(node: Any, path: str) -> str | None:
    """The first `url` a chart could load: data, images, anything outside the inline rows."""
    if isinstance(node, dict):
        mapping = cast("dict[str, Any]", node)
        for key, value in mapping.items():
            if key == URL_KEY:
                return f"{path}/{key}"
            if key in INLINE_ROW_KEYS:
                continue
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
        except SchemaNotFoundError as exc:
            messages = [str(exc)]
        except (ValueError, SchemaError) as exc:
            # ValueError covers JSONDecodeError, UnicodeDecodeError, and SchemaShapeError.
            problem = exc.message if isinstance(exc, SchemaError) else str(exc)
            path = schema_file(schema, ctx.instance_dir)
            messages = [f"{path}: invalid item-type schema ({problem})"]
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


def _unknown_item(report: dict[str, Any], ref: str) -> str:
    """Why `ref` is not a published item. References resolve against items, never signals."""
    if any(item["id"] == ref for item in report["signals"]):
        return f"item {ref!r} is a signal; references must point at a published item"
    return f"unknown item {ref!r}"


def _check_references(report: dict[str, Any]) -> Iterator[Issue]:
    published = {item["id"] for item in report["items"]}
    for key in ("tldr", "adoption_radar", "action_list"):
        for index, entry in enumerate(report[key]):
            ref = entry.get("item_id")
            if ref is not None and ref not in published:
                yield _error(f"{key}/{index}/item_id", _unknown_item(report, ref))


def _check_sources(report: dict[str, Any], ctx: _Context) -> Iterator[Issue]:
    tiers = ctx.cfg.quality.primary_tiers
    for where, item in _items(report):
        sources = item["sources"]
        has_primary = any(s["kind"] == "primary" and s["tier"] in tiers for s in sources)
        if item["confidence"] == "confirmed" and not has_primary:
            yield _error(
                where, f"confirmed items need a primary source of tier {' or '.join(tiers)}"
            )
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
        elif item["confidence"] == "reported" and reported == "main":
            yield _error(where, "reported items go in items (confidence.reported = main)")
        elif item["confidence"] == "reported" and reported == "exclude":
            yield _error(where, "reported items are excluded (confidence.reported = exclude)")


def _check_featured(report: dict[str, Any], ctx: _Context) -> Iterator[Issue]:
    by_id = {item["id"]: item for item in report["items"]}
    for slot, item_id in report["featured"].items():
        where = f"featured/{slot}"
        group = ctx.featured_slots.get(slot)
        if group is None:
            yield _error(where, "no section group declares this featured slot")
            continue
        item = by_id.get(item_id)
        if item is None:
            yield _error(where, _unknown_item(report, item_id))
            continue
        types = group["match"].get("types")
        if types and item["type"] not in types:
            yield _error(where, f"item {item_id!r} has type {item['type']!r}; slot accepts {types}")
        if item["section"] != group["section"]:
            yield _error(where, f"item {item_id!r} is not in section {group['section']!r}")


def _check_visuals(report: dict[str, Any]) -> Iterator[Issue]:
    for where, visual in _visuals(report):
        if visual["kind"] == VEGA_LITE_KIND:
            spec = visual["spec"]
            schema = spec.get("$schema")
            if schema is not None and VEGA_LITE_SCHEMA_MARK not in str(schema):
                yield _error(
                    f"{where}/spec/$schema",
                    f"{schema!r} is not a Vega-Lite schema; vega-lite visuals take Vega-Lite specs",
                )
            if "usermeta" in spec:
                yield _error(
                    f"{where}/spec/usermeta", "charts cannot carry embed options in usermeta"
                )
            remote = _remote_data(spec, "spec")
            if remote:
                yield _error(
                    where, f"remote chart data ({remote}) is not allowed; embed data.values"
                )
        elif visual["kind"] == TABLE_KIND:
            width = len(visual["columns"])
            for index, row in enumerate(visual["rows"]):
                if len(row) != width:
                    yield _error(f"{where}/rows/{index}", f"{len(row)} cells, expected {width}")


def _check_dashboard(where: str, visual: dict[str, Any]) -> Iterator[Issue]:
    for index, tile in enumerate(visual["tiles"]):
        span = tile.get("span", 1)
        if span > visual["columns"]:
            yield _error(
                f"{where}/tiles/{index}/span",
                f"span {span} is wider than the dashboard's {visual['columns']} columns",
            )
        if tile["tile"] == VISUAL_TILE and "block" in tile["visual"]:
            yield _error(
                f"{where}/tiles/{index}/visual/block",
                "visuals inside a dashboard cannot name a block",
            )


def _check_visual_placement(report: dict[str, Any], ctx: _Context) -> Iterator[Issue]:
    for index, visual in enumerate(report["front_page"]):
        where = f"front_page/{index}"
        if "block" in visual:
            yield _error(
                f"{where}/block",
                "front-page visuals are not in an item, so they cannot name a block",
            )
        if visual["kind"] == DASHBOARD_KIND:
            yield from _check_dashboard(where, visual)
    for item_where, item in _items(report):
        item_type = ctx.item_types.get(item["type"])
        for index, visual in enumerate(item["visuals"]):
            where = f"{item_where}/visuals/{index}"
            block = visual.get("block")
            # An unknown item type is reported by _check_registry_refs already.
            if block is not None and item_type is not None and block not in item_type["blocks"]:
                yield _error(
                    f"{where}/block",
                    f"block {block!r} is not one of the {item['type']!r} blocks: "
                    f"{', '.join(item_type['blocks'])}",
                )
            if visual["kind"] == DASHBOARD_KIND:
                yield from _check_dashboard(where, visual)


def _count(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _check_section_config(report: dict[str, Any], ctx: _Context) -> Iterator[Issue]:
    published = Counter(item["section"] for item in report["items"])
    signals = Counter(item["section"] for item in report["signals"])
    for section_id in sorted(published.keys() | signals.keys()):
        if section_id not in ctx.section_ids:
            continue  # reported as an unknown section already
        toggle = ctx.cfg.sections.get(section_id)
        if toggle is None or not toggle.enabled:
            parts = [
                _count(count, noun)
                for count, noun in (
                    (published[section_id], "item"),
                    (signals[section_id], "signal"),
                )
                if count
            ]
            where = "items" if published[section_id] else "signals"
            yield _error(where, f"section {section_id!r} is disabled but has {' and '.join(parts)}")
        elif published[section_id] > toggle.max_items:
            yield Issue(
                "warning",
                "items",
                f"section {section_id!r} has {_count(published[section_id], 'item')}; "
                f"max_items is {toggle.max_items}",
            )


def _check_window(report: dict[str, Any]) -> Iterator[Issue]:
    tz = report["meta"]["window"]["tz"]
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        yield _error("meta/window/tz", f"unknown time zone {tz!r}; use an IANA name")


def _check_section_notes(report: dict[str, Any], ctx: _Context) -> Iterator[Issue]:
    for section_id, notes in report["section_notes"].items():
        groups = ctx.section_groups.get(section_id)
        if groups is None:
            yield _error(f"section_notes/{section_id}", f"unknown section {section_id!r}")
            continue
        for index, note in enumerate(notes):
            group = note.get("group")
            if group is not None and group not in groups:
                yield _error(
                    f"section_notes/{section_id}/{index}/group",
                    f"section {section_id!r} has no group {group!r}",
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
        section_groups={s["id"]: {g["id"] for g in s["groups"]} for s in sections},
        item_types={t["id"]: t for t in item_types},
        featured_slots=slots,
    )


def validate_report(data: Any, instance_dir: Path | None = None) -> list[Issue]:
    """All problems with a report; schema problems stop further checks."""
    try:
        schema_errors = validate_document(data, REPORT_SCHEMA)
    except (EngineDataError, *SCHEMA_PROBLEMS) as exc:
        return [unusable_issue("load", f"cannot use schema {REPORT_SCHEMA!r} ({exc})")]
    if schema_errors:
        return [_error("schema", message) for message in schema_errors]
    try:
        ctx = _context(instance_dir)
    except (EngineDataError, ConfigError, RegistryError) as exc:
        return [unusable_issue("load", str(exc))]
    report: dict[str, Any] = data
    issues = [
        *_check_registry_refs(report, ctx),
        *_check_unique_ids(report),
        *_check_references(report),
        *_check_sources(report, ctx),
        *_check_confidence_routing(report, ctx),
        *_check_featured(report, ctx),
        *_check_visuals(report),
        *_check_visual_placement(report, ctx),
        *_check_section_config(report, ctx),
        *_check_section_notes(report, ctx),
        *_check_window(report),
    ]
    return sorted(issues)


def _reject_constant(name: str) -> Any:
    msg = f"{name} is not valid JSON"
    raise ValueError(msg)


def _finite_float(text: str) -> float:
    """A JSON number as a float; 1e999 overflows to infinity, which JSON cannot represent."""
    value = float(text)
    if not math.isfinite(value):
        msg = f"{text} is too large to be a JSON number"
        raise ValueError(msg)
    return value


def validate_report_file(path: Path, instance_dir: Path | None = None) -> list[Issue]:
    try:
        text = path.read_text(encoding="utf-8-sig")
        # ValueError covers UnicodeDecodeError, JSONDecodeError, and the NaN/Infinity/1e999
        # rejection.
        data = json.loads(text, parse_constant=_reject_constant, parse_float=_finite_float)
    except RecursionError:
        return [unusable_issue("file", f"{path}: nested too deeply")]
    except (OSError, ValueError) as exc:
        return [unusable_issue("file", f"{path}: {exc}")]
    try:
        return validate_report(data, instance_dir)
    except RecursionError:
        return [unusable_issue("file", f"{path}: nested too deeply")]
