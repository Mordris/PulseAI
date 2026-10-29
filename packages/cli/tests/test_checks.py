import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from pulseai.cli import app
from pulseai.issues import Issue
from pulseai.paths import ENGINE_DATA_ENV
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


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"version_regex": r"uv \d+\.\d+"}, "version_regex needs a capture group"),
        ({"version_regex": "uv ("}, "invalid version_regex"),
        ({"specifier": ">=0.11 totally bogus"}, "invalid specifier"),
    ],
)
def test_engine_tool_violations(engine_copy: Path, change: dict[str, str], expected: str) -> None:
    # Tool requirements are engine-only: edit the engine data, not an instance.
    path = engine_copy / "defaults/engine.yaml"
    engine = yaml.safe_load(path.read_text(encoding="utf-8"))
    next(tool for tool in engine["tools"] if tool["id"] == "uv").update(change)
    _write(path, engine)
    errors = _errors(check_registries())
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


def test_unresolvable_ref_in_an_item_type_schema_is_reported(tmp_path: Path) -> None:
    broken = tmp_path / "schema/item-types/industry.schema.json"
    broken.parent.mkdir(parents=True)
    broken.write_text(
        json.dumps({"type": "object", "properties": {"who": {"$ref": "#/$defs/missing"}}}),
        encoding="utf-8",
    )
    errors = _errors(check_registries(tmp_path))
    assert any(
        e.startswith("item_types/")
        and str(broken) in e
        and "unresolvable $ref '#/$defs/missing'" in e
        for e in errors
    ), errors


def test_resolvable_refs_are_accepted(tmp_path: Path) -> None:
    ok = tmp_path / "schema/item-types/industry.schema.json"
    ok.parent.mkdir(parents=True)
    ok.write_text(
        json.dumps(
            {
                "$defs": {"name": {"type": "string"}},
                "type": "object",
                "properties": {"who": {"$ref": "#/$defs/name"}, "what": {"$ref": "#/$defs/name"}},
            }
        ),
        encoding="utf-8",
    )
    assert not any("unresolvable" in e for e in _errors(check_registries(tmp_path)))


def test_item_type_schema_with_a_dollar_id_property_is_accepted(tmp_path: Path) -> None:
    ok = tmp_path / "schema/item-types/industry.schema.json"
    ok.parent.mkdir(parents=True)
    ok.write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"$id": {"type": "string", "examples": [{"$ref": "#/nowhere"}]}},
            }
        ),
        encoding="utf-8",
    )
    assert not any(str(ok) in e for e in _errors(check_registries(tmp_path)))


def test_unreadable_item_type_schema_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = tmp_path / "schema/item-types/industry.schema.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{}", encoding="utf-8")
    real_read_text = Path.read_text

    def read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        if self == broken:
            raise PermissionError(13, "Permission denied")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    errors = _errors(check_registries(tmp_path))
    assert any(
        e.startswith("item_types/") and str(broken) in e and "cannot read (Permission denied)" in e
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


def test_an_instance_enum_value_without_a_locale_string_is_an_error(
    tmp_path: Path, repo_root: Path
) -> None:
    schema = json.loads(
        (repo_root / "schema/item-types/security_advisory.schema.json").read_text(encoding="utf-8")
    )
    schema["properties"]["severity"]["enum"].append("extreme")
    override = tmp_path / "schema/item-types/security_advisory.schema.json"
    override.parent.mkdir(parents=True)
    override.write_text(json.dumps(schema), encoding="utf-8")
    assert _errors(check_registries(tmp_path)) == [
        "item-types/security_advisory.schema.json#/properties/severity: "
        "missing locale string 'severity.extreme'"
    ]


def test_cli_registry_check_exit_codes(tmp_path: Path) -> None:
    ok = runner.invoke(app, ["registry", "check", "--instance", str(tmp_path)])
    assert ok.exit_code == 0
    _write(tmp_path / "pulse.config.yaml", {"models_by_role": {"intern": "x"}})
    bad = runner.invoke(app, ["registry", "check", "--instance", str(tmp_path)])
    assert bad.exit_code == 1
    assert "unknown role 'intern'" in bad.output


def test_rule_violations_are_not_unusable(tmp_path: Path) -> None:
    _write(tmp_path / "pulse.config.yaml", {"models_by_role": {"intern": "x"}})
    issues = check_registries(tmp_path)
    assert _errors(issues)
    assert not any(i.unusable for i in issues)


def test_an_unloadable_config_is_one_unusable_load_issue(tmp_path: Path) -> None:
    _write(tmp_path / "pulse.config.yaml", {"schedule": {"time": "99:99"}})
    issues = check_registries(tmp_path)
    assert [(i.where, i.unusable) for i in issues] == [("load", True)]


def test_missing_engine_data_is_an_unusable_load_issue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENGINE_DATA_ENV, str(tmp_path / "nowhere"))
    issues = check_registries(tmp_path)
    assert [(i.where, i.unusable) for i in issues] == [("load", True)]
    assert ENGINE_DATA_ENV in issues[0].message


def test_duplicate_ids_in_an_engine_file_fail_the_registry_check(engine_copy: Path) -> None:
    path = engine_copy / "taxonomy/roles.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["roles"].append(dict(doc["roles"][0]))
    _write(path, doc)
    issues = check_registries()
    assert [(i.where, i.unusable) for i in issues] == [("load", True)]
    assert f"duplicate id {doc['roles'][0]['id']!r} in roles" in issues[0].message
    result = runner.invoke(app, ["registry", "check"])
    assert result.exit_code == 2
    assert "duplicate id" in result.stderr


def test_duplicate_ids_in_an_instance_file_fail_the_registry_check(tmp_path: Path) -> None:
    _write(
        tmp_path / "taxonomy/sections.yaml",
        {"schema_version": 1, "sections": [{"id": "models", "order": 1}, {"id": "models"}]},
    )
    issues = check_registries(tmp_path)
    assert [(i.where, i.unusable) for i in issues] == [("load", True)]
    assert "duplicate id 'models' in sections" in issues[0].message


@pytest.mark.parametrize(
    ("locale", "problem"),
    [
        ("{not json", "cannot parse"),
        (None, "no engine or instance files match locales/de.json"),
        (
            json.dumps({"schema_version": 1, "language": "de", "fallback": "de", "strings": {}}),
            "locale fallback cycle",
        ),
    ],
    ids=["not-json", "no-file", "fallback-cycle"],
)
def test_a_locale_that_fails_to_load_is_an_unusable_issue(
    tmp_path: Path, locale: str | None, problem: str
) -> None:
    _write(tmp_path / "pulse.config.yaml", {"language": "de"})
    if locale is not None:
        (tmp_path / "locales").mkdir()
        (tmp_path / "locales/de.json").write_text(locale, encoding="utf-8")
    issues = check_registries(tmp_path)
    assert [(i.where, i.unusable) for i in issues] == [("language", True)]
    assert problem in issues[0].message


def test_an_instance_can_add_a_language_end_to_end(tmp_path: Path) -> None:
    _write(tmp_path / "pulse.config.yaml", {"language": "de"})
    (tmp_path / "locales").mkdir()
    (tmp_path / "locales/de.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "language": "de",
                "fallback": "en",
                "strings": {"sections.models": "Modelle und Labore"},
            }
        ),
        encoding="utf-8",
    )
    config = runner.invoke(app, ["config", "check", "--instance", str(tmp_path)])
    assert config.exit_code == 0, config.output
    registries = runner.invoke(app, ["registry", "check", "--instance", str(tmp_path)])
    assert registries.exit_code == 0, registries.output
    assert "Registries are consistent." in registries.stdout
    assert "not translated to 'de'" in registries.stdout


def test_block_and_brief_field_labels_must_exist(engine_copy: Path) -> None:
    for name in ("en", "tr"):
        path = engine_copy / "locales" / f"{name}.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        del doc["strings"]["blocks.timeline"]
        del doc["strings"]["fields.who"]
        path.write_text(json.dumps(doc), encoding="utf-8")
    messages = [f"{i.where}: {i.message}" for i in check_registries() if i.level == "error"]
    assert any("missing locale string 'blocks.timeline'" in m for m in messages), messages
    assert any("missing locale string 'fields.who'" in m for m in messages), messages
    assert any("/blocks/" in m for m in messages)
    assert any("/brief_fields/" in m for m in messages)


def _write_sources(tmp_path: Path, *sources: dict[str, Any]) -> None:
    _write(tmp_path / "sources/registry/mine.yaml", {"schema_version": 1, "sources": list(sources)})


def _collector_with_id(source_id: str, url: str, **overrides: Any) -> dict[str, Any]:
    return {**_collector_source(url), "id": source_id, **overrides}


def _authenticated_source(source_id: str = "keyed", **http: Any) -> dict[str, Any]:
    source = _collector_with_id(source_id, "https://e.org/feed.json")
    source["collector"]["http"] = {"auth_header": "X-Api-Key", "auth_env": "EXAMPLE_KEY", **http}
    return source


def _warnings(issues: list[Issue]) -> list[str]:
    return [f"{i.where}: {i.message}" for i in issues if i.level == "warning"]


@pytest.mark.parametrize(
    "variable",
    ["config.window.max_hours", "config.quality.text_contrast_min", "config.language"],
    ids=["int", "float", "str"],
)
def test_config_template_variable_resolves(tmp_path: Path, variable: str) -> None:
    _write_sources(tmp_path, _collector_source(f"https://e.org/feed?v={{{variable}}}"))
    assert _errors(check_registries(tmp_path)) == []


def test_config_template_variable_is_accepted_in_a_search_query(tmp_path: Path) -> None:
    _write_sources(tmp_path, _search_source("claude {config.window.max_hours}"))
    assert _errors(check_registries(tmp_path)) == []


@pytest.mark.parametrize(
    "variable",
    ["config.window.nope", "config.nope", "config.", "config", "configuration.window"],
    ids=["unknown-leaf", "unknown-section", "empty-path", "bare-config", "other-prefix"],
)
def test_unknown_config_template_variable(tmp_path: Path, variable: str) -> None:
    _write_sources(tmp_path, _collector_source(f"https://e.org/{{{variable}}}"))
    errors = _errors(check_registries(tmp_path))
    assert any(f"unknown template variable '{variable}'" in e for e in errors), errors


@pytest.mark.parametrize(
    "variable",
    ["config.interests.high", "config.window", "config.site.url", "config.collect.respect_robots"],
    ids=["list", "mapping", "null", "boolean"],
)
def test_non_scalar_config_template_variable(tmp_path: Path, variable: str) -> None:
    _write_sources(tmp_path, _collector_source(f"https://e.org/{{{variable}}}"))
    errors = _errors(check_registries(tmp_path))
    assert any(f"'{variable}' must be a string or number" in e for e in errors), errors


@pytest.mark.parametrize(
    ("field", "problem"),
    [
        ("date:%Y", "has a format spec or conversion"),
        ("date!r", "has a format spec or conversion"),
        ("config.window.max_hours:>5", "has a format spec or conversion"),
        ("", "has no name"),
        (":>5", "has no name"),
    ],
    ids=["format-spec", "conversion", "config-format-spec", "empty-name", "empty-name-with-spec"],
)
@pytest.mark.parametrize("make_source", [_collector_source, _search_source], ids=["url", "query"])
def test_template_field_that_expand_url_rejects_is_an_error(
    tmp_path: Path, make_source: Callable[[str], dict[str, Any]], field: str, problem: str
) -> None:
    template = (
        f"https://e.org/{{{field}}}" if make_source is _collector_source else f"x {{{field}}}"
    )
    _write_sources(tmp_path, make_source(template))
    errors = _errors(check_registries(tmp_path))
    assert any(f"{problem} in {template!r}" in e for e in errors), errors


def test_catalog_and_config_variables_can_be_mixed(tmp_path: Path) -> None:
    _write_sources(tmp_path, _collector_source("https://e.org/{date}/{config.window.max_hours}"))
    assert _errors(check_registries(tmp_path)) == []


def test_duplicate_collector_url_warns(tmp_path: Path) -> None:
    url = "https://e.org/feed.json"
    _write_sources(
        tmp_path,
        _collector_with_id("first", url),
        _collector_with_id("second", url),
        _collector_with_id("other", "https://e.org/other.json"),
    )
    warnings = [w for w in _warnings(check_registries(tmp_path)) if url in w]
    assert len(warnings) == 1, warnings
    assert "'first'" in warnings[0]
    assert "'second'" in warnings[0]
    assert "'other'" not in warnings[0]


def test_a_url_shared_by_three_sources_warns_once(tmp_path: Path) -> None:
    url = "https://e.org/feed.json"
    _write_sources(tmp_path, *(_collector_with_id(name, url) for name in ("a", "b", "c")))
    warnings = [w for w in _warnings(check_registries(tmp_path)) if url in w]
    assert len(warnings) == 1, warnings
    assert all(f"'{name}'" in warnings[0] for name in ("a", "b", "c"))


def test_disabled_duplicate_url_does_not_warn(tmp_path: Path) -> None:
    url = "https://e.org/feed.json"
    _write_sources(
        tmp_path,
        _collector_with_id("first", url),
        _collector_with_id("second", url, enabled=False),
    )
    assert _warnings(check_registries(tmp_path)) == []


def test_required_auth_env_unset_warns(tmp_path: Path) -> None:
    _write_sources(tmp_path, _authenticated_source())
    issues = check_registries(tmp_path, environ={})
    assert any(i.level == "warning" and "EXAMPLE_KEY" in i.message for i in issues)
    assert _errors(issues) == []


def test_required_auth_env_set_is_silent(tmp_path: Path) -> None:
    _write_sources(tmp_path, _authenticated_source())
    assert _warnings(check_registries(tmp_path, environ={"EXAMPLE_KEY": "secret"})) == []


def test_auth_env_warning_never_carries_the_secret(tmp_path: Path) -> None:
    _write_sources(tmp_path, _authenticated_source(), _authenticated_source("other"))
    issues = check_registries(tmp_path, environ={"EXAMPLE_KEY": "s3cr3t-value"})
    assert "s3cr3t-value" not in "".join(f"{i.where}{i.message}" for i in issues)


def test_optional_auth_env_unset_is_silent(tmp_path: Path) -> None:
    _write_sources(tmp_path, _authenticated_source(auth_optional=True))
    assert _warnings(check_registries(tmp_path, environ={})) == []


def test_disabled_source_with_unset_auth_env_is_silent(tmp_path: Path) -> None:
    source = _authenticated_source()
    source["enabled"] = False
    _write_sources(tmp_path, source)
    assert _warnings(check_registries(tmp_path, environ={})) == []


def test_environ_defaults_to_the_process_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_sources(tmp_path, _authenticated_source())
    monkeypatch.delenv("EXAMPLE_KEY", raising=False)
    assert any("EXAMPLE_KEY" in w for w in _warnings(check_registries(tmp_path)))
    monkeypatch.setenv("EXAMPLE_KEY", "secret")
    assert _warnings(check_registries(tmp_path)) == []


def test_cli_registry_check_reports_unset_auth_env_without_failing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_sources(tmp_path, _authenticated_source())
    monkeypatch.delenv("EXAMPLE_KEY", raising=False)
    result = runner.invoke(app, ["registry", "check", "--instance", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "warning sources/" in result.output
    assert "EXAMPLE_KEY" in result.output
