from pathlib import Path

import pytest
import yaml

from pulseai.registry.loader import (
    RegistryError,
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


def test_locale_falls_back() -> None:
    tr = load_locale("tr")
    en = load_locale("en")
    assert tr["sections.models"] == "Modeller ve laboratuvarlar"
    assert set(en) <= set(tr)


def test_missing_locale_is_an_error() -> None:
    with pytest.raises(RegistryError, match="no engine files"):
        load_locale("xx")
