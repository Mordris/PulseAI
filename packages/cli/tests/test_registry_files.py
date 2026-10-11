import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

CONDITIONAL_KEYWORDS = frozenset({"if", "then", "else"})


def _load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)


def _validator(root: Path, name: str) -> Draft202012Validator:
    schema = _load(root / "schema" / name)
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def _schema_files(root: Path) -> list[Path]:
    return sorted((root / "schema").rglob("*.schema.json"))


def _walk_keys(node: Any) -> set[str]:
    if isinstance(node, dict):
        keys = set(node)
        for value in node.values():
            keys |= _walk_keys(value)
        return keys
    if isinstance(node, list):
        return set().union(*(_walk_keys(v) for v in node)) if node else set()
    return set()


def test_every_schema_is_valid_2020_12(repo_root: Path) -> None:
    files = _schema_files(repo_root)
    assert files
    for path in files:
        Draft202012Validator.check_schema(_load(path))


def test_no_conditional_keywords(repo_root: Path) -> None:
    for path in _schema_files(repo_root):
        used = CONDITIONAL_KEYWORDS & _walk_keys(_load(path))
        assert not used, f"{path.name} uses {sorted(used)}; Zod cannot convert if/then/else"


def test_catalog_lists_every_registry_file(repo_root: Path) -> None:
    catalog = _load(repo_root / "defaults/registries.yaml")
    assert list(_validator(repo_root, "registries.schema.json").iter_errors(catalog)) == []
    for spec in catalog["registries"]:
        pattern = spec["paths"][0].replace("{language}", "*")
        matches = sorted(repo_root.glob(pattern))
        assert matches, f"{spec['id']}: nothing matches {pattern}"
        validator = _validator(repo_root, spec["schema"])
        for path in matches:
            errors = [e.message for e in validator.iter_errors(_load(path))]
            assert errors == [], f"{path}: {errors}"


@pytest.mark.parametrize(
    ("module", "root_class"),
    [
        ("registries", "RegistriesCatalog"),
        ("engine", "EngineRegistry"),
        ("sections", "SectionsRegistry"),
        ("item_types", "ItemTypesRegistry"),
        ("roles", "RolesRegistry"),
        ("sources", "SourcesRegistry"),
        ("locale", "Locale"),
    ],
)
def test_generated_registry_models_import(module: str, root_class: str) -> None:
    imported = __import__(f"pulseai.models.{module}", fromlist=[root_class])
    assert hasattr(imported, root_class)
