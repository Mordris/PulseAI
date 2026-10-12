import json
from pathlib import Path
from typing import Any

import pytest

from pulseai.registry.loader import load_registry
from pulseai.report.validate import validate_report_file

EXAMPLES = Path(__file__).resolve().parents[3] / "examples"
REPORTS = sorted((EXAMPLES / "reports").glob("*/*/*/report.json"))
VISUAL_KINDS = {"vega-lite", "mermaid", "table", "image-ref", "dashboard"}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _kinds(visual: dict[str, Any]) -> set[str]:
    kinds = {visual["kind"]}
    for tile in visual.get("tiles", []):
        if tile["tile"] == "visual":
            kinds |= _kinds(tile["visual"])
    return kinds


def test_three_sample_editions() -> None:
    dates = ["/".join(p.parts[-4:-1]) for p in REPORTS]
    assert dates == ["2026/10/09", "2026/10/10", "2026/10/11"]


@pytest.mark.parametrize("path", REPORTS, ids=lambda p: "/".join(p.parts[-4:-1]))
def test_sample_report_is_valid_without_warnings(path: Path) -> None:
    issues = validate_report_file(path, EXAMPLES)
    assert [f"{i.level} {i.where}: {i.message}" for i in issues] == []


@pytest.mark.parametrize("path", REPORTS, ids=lambda p: "/".join(p.parts[-4:-1]))
def test_path_matches_the_report_date(path: Path) -> None:
    report = _load(path)
    assert report["meta"]["date"] == "-".join(path.parts[-4:-1])
    assert report["meta"]["sample"] is True


def test_editions_count_up_by_date() -> None:
    assert [_load(p)["meta"]["edition"] for p in REPORTS] == [1, 2, 3]


def test_showcase_covers_every_item_type_and_visual_kind() -> None:
    showcase = _load(REPORTS[-1])
    registry_types = {t["id"] for t in load_registry("item-types", EXAMPLES).data["item_types"]}
    used_types = {item["type"] for item in showcase["items"]}
    assert used_types == registry_types
    kinds: set[str] = set()
    for visual in showcase["front_page"]:
        kinds |= _kinds(visual)
    for item in showcase["items"]:
        for visual in item["visuals"]:
            kinds |= _kinds(visual)
    assert kinds == VISUAL_KINDS
    assert any("block" in v for item in showcase["items"] for v in item["visuals"])
    assert showcase["signals"] and showcase["corrections"] and showcase["section_notes"]
    assert any(not source["ok"] for source in showcase["meta"]["source_health"])
    assert any("update_of" in item for item in showcase["items"])
