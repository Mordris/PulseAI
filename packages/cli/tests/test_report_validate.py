import json
from pathlib import Path
from typing import Any

import jsonpatch
import pytest
from typer.testing import CliRunner

from pulseai.cli import app
from pulseai.report import validate as report_validate
from pulseai.report.validate import validate_report
from pulseai.schemas import ITEM_TYPE_SCHEMA_DIR, SchemaShapeError

runner = CliRunner()
TESTS = Path(__file__).parent


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def minimal(repo_root: Path) -> dict[str, Any]:
    return _load(repo_root / "schema/examples/report/valid/minimal.json")


def test_minimal_example_is_valid(minimal: dict[str, Any]) -> None:
    assert validate_report(minimal) == []


def test_invalid_schema_cases_are_rejected(repo_root: Path, minimal: dict[str, Any]) -> None:
    for case in _load(repo_root / "schema/examples/report/invalid-schema.json"):
        issues = validate_report(jsonpatch.apply_patch(minimal, case["patch"]))
        assert issues, case["name"]
        assert all(i.where == "schema" for i in issues), case["name"]


@pytest.mark.parametrize(
    "case", _load(TESTS / "data/report-semantic-cases.json"), ids=lambda c: c["name"]
)
def test_semantic_cases_are_rejected(minimal: dict[str, Any], case: dict[str, Any]) -> None:
    issues = validate_report(jsonpatch.apply_patch(minimal, case["patch"]))
    errors = [f"{i.where}: {i.message}" for i in issues if i.level == "error"]
    assert any(case["expect"] in e for e in errors), errors


def test_disabled_section_with_items_is_an_error(tmp_path: Path, minimal: dict[str, Any]) -> None:
    (tmp_path / "pulse.config.yaml").write_text(
        "sections:\n  models: { enabled: false, max_items: 8 }\n", encoding="utf-8"
    )
    errors = [i.message for i in validate_report(minimal, tmp_path) if i.level == "error"]
    assert any("section 'models' is disabled" in e for e in errors)


def test_too_many_items_is_a_warning(tmp_path: Path, minimal: dict[str, Any]) -> None:
    (tmp_path / "pulse.config.yaml").write_text(
        "sections:\n  research: { enabled: true, max_items: 1 }\n", encoding="utf-8"
    )
    extra = jsonpatch.apply_patch(
        minimal,
        [{"op": "add", "path": "/items/-", "value": {**minimal["items"][1], "id": "second-paper"}}],
    )
    issues = validate_report(extra, tmp_path)
    assert [i for i in issues if i.level == "error"] == []
    assert any(i.level == "warning" and "max_items" in i.message for i in issues)


def test_cli_validate(tmp_path: Path, repo_root: Path) -> None:
    good = repo_root / "schema/examples/report/valid/minimal.json"
    assert runner.invoke(app, ["validate", str(good)]).exit_code == 0
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    result = runner.invoke(app, ["validate", str(bad)])
    assert result.exit_code == 1
    assert "headline" in result.output


def test_missing_detail_schema_is_an_issue(engine_copy: Path, minimal: dict[str, Any]) -> None:
    (engine_copy / "schema/item-types/industry.schema.json").unlink()
    errors = [i for i in validate_report(minimal) if i.level == "error"]
    assert [i.where for i in errors] == ["items/0/detail"]
    assert "industry.schema.json" in errors[0].message


def test_non_object_detail_schema_is_an_issue(
    monkeypatch: pytest.MonkeyPatch, minimal: dict[str, Any]
) -> None:
    real = report_validate.validate_document

    def fake(data: Any, schema_name: str, instance_dir: Path | None = None) -> list[str]:
        if schema_name.startswith(f"{ITEM_TYPE_SCHEMA_DIR}/"):
            msg = f"schema {schema_name!r} must be a JSON object"
            raise SchemaShapeError(msg)
        return real(data, schema_name, instance_dir)

    monkeypatch.setattr(report_validate, "validate_document", fake)
    errors = [i for i in validate_report(minimal) if i.level == "error"]
    assert {i.where for i in errors} == {"items/0/detail", "items/1/detail"}
    assert all("must be a JSON object" in i.message for i in errors)
