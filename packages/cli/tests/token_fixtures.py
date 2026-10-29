"""Resolved token maps for tests: a theme that passes `pulse tokens check`, for tests to break."""

import copy
import json
from pathlib import Path
from typing import Any

from pulseai.labels import labelled_enums
from pulseai.registry.loader import load_registry

SECTIONS = ("models", "tooling", "research", "oss")
SECTION_COLORS = {
    "light": ("#2a78d6", "#eb6834", "#1baf7a", "#eda100"),
    "dark": ("#3987e5", "#d95926", "#199e70", "#e6b000"),
}
SURFACE = {"light": "#ffffff", "dark": "#111111"}
TEXT = {"light": "#111111", "dark": "#f5f5f5"}
CHART = {"light": ("#2a78d6", "#eb6834", "#1baf7a"), "dark": ("#3987e5", "#d95926", "#199e70")}
# Every value of a toned enum in the engine schemas has a color. Read once, at import, from the
# real engine: tests that point PULSE_ENGINE_DATA elsewhere still get a passing map.
TONE_TOKENS = tuple(
    token
    for labelled in labelled_enums(load_registry("item-types").data["item_types"])
    for value in labelled.values
    if (token := labelled.tone_token(value)) is not None
)


def entry(path: str, value: Any, extensions: dict[str, Any] | None = None) -> dict[str, Any]:
    token: dict[str, Any] = {
        "value": value,
        "type": "color",
        "name": "--pulse-" + path.replace(".", "-").replace("_", "-"),
    }
    if extensions:
        token["extensions"] = extensions
    return token


def passing(mode: str) -> dict[str, Any]:
    tokens = {
        "color.surface.page": entry("color.surface.page", SURFACE[mode]),
        "color.text.primary": entry(
            "color.text.primary", TEXT[mode], {"contrast_against": ["color.surface.page"]}
        ),
    }
    for section, color in zip(SECTIONS, SECTION_COLORS[mode], strict=True):
        path = f"color.section.{section}"
        tokens[path] = entry(path, color)
    for order, color in enumerate(CHART[mode], start=1):
        path = f"color.chart.category.{order}"
        tokens[path] = entry(path, color, {"distinct": {"set": "chart", "order": order}})
    for token in TONE_TOKENS:
        tokens[token] = entry(token, TEXT[mode])
    return {"schema_version": 1, "preset": "test", "mode": mode, "tokens": tokens}


def write(directory: Path, docs: dict[str, dict[str, Any]] | None = None) -> Path:
    """Write light.json and dark.json (passing maps unless docs replaces one)."""
    directory.mkdir(parents=True, exist_ok=True)
    for mode in ("light", "dark"):
        doc = copy.deepcopy((docs or {}).get(mode) or passing(mode))
        (directory / f"{mode}.json").write_text(json.dumps(doc), encoding="utf-8")
    return directory
