"""Cross-registry consistency rules. Values come from registries; this module only holds rules."""

from __future__ import annotations

import re
import string
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import jmespath
from jmespath.exceptions import JMESPathError
from jsonschema.exceptions import SchemaError
from packaging.specifiers import InvalidSpecifier, SpecifierSet

from pulseai.config import ConfigError, load_config
from pulseai.issues import Issue
from pulseai.models.config import PulseConfig
from pulseai.registry.loader import (
    LOCALE_REGISTRY,
    LOCALE_VARIABLE,
    RegistryError,
    load_catalog,
    load_locale,
    load_registry,
)
from pulseai.schemas import (
    ITEM_TYPE_SCHEMA_DIR,
    SchemaNotFoundError,
    SchemaShapeError,
    load_schema,
    schema_file,
)

COLLECTOR_EXPRESSION_KEYS = ("items", "key")


def _error(where: str, message: str) -> Issue:
    return Issue("error", where, message)


def _warning(where: str, message: str) -> Issue:
    return Issue("warning", where, message)


def _template_fields(text: str) -> Iterator[str]:
    for _, field, _, _ in string.Formatter().parse(text):
        if field:
            yield field


def _label_keys(
    sections: list[dict[str, Any]], item_types: list[dict[str, Any]]
) -> Iterator[tuple[str, str]]:
    for i, section in enumerate(sections):
        yield f"sections/{i}/label", section["label"]
        for j, group in enumerate(section["groups"]):
            yield f"sections/{i}/groups/{j}/label", group["label"]
    for i, item_type in enumerate(item_types):
        yield f"item_types/{i}/label", item_type["label"]


def _check_sections(sections: list[dict[str, Any]], type_ids: set[str]) -> Iterator[Issue]:
    for i, section in enumerate(sections):
        for t in section["default_item_types"]:
            if t not in type_ids:
                yield _error(f"sections/{i}/default_item_types", f"unknown item type {t!r}")
        for j, group in enumerate(section["groups"]):
            for t in group["match"].get("types", []):
                if t not in type_ids:
                    yield _error(f"sections/{i}/groups/{j}/match/types", f"unknown item type {t!r}")


def _check_item_types(
    item_types: list[dict[str, Any]], instance_dir: Path | None
) -> Iterator[Issue]:
    for i, item_type in enumerate(item_types):
        name = f"{ITEM_TYPE_SCHEMA_DIR}/{item_type['schema']}"
        try:
            properties = set(load_schema(name, instance_dir).get("properties", {}))
        except (SchemaNotFoundError, SchemaShapeError) as exc:
            yield _error(f"item_types/{i}/schema", str(exc))
            continue
        except (ValueError, SchemaError) as exc:
            # ValueError covers JSONDecodeError and UnicodeDecodeError from the schema file.
            problem = exc.message if isinstance(exc, SchemaError) else str(exc)
            yield _error(
                f"item_types/{i}/schema", f"{schema_file(name, instance_dir)}: invalid ({problem})"
            )
            continue
        for key in ("brief_fields", "markdown_fields"):
            for field in item_type[key]:
                if field not in properties:
                    yield _error(
                        f"item_types/{i}/{key}", f"field {field!r} is not in {item_type['schema']}"
                    )


def _check_locales(
    labels: list[tuple[str, str]], cfg: PulseConfig, instance_dir: Path | None
) -> Iterator[Issue]:
    try:
        merged = load_locale(cfg.language, instance_dir)
        own = load_registry(LOCALE_REGISTRY, instance_dir, {LOCALE_VARIABLE: cfg.language}).data
    except RegistryError as exc:
        yield _error("language", str(exc))
        return
    for where, key in labels:
        if key not in merged:
            yield _error(where, f"missing locale string {key!r}")
        elif own["fallback"] is not None and key not in own["strings"]:
            yield _warning(where, f"{key!r} is not translated to {cfg.language!r}; using fallback")


def _check_config(cfg: PulseConfig, section_ids: set[str], role_ids: set[str]) -> Iterator[Issue]:
    for section_id in cfg.sections:
        if section_id not in section_ids:
            yield _error(f"config/sections/{section_id}", f"unknown section {section_id!r}")
    for section_id in sorted(section_ids - set(cfg.sections)):
        yield _warning(
            f"config/sections/{section_id}", "section has no config entry; it is disabled"
        )
    for role in cfg.models_by_role:
        if role not in role_ids:
            yield _error(f"config/models_by_role/{role}", f"unknown role {role!r}")
    for role in sorted(role_ids - set(cfg.models_by_role)):
        yield _error(f"config/models_by_role/{role}", f"role {role!r} has no model")
    try:
        ZoneInfo(cfg.schedule.tz)
    except (ZoneInfoNotFoundError, ValueError):
        yield _error("config/schedule/tz", f"unknown time zone {cfg.schedule.tz!r}")
    if cfg.quality.section_cvd_fail > cfg.quality.section_cvd_target:
        yield _error("config/quality", "section_cvd_fail must not exceed section_cvd_target")


def _check_sources(
    sources: list[dict[str, Any]],
    section_ids: set[str],
    allowed_variables: set[str],
    mcp_servers: set[str],
) -> Iterator[Issue]:
    for i, source in enumerate(sources):
        where = f"sources/{i} ({source['id']})"
        for section_id in source["sections"]:
            if section_id not in section_ids:
                yield _error(where, f"unknown section {section_id!r}")
        templates: list[str] = []
        expressions: list[str] = []
        collector = source.get("collector")
        if collector is not None:
            templates.append(collector["url"])
            expressions += [collector[k] for k in COLLECTOR_EXPRESSION_KEYS if k in collector]
            expressions += list(collector.get("fields", {}).values())
            expressions += list(collector.get("track", []))
        templates += source.get("search", {}).get("queries", [])
        for template in templates:
            try:
                fields = list(_template_fields(template))
            except ValueError as exc:
                yield _error(where, f"invalid template {template!r}: {exc}")
                continue
            for field in fields:
                if field not in allowed_variables:
                    yield _error(where, f"unknown template variable {field!r} in {template!r}")
        for expression in expressions:
            try:
                jmespath.compile(expression)
            except JMESPathError as exc:
                yield _error(where, f"invalid JMESPath {expression!r}: {exc}")
        mcp = source.get("mcp")
        if mcp is not None and source["enabled"] and mcp["server"] not in mcp_servers:
            yield _error(
                where,
                f"MCP server {mcp['server']!r} is not listed in config.mcp.enabled "
                "or config.mcp.optional",
            )


def _check_engine(tools: list[dict[str, Any]]) -> Iterator[Issue]:
    for i, tool in enumerate(tools):
        try:
            re.compile(tool["version_regex"])
        except re.error as exc:
            yield _error(f"tools/{i} ({tool['id']})", f"invalid version_regex: {exc}")
        try:
            SpecifierSet(tool["specifier"])
        except InvalidSpecifier:
            yield _error(f"tools/{i} ({tool['id']})", f"invalid specifier {tool['specifier']!r}")


def check_registries(instance_dir: Path | None = None) -> list[Issue]:
    """Load every registry and the config, then apply the cross-reference rules."""
    try:
        cfg = load_config(instance_dir)
        sections = load_registry("sections", instance_dir).data["sections"]
        item_types = load_registry("item-types", instance_dir).data["item_types"]
        roles = load_registry("roles", instance_dir).data["roles"]
        sources = load_registry("sources", instance_dir).data["sources"]
        tools = load_registry("engine", instance_dir).data["tools"]
    except (RegistryError, ConfigError) as exc:
        return [_error("load", str(exc))]

    section_ids = {s["id"] for s in sections}
    type_ids = {t["id"] for t in item_types}
    role_ids = {r["id"] for r in roles}
    mcp_servers = set(cfg.mcp.enabled) | set(cfg.mcp.optional)
    allowed_variables = set(load_catalog().template_variables)

    issues = [
        *_check_sections(sections, type_ids),
        *_check_item_types(item_types, instance_dir),
        *_check_locales(list(_label_keys(sections, item_types)), cfg, instance_dir),
        *_check_config(cfg, section_ids, role_ids),
        *_check_sources(sources, section_ids, allowed_variables, mcp_servers),
        *_check_engine(tools),
    ]
    return sorted(issues)
