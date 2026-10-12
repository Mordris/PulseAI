"""Resolve the site build context: everything the site needs from the engine and an instance.

The merge logic for config, registries, and locales lives here (in Python) only; the site reads the
result instead of re-implementing it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pulseai import __version__
from pulseai.config import load_config
from pulseai.registry.loader import load_locale, load_registry
from pulseai.schemas import ITEM_TYPE_SCHEMA_DIR, SCHEMA_PROBLEMS, load_schema, validate_document

SITE_CONTEXT_SCHEMA = "site-context.schema.json"
REPORT_SCHEMA = "report.schema.json"
WORK_DIR = ".pulse"
CONTEXT_FILE = "site-context.json"


class SiteContextError(Exception):
    """A schema the context needs is missing or broken, or the context fails its own schema."""


def default_context_path(instance_dir: Path | None) -> Path:
    return (instance_dir or Path.cwd()) / WORK_DIR / CONTEXT_FILE


def _schemas(item_types: list[dict[str, Any]], instance_dir: Path | None) -> dict[str, Any]:
    names = sorted({f"{ITEM_TYPE_SCHEMA_DIR}/{t['schema']}" for t in item_types})
    schemas: dict[str, Any] = {}
    for name in [REPORT_SCHEMA, *names]:
        # The report schema is engine-only, exactly as `pulse validate` uses it.
        owner = None if name == REPORT_SCHEMA else instance_dir
        try:
            schemas[name] = load_schema(name, owner)
        except SCHEMA_PROBLEMS as exc:
            msg = f"cannot use schema {name!r} ({exc})"
            raise SiteContextError(msg) from None
    return schemas


def build_site_context(instance_dir: Path | None = None) -> dict[str, Any]:
    cfg = load_config(instance_dir)
    sections = sorted(
        load_registry("sections", instance_dir).data["sections"],
        key=lambda section: (section["order"], section["id"]),
    )
    item_types = load_registry("item-types", instance_dir).data["item_types"]
    context: dict[str, Any] = {
        "schema_version": 1,
        "engine_version": __version__,
        "config": cfg.model_dump(mode="json", exclude_unset=True),
        "sections": sections,
        "item_types": item_types,
        "strings": load_locale(cfg.language, instance_dir),
        "schemas": _schemas(item_types, instance_dir),
    }
    try:
        errors = validate_document(context, SITE_CONTEXT_SCHEMA)
    except SCHEMA_PROBLEMS as exc:
        msg = f"cannot use schema {SITE_CONTEXT_SCHEMA!r} ({exc})"
        raise SiteContextError(msg) from None
    if errors:
        msg = "site context is invalid\n" + "\n".join(f"  - {error}" for error in errors)
        raise SiteContextError(msg)
    return context


def write_site_context(instance_dir: Path | None, out: Path) -> Path:
    context = build_site_context(instance_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(context, ensure_ascii=False, indent=2)
    out.write_text(text + "\n", encoding="utf-8")
    return out
