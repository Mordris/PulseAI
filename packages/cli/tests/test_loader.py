import json
from pathlib import Path

import pytest
import yaml

from pulseai.registry.loader import (
    RegistryError,
    _expand,  # pyright: ignore[reportPrivateUsage]
    load_catalog,
    load_locale,
    load_registry,
    read_document,
    registry_spec,
)


def _write(path: Path, data: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_loads_engine_sections() -> None:
    reg = load_registry("sections")
    assert [s["id"] for s in reg.data["sections"]][:1] == ["models"]
    assert reg.files and reg.files[0].name == "sections.yaml"


def test_unknown_registry_lists_known_ids() -> None:
    with pytest.raises(RegistryError, match="known: config"):
        registry_spec("nope")


def test_instance_override_patches_by_id(tmp_path: Path) -> None:
    _write(
        tmp_path / "taxonomy/sections.yaml",
        {"schema_version": 1, "sections": [{"id": "models", "order": 99}]},
    )
    reg = load_registry("sections", tmp_path)
    models = next(s for s in reg.data["sections"] if s["id"] == "models")
    assert models["order"] == 99
    assert models["label"] == "sections.models"


def test_instance_can_add_and_remove_sources(tmp_path: Path) -> None:
    _write(
        tmp_path / "sources/registry/mine.yaml",
        {
            "schema_version": 1,
            "sources": [
                {"id": "simon-willison", "_remove": True},
                {
                    "id": "my-blog",
                    "name": "My blog",
                    "tier": "T2",
                    "sections": ["tooling"],
                    "trust": 3,
                    "enabled": True,
                    "via": "collector",
                    "collector": {"kind": "rss", "url": "https://example.org/feed.xml"},
                },
            ],
        },
    )
    ids = [s["id"] for s in load_registry("sources", tmp_path).data["sources"]]
    assert "my-blog" in ids
    assert "simon-willison" not in ids


def test_invalid_instance_override_names_file_and_path(tmp_path: Path) -> None:
    bad = _write(
        tmp_path / "taxonomy/sections.yaml",
        {"schema_version": 1, "sections": [{"id": "models", "order": "first"}]},
    )
    with pytest.raises(RegistryError) as info:
        load_registry("sections", tmp_path)
    message = str(info.value)
    assert str(bad) in message
    assert "sections/0/order" in message


def test_duplicate_ids_across_engine_files_are_rejected(engine_copy: Path) -> None:
    core = yaml.safe_load((engine_copy / "sources/registry/core.yaml").read_text(encoding="utf-8"))
    _write(
        engine_copy / "sources/registry/extra.yaml",
        {"schema_version": 1, "sources": core["sources"][:1]},
    )
    with pytest.raises(RegistryError, match="duplicate id"):
        load_registry("sources")


def test_read_document_handles_bom(tmp_path: Path) -> None:
    path = tmp_path / "x.yaml"
    path.write_bytes("﻿a: 1\n".encode())
    assert read_document(path) == {"a": 1}


def test_read_document_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "x.yaml"
    path.write_text("  \n", encoding="utf-8")
    with pytest.raises(RegistryError, match="empty"):
        read_document(path)


def test_read_document_unsupported_suffix(tmp_path: Path) -> None:
    path = tmp_path / "x.toml"
    path.write_text("a = 1", encoding="utf-8")
    with pytest.raises(RegistryError, match="unsupported file type"):
        read_document(path)


def test_read_document_not_utf8_names_the_file(tmp_path: Path) -> None:
    path = tmp_path / "x.yaml"
    path.write_bytes("a: 1\n".encode("utf-16"))
    with pytest.raises(RegistryError, match="not valid UTF-8") as info:
        read_document(path)
    assert str(path) in str(info.value)


def test_read_document_unreadable_without_strerror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(self: Path, *args: object, **kwargs: object) -> str:
        raise OSError

    monkeypatch.setattr(Path, "read_text", fail)
    path = tmp_path / "x.yaml"
    with pytest.raises(RegistryError, match="cannot read") as info:
        read_document(path)
    assert str(path) in str(info.value)
    assert "None" not in str(info.value)


def test_read_document_yaml_value_error_names_the_file(tmp_path: Path) -> None:
    # PyYAML constructs an unquoted impossible date itself and raises a plain ValueError.
    path = tmp_path / "x.yaml"
    path.write_text("released: 2026-02-30\n", encoding="utf-8")
    with pytest.raises(RegistryError, match="cannot parse") as info:
        read_document(path)
    assert str(path) in str(info.value)


@pytest.mark.parametrize("suffix", [".yaml", ".json"])
def test_read_document_too_deeply_nested_names_the_file(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"x{suffix}"
    path.write_text("[" * 100_000, encoding="utf-8")
    with pytest.raises(RegistryError, match="nested too deeply") as info:
        read_document(path)
    assert str(path) in str(info.value)


def test_expand_reports_a_template_that_format_map_rejects_with_type_error(tmp_path: Path) -> None:
    # "{language[x]}" indexes a string with a string, which raises TypeError.
    with pytest.raises(RegistryError, match="not a valid template"):
        _expand(tmp_path, ["locales/{language[x]}.json"], {"language": "en"})


@pytest.mark.parametrize("language", ["*", "?", "[a]", "../en", "..", "a/b", "a\\b", "/etc/passwd"])
def test_locale_rejects_unsafe_language(language: str) -> None:
    with pytest.raises(RegistryError, match="variable 'language'"):
        load_locale(language)


@pytest.mark.parametrize("template", ["locales/{}.json", "locales/{language.nope}.json"])
def test_invalid_path_template_is_a_registry_error(engine_copy: Path, template: str) -> None:
    catalog_path = engine_copy / "defaults/registries.yaml"
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    next(r for r in catalog["registries"] if r["id"] == "locale")["paths"] = [template]
    _write(catalog_path, catalog)
    with pytest.raises(RegistryError, match="not a valid template"):
        load_locale("en")


def test_locale_falls_back() -> None:
    tr = load_locale("tr")
    en = load_locale("en")
    assert tr["sections.models"] == "Modeller ve laboratuvarlar"
    assert set(en) <= set(tr)


def test_missing_locale_is_an_error() -> None:
    with pytest.raises(RegistryError, match="no engine files"):
        load_locale("xx")


def test_missing_engine_schema_is_a_registry_error(engine_copy: Path) -> None:
    (engine_copy / "schema/sections.schema.json").unlink()
    with pytest.raises(RegistryError, match=r"sections.*sections\.schema\.json"):
        load_registry("sections")


def test_missing_catalog_schema_is_a_registry_error(engine_copy: Path) -> None:
    (engine_copy / "schema/registries.schema.json").unlink()
    with pytest.raises(RegistryError, match=r"registries\.schema\.json"):
        load_catalog()


REGISTRY_FILES = [
    ("sections", "taxonomy/sections.yaml", "sections"),
    ("item-types", "taxonomy/item-types.yaml", "item_types"),
    ("roles", "taxonomy/roles.yaml", "roles"),
    ("sources", "sources/registry/core.yaml", "sources"),
    ("engine", "defaults/engine.yaml", "tools"),
]


def _repeat_first_entry(path: Path, list_key: str) -> str:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc[list_key].append(dict(doc[list_key][0]))
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return str(doc[list_key][0]["id"])


@pytest.mark.parametrize(("registry", "relative", "list_key"), REGISTRY_FILES)
def test_duplicate_ids_within_an_engine_file_are_rejected(
    engine_copy: Path, registry: str, relative: str, list_key: str
) -> None:
    repeated = _repeat_first_entry(engine_copy / relative, list_key)
    with pytest.raises(RegistryError) as info:
        load_registry(registry)
    message = str(info.value)
    assert str(engine_copy / relative) in message
    assert f"duplicate id {repeated!r} in {list_key}" in message


@pytest.mark.parametrize(("registry", "relative", "list_key"), REGISTRY_FILES[:4])
def test_duplicate_ids_within_an_instance_file_are_rejected(
    tmp_path: Path, registry: str, relative: str, list_key: str, repo_root: Path
) -> None:
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text((repo_root / relative).read_text(encoding="utf-8"), encoding="utf-8")
    repeated = _repeat_first_entry(path, list_key)
    with pytest.raises(RegistryError) as info:
        load_registry(registry, tmp_path)
    assert str(path) in str(info.value)
    assert f"duplicate id {repeated!r} in {list_key}" in str(info.value)


def test_every_duplicate_in_every_file_is_listed(engine_copy: Path, tmp_path: Path) -> None:
    _repeat_first_entry(engine_copy / "taxonomy/sections.yaml", "sections")
    path = tmp_path / "taxonomy/sections.yaml"
    _write(
        path,
        {"schema_version": 1, "sections": [{"id": "tooling"}, {"id": "tooling", "order": 1}]},
    )
    with pytest.raises(RegistryError) as info:
        load_registry("sections", tmp_path)
    message = str(info.value)
    assert str(engine_copy / "taxonomy/sections.yaml") in message
    assert str(path) in message
    assert message.count("duplicate id '") == 2


def test_duplicate_group_ids_inside_a_section_are_rejected(tmp_path: Path) -> None:
    group = {"id": "extra", "label": "groups.top_papers", "match": {"types": ["paper"]}}
    _write(
        tmp_path / "taxonomy/sections.yaml",
        {"schema_version": 1, "sections": [{"id": "research", "groups": [group, group]}]},
    )
    with pytest.raises(RegistryError, match=r"duplicate id 'extra' in sections/0/groups"):
        load_registry("sections", tmp_path)


def test_an_instance_can_replace_an_entry_by_removing_and_adding_it(tmp_path: Path) -> None:
    source = {
        "id": "simon-willison",
        "name": "Simon",
        "tier": "T2",
        "sections": ["tooling"],
        "trust": 3,
        "enabled": True,
        "via": "collector",
        "collector": {"kind": "rss", "url": "https://example.org/feed.xml"},
    }
    _write(
        tmp_path / "sources/registry/mine.yaml",
        {"schema_version": 1, "sources": [{"id": "simon-willison", "_remove": True}, source]},
    )
    sources = load_registry("sources", tmp_path).data["sources"]
    assert [s["name"] for s in sources if s["id"] == "simon-willison"] == ["Simon"]


def _german(strings: dict[str, str]) -> dict[str, object]:
    return {"schema_version": 1, "language": "de", "fallback": "en", "strings": strings}


def test_instance_can_add_a_language(tmp_path: Path) -> None:
    (tmp_path / "locales").mkdir()
    (tmp_path / "locales/de.json").write_text(
        json.dumps(_german({"sections.models": "Modelle und Labore"})), encoding="utf-8"
    )
    de = load_locale("de", tmp_path)
    assert de["sections.models"] == "Modelle und Labore"
    assert de["sections.tooling"] == load_locale("en")["sections.tooling"]


def test_a_language_without_any_file_is_an_error_with_an_instance_too(tmp_path: Path) -> None:
    with pytest.raises(RegistryError, match=r"no engine or instance files match locales/xx\.json"):
        load_locale("xx", tmp_path)


def test_the_engine_registry_is_engine_only(tmp_path: Path) -> None:
    instance_file = _write(
        tmp_path / "defaults/engine.yaml",
        {"tool_timeout_seconds": 99, "tools": [{"id": "python", "command": ["sh", "-c", "evil"]}]},
    )
    loaded = load_registry("engine", tmp_path)
    assert instance_file not in loaded.files
    assert loaded.data == load_registry("engine").data
    assert loaded.data["tool_timeout_seconds"] != 99


def test_a_broken_instance_file_for_an_engine_only_registry_is_never_read(tmp_path: Path) -> None:
    (tmp_path / "defaults").mkdir()
    (tmp_path / "defaults/engine.yaml").write_text("{not: [valid", encoding="utf-8")
    assert load_registry("engine", tmp_path).data == load_registry("engine").data


def test_only_the_engine_registry_refuses_instance_files() -> None:
    overridable = {spec.id: spec.instance_overridable for spec in load_catalog().registries}
    assert overridable.pop("engine") is False
    assert all(flag is not False for flag in overridable.values()), overridable
