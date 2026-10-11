from pathlib import Path

import pytest

from pulseai.schemas import SchemaShapeError, load_schema


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
