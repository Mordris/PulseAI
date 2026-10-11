import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from pulseai.cli import app
from pulseai.issues import Issue
from pulseai.registry.checks import check_registries

runner = CliRunner()


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _errors(issues: list[Issue]) -> list[str]:
    return [f"{i.where}: {i.message}" for i in issues if i.level == "error"]


def test_engine_defaults_are_consistent() -> None:
    assert check_registries() == []


@pytest.mark.parametrize(
    ("relative", "data", "expected"),
    [
        (
            "taxonomy/sections.yaml",
            {"schema_version": 1, "sections": [{"id": "models", "default_item_types": ["poem"]}]},
            "unknown item type 'poem'",
        ),
        (
            "taxonomy/sections.yaml",
            {"schema_version": 1, "sections": [{"id": "models", "label": "sections.weather"}]},
            "missing locale string 'sections.weather'",
        ),
        (
            "taxonomy/item-types.yaml",
            {"schema_version": 1, "item_types": [{"id": "industry", "brief_fields": ["ceo"]}]},
            "field 'ceo' is not in industry.schema.json",
        ),
        (
            "taxonomy/item-types.yaml",
            {
                "schema_version": 1,
                "item_types": [{"id": "industry", "schema": "missing.schema.json"}],
            },
            "schema 'item-types/missing.schema.json' not found",
        ),
        (
            "pulse.config.yaml",
            {"sections": {"weather": {"enabled": True, "max_items": 3}}},
            "unknown section 'weather'",
        ),
        (
            "pulse.config.yaml",
            {"models_by_role": {"intern": "claude-haiku-5-5"}},
            "unknown role 'intern'",
        ),
        ("pulse.config.yaml", {"schedule": {"tz": "Mars/Olympus"}}, "unknown time zone"),
        (
            "defaults/engine.yaml",
            {"tools": [{"id": "uv", "version_regex": r"uv \d+\.\d+"}]},
            "version_regex needs a capture group",
        ),
        (
            "defaults/engine.yaml",
            {"tools": [{"id": "uv", "version_regex": "uv ("}]},
            "invalid version_regex",
        ),
        (
            "defaults/engine.yaml",
            {"tools": [{"id": "uv", "specifier": ">=0.11 totally bogus"}]},
            "invalid specifier",
        ),
        (
            "pulse.config.yaml",
            {"quality": {"section_cvd_fail": 9, "section_cvd_target": 8}},
            "section_cvd_fail must not exceed section_cvd_target",
        ),
        (
            "sources/registry/mine.yaml",
            {
                "schema_version": 1,
                "sources": [
                    {
                        "id": "via-unknown-mcp",
                        "name": "Unknown MCP",
                        "tier": "T1",
                        "sections": ["tooling"],
                        "trust": 4,
                        "enabled": True,
                        "via": "mcp",
                        "mcp": {"server": "jira", "tool": "search"},
                    }
                ],
            },
            "MCP server 'jira' is not listed in config.mcp.enabled or config.mcp.optional",
        ),
    ],
)
def test_rule_violations(tmp_path: Path, relative: str, data: Any, expected: str) -> None:
    _write(tmp_path / relative, data)
    errors = _errors(check_registries(tmp_path))
    assert any(expected in e for e in errors), errors


def test_bad_source_reports_every_problem(tmp_path: Path) -> None:
    _write(
        tmp_path / "sources/registry/mine.yaml",
        {
            "schema_version": 1,
            "sources": [
                {
                    "id": "bad-json",
                    "name": "Bad",
                    "tier": "T2",
                    "sections": ["weather"],
                    "trust": 2,
                    "enabled": True,
                    "via": "collector",
                    "collector": {
                        "kind": "json",
                        "url": "https://example.org/{when}",
                        "items": "items[",
                        "fields": {"title": "title", "url": "url"},
                    },
                }
            ],
        },
    )
    joined = "\n".join(_errors(check_registries(tmp_path)))
    assert "unknown section 'weather'" in joined
    assert "unknown template variable 'when'" in joined
    assert "invalid JMESPath" in joined


def _source(**extra: Any) -> dict[str, Any]:
    return {
        "id": "templated",
        "name": "Templated",
        "tier": "T2",
        "sections": ["tooling"],
        "trust": 2,
        "enabled": True,
        **extra,
    }


def _collector_source(url: str) -> dict[str, Any]:
    collector = {"kind": "json", "url": url, "items": "items", "fields": {"title": "t", "url": "u"}}
    return _source(via="collector", collector=collector)


def _search_source(query: str) -> dict[str, Any]:
    return _source(via="search", search={"queries": [query]})


@pytest.mark.parametrize(
    "source",
    [
        _collector_source("https://e.org/{"),
        _collector_source("https://e.org/a}b"),
        _search_source("{foo OR bar"),
    ],
    ids=["collector-open-brace", "collector-close-brace", "search-open-brace"],
)
def test_malformed_template_is_reported(tmp_path: Path, source: dict[str, Any]) -> None:
    _write(tmp_path / "sources/registry/mine.yaml", {"schema_version": 1, "sources": [source]})
    errors = _errors(check_registries(tmp_path))
    assert any("invalid template" in e for e in errors), errors


@pytest.mark.parametrize(
    ("content", "problem"),
    [
        ("{not json", "Expecting property name"),
        ('{"type": 5}', "5 is not valid under any of the given schemas"),
        ("true", "must be a JSON object"),
    ],
    ids=["not-json", "not-a-schema", "boolean-schema"],
)
def test_broken_item_type_schema_is_reported(tmp_path: Path, content: str, problem: str) -> None:
    broken = tmp_path / "schema/item-types/broken.schema.json"
    broken.parent.mkdir(parents=True)
    broken.write_text(content, encoding="utf-8")
    _write(
        tmp_path / "taxonomy/item-types.yaml",
        {"schema_version": 1, "item_types": [{"id": "industry", "schema": "broken.schema.json"}]},
    )
    errors = _errors(check_registries(tmp_path))
    assert any(
        e.startswith("item_types/") and "/schema:" in e and str(broken) in e and problem in e
        for e in errors
    ), errors


def test_missing_translation_is_a_warning(tmp_path: Path, engine_copy: Path) -> None:
    # Instance locale overrides merge over the engine file and cannot delete keys, so remove the
    # translation from a writable engine copy instead.
    tr_path = engine_copy / "locales/tr.json"
    tr = json.loads(tr_path.read_text(encoding="utf-8"))
    del tr["strings"]["sections.models"]
    tr_path.write_text(json.dumps(tr, ensure_ascii=False), encoding="utf-8")
    instance = tmp_path / "instance"
    _write(instance / "pulse.config.yaml", {"language": "tr"})
    issues = check_registries(instance)
    assert _errors(issues) == []
    assert any(i.level == "warning" and "not translated" in i.message for i in issues)


def test_cli_registry_check_exit_codes(tmp_path: Path) -> None:
    ok = runner.invoke(app, ["registry", "check", "--instance", str(tmp_path)])
    assert ok.exit_code == 0
    _write(tmp_path / "pulse.config.yaml", {"models_by_role": {"intern": "x"}})
    bad = runner.invoke(app, ["registry", "check", "--instance", str(tmp_path)])
    assert bad.exit_code == 1
    assert "unknown role 'intern'" in bad.output
