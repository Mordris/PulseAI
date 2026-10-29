import json
from pathlib import Path
from typing import Any

import jsonpatch
import pytest

from pulseai.schemas import (
    SchemaRefError,
    SchemaShapeError,
    check_references,
    load_schema,
    validate_document,
)


@pytest.mark.parametrize("content", ["true", "false"])
def test_load_schema_rejects_non_object_documents(tmp_path: Path, content: str) -> None:
    # A bare boolean is a valid JSON Schema, but no registry can use it as a document schema.
    path = tmp_path / "schema/item-types/flag.schema.json"
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    with pytest.raises(SchemaShapeError) as excinfo:
        load_schema("item-types/flag.schema.json", tmp_path)
    message = str(excinfo.value)
    assert "item-types/flag.schema.json" in message
    assert str(path) in message
    assert "must be a JSON object" in message


def test_schema_shape_error_is_a_value_error() -> None:
    assert issubclass(SchemaShapeError, ValueError)


def test_load_schema_returns_object_documents(tmp_path: Path) -> None:
    path = tmp_path / "schema/item-types/ok.schema.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"type": "object", "properties": {"a": {}}}', encoding="utf-8")
    assert load_schema("item-types/ok.schema.json", tmp_path)["properties"] == {"a": {}}


def test_property_named_dollar_id_is_not_a_schema_keyword() -> None:
    # Property names are data: a property called "$id" must not be read as the schema's identifier.
    check_references(
        {"type": "object", "properties": {"$id": {"type": "string"}, "$ref": {"type": "string"}}}
    )


def test_load_schema_accepts_a_property_named_dollar_id(tmp_path: Path) -> None:
    path = tmp_path / "schema/item-types/ok.schema.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"type": "object", "properties": {"$id": {"type": "string"}}}', encoding="utf-8"
    )
    assert load_schema("item-types/ok.schema.json", tmp_path)["type"] == "object"


@pytest.mark.parametrize(
    "keyword_value",
    [
        ("examples", [{"$ref": "#/nowhere"}]),
        ("default", {"$ref": "#/nowhere"}),
        ("const", {"$ref": "#/nowhere"}),
        ("enum", [{"$ref": "#/nowhere"}]),
    ],
    ids=["examples", "default", "const", "enum"],
)
def test_ref_shaped_instance_data_is_not_a_reference(keyword_value: tuple[str, Any]) -> None:
    keyword, value = keyword_value
    check_references({"type": "object", "properties": {"x": {keyword: value}}})


@pytest.mark.parametrize(
    "schema",
    [
        {"$ref": "#/$defs/missing"},
        {"properties": {"x": {"$ref": "#/$defs/missing"}}},
        {"items": {"$ref": "#/$defs/missing"}},
        {"$defs": {"x": {"$ref": "#/$defs/missing"}}},
        {"oneOf": [{"type": "string"}, {"$ref": "#/$defs/missing"}]},
        {"properties": {"x": {"items": {"oneOf": [{"$ref": "#/$defs/missing"}]}}}},
    ],
    ids=["root", "properties", "items", "defs", "one-of", "nested"],
)
def test_unresolvable_refs_are_still_reported(schema: dict[str, Any]) -> None:
    with pytest.raises(SchemaRefError, match=r"unresolvable \$ref '#/\$defs/missing'"):
        check_references(schema)


def test_refs_resolve_inside_subschemas_with_their_own_id() -> None:
    check_references(
        {
            "$defs": {
                "inner": {
                    "$id": "https://example.test/inner",
                    "$defs": {"leaf": {"type": "string"}},
                    "properties": {"a": {"$ref": "#/$defs/leaf"}},
                }
            }
        }
    )


# --- Sources registry: the sitemap kind and the M3a collector fields ---------------------------

SOURCES = "sources.schema.json"
COLLECTED = "collected.schema.json"
COLLECT_RUN = "collect-run.schema.json"
EXAMPLES = Path(__file__).resolve().parents[3] / "schema" / "examples"


def _source(collector: dict[str, Any], **extra: Any) -> dict[str, Any]:
    source: dict[str, Any] = {
        "id": "example-lab",
        "name": "Example Lab",
        "tier": "T1",
        "sections": ["models"],
        "trust": 4,
        "enabled": True,
        "via": "collector",
        "collector": collector,
    }
    return source | extra


def _registry(source: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": 1, "sources": [source]}


def _sitemap(**fields: Any) -> dict[str, Any]:
    base = {"kind": "sitemap", "url": "https://example.com/sitemap.xml", "include": ["/news/"]}
    return base | fields


def test_sitemap_collector_requires_include() -> None:
    collector = {"kind": "sitemap", "url": "https://example.com/sitemap.xml"}
    assert validate_document(_registry(_source(collector)), SOURCES)
    assert validate_document(_registry(_source(_sitemap())), SOURCES) == []


def test_sitemap_collector_accepts_globs_and_limit() -> None:
    collector = _sitemap(
        include=["/news/*"], exclude=["/news/tag/*", "/news/archive"], meta_fetch_limit=20
    )
    assert validate_document(_registry(_source(collector)), SOURCES) == []


@pytest.mark.parametrize(
    "fields",
    [
        {"include": []},
        {"include": ["news/"]},
        {"include": ["/news/ x"]},
        {"exclude": []},
        {"exclude": ["tag/*"]},
        {"meta_fetch_limit": 0},
        {"meta_fetch_limit": 1.5},
        {"selector": "a"},
    ],
    ids=[
        "empty-include",
        "include-without-slash",
        "include-with-space",
        "empty-exclude",
        "exclude-without-slash",
        "zero-limit",
        "fractional-limit",
        "unknown-field",
    ],
)
def test_sitemap_collector_rejects_bad_fields(fields: dict[str, Any]) -> None:
    assert validate_document(_registry(_source(_sitemap(**fields))), SOURCES)


def test_sitemap_collector_accepts_http_options() -> None:
    collector = _sitemap(http={"timeout_seconds": 30, "rate_limit_per_minute": 10})
    assert validate_document(_registry(_source(collector)), SOURCES) == []


def test_feed_collector_accepts_optional_fields() -> None:
    plain = {"kind": "rss", "url": "https://example.com/feed.xml"}
    mapped = plain | {"fields": {"title": "title", "url": "links[0].href"}}
    assert validate_document(_registry(_source(plain)), SOURCES) == []
    assert validate_document(_registry(_source(mapped)), SOURCES) == []
    assert validate_document(_registry(_source(mapped | {"kind": "atom"})), SOURCES) == []


def test_feed_fields_are_validated_like_json_fields() -> None:
    bad = {"kind": "rss", "url": "https://example.com/feed.xml", "fields": {"title": "title"}}
    assert validate_document(_registry(_source(bad)), SOURCES)


def _json_collector(**fields: Any) -> dict[str, Any]:
    return {
        "kind": "json",
        "url": "https://api.example.com/releases",
        "items": "[*]",
        "fields": {"title": "name", "url": "html_url"} | fields,
    }


def test_field_map_extra_is_jmespath_by_id() -> None:
    good = _json_collector(extra={"prerelease": "prerelease", "tag-name": "tag_name"})
    assert validate_document(_registry(_source(good)), SOURCES) == []
    bad_key = _json_collector(extra={"Bad Key": "x"})
    assert validate_document(_registry(_source(bad_key)), SOURCES)
    empty_path = _json_collector(extra={"prerelease": ""})
    assert validate_document(_registry(_source(empty_path)), SOURCES)
    not_a_path = _json_collector(extra={"prerelease": 1})
    assert validate_document(_registry(_source(not_a_path)), SOURCES)


def test_field_map_extra_applies_to_snapshot_collectors() -> None:
    collector = {
        "kind": "json-snapshot-diff",
        "url": "https://api.example.com/models",
        "items": "data",
        "key": "id",
        "fields": {"title": "name", "url": "url", "extra": {"context": "context_length"}},
    }
    assert validate_document(_registry(_source(collector)), SOURCES) == []


def test_http_auth_optional_is_boolean() -> None:
    def with_http(http: dict[str, Any]) -> dict[str, Any]:
        return _registry(_source(_json_collector() | {"http": http}))

    optional = {"auth_env": "GITHUB_TOKEN", "auth_optional": True}
    assert validate_document(with_http(optional), SOURCES) == []
    assert validate_document(with_http({"auth_optional": False}), SOURCES) == []
    assert validate_document(with_http({"auth_optional": "yes"}), SOURCES)


def test_changelog_flag_on_collector_sources_only() -> None:
    feed = {"kind": "rss", "url": "https://example.com/changelog.xml"}
    assert validate_document(_registry(_source(feed, changelog=True)), SOURCES) == []
    assert validate_document(_registry(_source(feed, changelog="yes")), SOURCES)

    mcp = {
        "id": "example-mcp",
        "name": "Example MCP",
        "tier": "T1",
        "sections": ["tooling"],
        "trust": 5,
        "enabled": True,
        "via": "mcp",
        "mcp": {"server": "github", "tool": "list_releases"},
    }
    assert validate_document(_registry(mcp), SOURCES) == []
    assert validate_document(_registry(mcp | {"changelog": True}), SOURCES)


def _search(**fields: Any) -> dict[str, Any]:
    return {
        "id": "example-search",
        "name": "Example search",
        "tier": "T2",
        "sections": ["models"],
        "trust": 3,
        "enabled": True,
        "via": "search",
        "search": {"queries": ["example lab announcements"]} | fields,
    }


def test_search_pages_are_https_urls() -> None:
    assert validate_document(_registry(_search(pages=["https://x.ai/news"])), SOURCES) == []
    assert validate_document(_registry(_search(pages=["http://x.ai/news"])), SOURCES)
    assert validate_document(_registry(_search(pages=["x.ai/news"])), SOURCES)
    twice = ["https://x.ai/a", "https://x.ai/a"]
    assert validate_document(_registry(_search(pages=twice)), SOURCES)
    assert validate_document(_registry(_search()), SOURCES) == []


# --- Collected output (collected/<source-id>.json) ---------------------------------------------


def _item(**fields: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": "example-lab:3f2a9c1e0b4d5a67",
        "source_id": "example-lab",
        "title": "Example launches a model",
        "url": "https://example.com/news/launch?utm_source=feed",
        "canonical_url": "https://example.com/news/launch",
        "published": "2026-10-28T09:00:00Z",
        "undated": False,
        "summary": "A short summary.",
        "signal": None,
        "extra": {},
    }
    return item | fields


def _collected(*items: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": {
            "id": "example-lab",
            "name": "Example Lab",
            "tier": "T1",
            "trust": 4,
            "sections": ["models"],
            "kind": "rss",
            "url": "https://example.com/feed.xml",
        },
        "window": {"since": "2026-10-26T17:00:00Z", "until": "2026-10-29T17:00:00Z"},
        "collected_at": "2026-10-29T17:00:03Z",
        "items": list(items),
    }


def test_collected_document_accepts_dated_and_undated_items() -> None:
    undated = _item(id="example-lab:release-1-2-0", published=None, undated=True)
    assert validate_document(_collected(_item(), undated), COLLECTED) == []
    assert validate_document(_collected(), COLLECTED) == []


@pytest.mark.parametrize(
    "item_id",
    ["example-lab:3f2a9c1e0b4d5a67", "openai-news:3f2a9c1e0b4d5a67", "a:b", "x_y-z:release-1-2-0"],
)
def test_collected_item_ids_are_source_scoped(item_id: str) -> None:
    assert validate_document(_collected(_item(id=item_id)), COLLECTED) == []


@pytest.mark.parametrize(
    "item_id",
    [
        "OpenAI:x",
        "no-colon",
        ":abc",
        "example-lab:",
        "example-lab:A1",
        "example-lab:a_b",
        "example-lab:a:b",
        "example lab:abc",
        f"example-lab:{'a' * 128}",
    ],
)
def test_collected_item_ids_must_be_source_scoped_ascii(item_id: str) -> None:
    assert validate_document(_collected(_item(id=item_id)), COLLECTED)


def test_collected_item_undated_requires_null_published() -> None:
    assert validate_document(_collected(_item(published=None, undated=True)), COLLECTED) == []
    # A dated item must carry a timestamp, and an undated one must not.
    assert validate_document(_collected(_item(published=None, undated=False)), COLLECTED)
    assert validate_document(_collected(_item(undated=True)), COLLECTED)


def test_collected_item_requires_both_date_fields() -> None:
    without_undated = {k: v for k, v in _item().items() if k != "undated"}
    without_published = {k: v for k, v in _item().items() if k != "published"}
    assert validate_document(_collected(without_undated), COLLECTED)
    assert validate_document(_collected(without_published), COLLECTED)


@pytest.mark.parametrize(
    "published",
    ["2026-10-28", "2026-10-28t09:00:00z", "2026-10-28 09:00:00Z", "yesterday", 1790000000],
)
def test_collected_timestamps_need_uppercase_t_and_z(published: object) -> None:
    assert validate_document(_collected(_item(published=published)), COLLECTED)


def test_collected_timestamps_accept_fractions_and_offsets() -> None:
    for stamp in ("2026-10-28T09:00:00.123Z", "2026-10-28T12:00:00+03:00"):
        assert validate_document(_collected(_item(published=stamp)), COLLECTED) == []


@pytest.mark.parametrize(
    "fields",
    [
        {"url": "http://example.com/news/launch"},
        {"canonical_url": "http://example.com/news/launch"},
        {"url": "https://example.com/a b"},
        {"title": ""},
        {"source_id": "Example Lab"},
        {"signal": "12"},
        {"summary": 5},
        {"extra": {"nested": {"a": 1}}},
        {"extra": {"Bad Key": 1}},
        {"extra": {"list": [1]}},
        {"surprise": True},
    ],
    ids=[
        "http-url",
        "http-canonical",
        "url-with-space",
        "empty-title",
        "bad-source-id",
        "string-signal",
        "numeric-summary",
        "nested-extra",
        "extra-key",
        "list-extra",
        "unknown-field",
    ],
)
def test_collected_item_rejects_bad_fields(fields: dict[str, Any]) -> None:
    assert validate_document(_collected(_item(**fields)), COLLECTED)


def test_collected_item_accepts_nullable_and_scalar_values() -> None:
    extra = {"prerelease": False, "stars": 7, "lang": "en", "n": None}
    item = _item(summary=None, signal=12.5, extra=extra)
    assert validate_document(_collected(item), COLLECTED) == []


def test_collected_item_change_and_detected_at() -> None:
    change = {
        "kind": "changed",
        "fields": [{"path": "context_length", "old": 200000, "new": 1000000}],
    }
    item = _item(published=None, undated=True, detected_at="2026-10-29T17:00:01Z", change=change)
    assert validate_document(_collected(item), COLLECTED) == []
    for kind in ("added", "removed", "updated"):
        added = _item(change={"kind": kind, "fields": []})
        assert validate_document(_collected(added), COLLECTED) == []
    renamed = _item(change=change | {"kind": "renamed"})
    assert validate_document(_collected(renamed), COLLECTED)
    no_fields = _item(change={"kind": "added"})
    assert validate_document(_collected(no_fields), COLLECTED)
    half_field = _item(change={"kind": "added", "fields": [{"path": "x"}]})
    assert validate_document(_collected(half_field), COLLECTED)
    assert validate_document(_collected(_item(detected_at="today")), COLLECTED)


def test_collected_source_block_and_window_are_checked() -> None:
    document = _collected(_item())
    source = document["source"]
    assert validate_document(document | {"schema_version": 2}, COLLECTED)
    assert validate_document(document | {"collected_at": "now"}, COLLECTED)
    assert validate_document(document | {"window": {"since": "2026-10-26T17:00:00Z"}}, COLLECTED)
    assert validate_document(document | {"source": source | {"kind": "html"}}, COLLECTED)
    insecure = source | {"url": "http://example.com/f"}
    assert validate_document(document | {"source": insecure}, COLLECTED)
    assert validate_document(document | {"source": source | {"trust": 6}}, COLLECTED)
    assert validate_document(document | {"extra": 1}, COLLECTED)
    for kind in ("rss", "atom", "json", "json-snapshot-diff", "sitemap"):
        assert validate_document(document | {"source": source | {"kind": kind}}, COLLECTED) == []


# --- Collect run summary (collected/collect.json) ----------------------------------------------


def _outcome(**fields: Any) -> dict[str, Any]:
    outcome: dict[str, Any] = {
        "id": "example-lab",
        "status": "ok",
        "sections": ["models"],
        "kind": "rss",
        "http_status": 200,
        "items": 3,
        "items_dropped_window": 1,
        "items_dropped_invalid": 0,
        "duration_ms": 240,
        "from_cache": False,
        "redirected_to": None,
        "note": None,
        "unread": 0,
    }
    return outcome | fields


def _failed(**fields: Any) -> dict[str, Any]:
    return _outcome(status="failed", reason="http_error", http_status=404, items=0) | fields


def _run(*outcomes: dict[str, Any], **fields: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_version": 1,
        "engine_version": "0.1.0",
        "run_date": "2026-10-29",
        "started_at": "2026-10-29T17:00:00Z",
        "updated_at": "2026-10-29T17:00:09Z",
        "window": {"since": "2026-10-26T17:00:00Z", "until": "2026-10-29T17:00:00Z"},
        "options": {"sections": [], "sources": [], "offline": False},
        "sources": list(outcomes),
        "not_collected": [{"id": "claude-code-releases", "via": "mcp", "sections": ["tooling"]}],
    }
    return document | fields


@pytest.mark.parametrize("status", ["ok", "empty"])
def test_outcome_without_reason_is_ok_or_empty(status: str) -> None:
    assert validate_document(_run(_outcome(status=status)), COLLECT_RUN) == []


@pytest.mark.parametrize("status", ["ok", "empty"])
def test_outcome_ok_and_empty_reject_a_reason(status: str) -> None:
    assert validate_document(_run(_outcome(status=status, reason="timeout")), COLLECT_RUN)


@pytest.mark.parametrize("status", ["failed", "skipped"])
def test_outcome_reason_required_for_failed_and_skipped(status: str) -> None:
    assert validate_document(_run(_outcome(status=status)), COLLECT_RUN)
    assert validate_document(_run(_outcome(status=status, reason="timeout")), COLLECT_RUN) == []


REASONS = [
    "http_error",
    "timeout",
    "network_error",
    "rate_limited",
    "robots_disallowed",
    "missing_auth_env",
    "parse_error",
    "invalid_items",
    "too_large",
    "offline_miss",
]


@pytest.mark.parametrize("reason", REASONS)
def test_outcome_accepts_every_documented_reason(reason: str) -> None:
    assert validate_document(_run(_failed(reason=reason)), COLLECT_RUN) == []


@pytest.mark.parametrize("reason", ["http_404", "boom", "", None])
def test_outcome_rejects_other_reasons(reason: object) -> None:
    assert validate_document(_run(_failed(reason=reason)), COLLECT_RUN)


def test_outcome_status_must_be_known() -> None:
    assert validate_document(_run(_outcome(status="partial")), COLLECT_RUN)
    assert validate_document(_run(_failed(status="partial")), COLLECT_RUN)


@pytest.mark.parametrize(
    "fields",
    [
        {"http_status": None},
        {"http_status": 503},
        {"redirected_to": "cdn.example.com"},
        {"redirected_to": "cdn.example.com:8443"},
        {"note": "baseline created"},
        {"unread": 12},
        {"from_cache": True},
        {"kind": "sitemap"},
    ],
)
def test_outcome_accepts_nullable_and_optional_values(fields: dict[str, Any]) -> None:
    assert validate_document(_run(_outcome(**fields)), COLLECT_RUN) == []


@pytest.mark.parametrize(
    "fields",
    [
        {"http_status": "200"},
        {"http_status": 99},
        {"http_status": 600},
        {"items": -1},
        {"items": 1.5},
        {"items_dropped_window": -1},
        {"items_dropped_invalid": -1},
        {"duration_ms": -1},
        {"from_cache": "no"},
        {"redirected_to": "https://cdn.example.com/"},
        {"redirected_to": "CDN example"},
        {"note": 5},
        {"unread": -1},
        {"kind": "html"},
        {"sections": []},
        {"id": "Example Lab"},
        {"surprise": True},
    ],
)
def test_outcome_rejects_bad_values(fields: dict[str, Any]) -> None:
    assert validate_document(_run(_outcome(**fields)), COLLECT_RUN)
    assert validate_document(_run(_failed(**fields)), COLLECT_RUN)


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "status",
        "sections",
        "kind",
        "http_status",
        "items",
        "items_dropped_window",
        "items_dropped_invalid",
        "duration_ms",
        "from_cache",
        "redirected_to",
        "note",
        "unread",
    ],
)
def test_outcome_requires_every_common_field(field: str) -> None:
    outcome = _outcome()
    del outcome[field]
    assert validate_document(_run(outcome), COLLECT_RUN)


def test_run_options_and_not_collected_are_checked() -> None:
    chosen = {"sections": ["models"], "sources": ["example-lab"], "offline": True}
    assert validate_document(_run(_outcome(), options=chosen), COLLECT_RUN) == []
    assert validate_document(_run(_outcome(), options=chosen | {"offline": "yes"}), COLLECT_RUN)
    bad_source = chosen | {"sources": ["Bad Id"]}
    assert validate_document(_run(_outcome(), options=bad_source), COLLECT_RUN)
    no_offline = {"sections": [], "sources": []}
    assert validate_document(_run(_outcome(), options=no_offline), COLLECT_RUN)
    for via in ("mcp", "search"):
        row = {"id": "xai-news", "via": via, "sections": ["models"]}
        assert validate_document(_run(_outcome(), not_collected=[row]), COLLECT_RUN) == []
    bad_via = {"id": "xai-news", "via": "collector", "sections": ["models"]}
    assert validate_document(_run(_outcome(), not_collected=[bad_via]), COLLECT_RUN)
    no_sections = {"id": "xai-news", "via": "mcp"}
    assert validate_document(_run(_outcome(), not_collected=[no_sections]), COLLECT_RUN)


def test_run_header_is_checked() -> None:
    assert validate_document(_run(), COLLECT_RUN) == []
    assert validate_document(_run(schema_version=2), COLLECT_RUN)
    assert validate_document(_run(run_date="29-10-2026"), COLLECT_RUN)
    assert validate_document(_run(updated_at="2026-10-29 17:00:09"), COLLECT_RUN)
    assert validate_document(_run(engine_version=""), COLLECT_RUN)
    assert validate_document(_run(window={"since": "2026-10-26T17:00:00Z"}), COLLECT_RUN)


# --- Shared examples (also parsed by the TypeScript contracts tests) ---------------------------


OUTPUT_EXAMPLES = [("collected", COLLECTED), ("collect-run", COLLECT_RUN)]


def _read_example(example: str, name: str) -> Any:
    return json.loads((EXAMPLES / example / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(("example", "schema"), OUTPUT_EXAMPLES)
def test_minimal_example_is_valid(example: str, schema: str) -> None:
    assert validate_document(_read_example(example, "valid/minimal.json"), schema) == []


@pytest.mark.parametrize(
    ("example", "schema", "patch"),
    [
        pytest.param(example, schema, case["patch"], id=f"{example}: {case['name']}")
        for example, schema in OUTPUT_EXAMPLES
        for case in _read_example(example, "invalid-schema.json")
    ],
)
def test_invalid_example_cases_are_rejected(
    example: str, schema: str, patch: list[dict[str, Any]]
) -> None:
    minimal = _read_example(example, "valid/minimal.json")
    assert validate_document(jsonpatch.apply_patch(minimal, patch), schema)
