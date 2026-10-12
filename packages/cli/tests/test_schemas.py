from pathlib import Path
from typing import Any

import pytest

from pulseai.schemas import SchemaRefError, SchemaShapeError, check_references, load_schema


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
