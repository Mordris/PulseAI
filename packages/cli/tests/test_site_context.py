import json
from pathlib import Path

from typer.testing import CliRunner

from pulseai import __version__
from pulseai.cli import app
from pulseai.site.context import build_site_context, default_context_path

runner = CliRunner()


def _instance(tmp_path: Path, config: str) -> Path:
    instance = tmp_path / "instance"
    instance.mkdir()
    (instance / "pulse.config.yaml").write_text(config, encoding="utf-8")
    return instance


def test_context_holds_config_registries_strings_and_schemas() -> None:
    context = build_site_context()
    assert context["schema_version"] == 1
    assert context["engine_version"] == __version__
    assert context["config"]["language"] == "en"
    orders = [s["order"] for s in context["sections"]]
    assert orders == sorted(orders)
    assert {t["id"] for t in context["item_types"]} >= {"paper", "repo", "industry"}
    assert context["strings"]["sections.models"] == "Models and labs"
    assert "report.schema.json" in context["schemas"]
    assert "item-types/paper.schema.json" in context["schemas"]
    assert context["schemas"]["item-types/release.schema.json"]["title"] == "ReleaseDetail"


def test_instance_config_and_language_reach_the_context(tmp_path: Path) -> None:
    instance = _instance(tmp_path, "language: tr\ntheme:\n  preset: paper\n")
    context = build_site_context(instance)
    assert context["config"]["theme"]["preset"] == "paper"
    assert context["strings"]["sections.models"] == "Modeller ve laboratuvarlar"
    # Strings tr does not translate fall back to en.
    assert all(isinstance(value, str) for value in context["strings"].values())


def test_instance_item_type_schema_wins(tmp_path: Path, repo_root: Path) -> None:
    instance = _instance(tmp_path, "language: en\n")
    target = instance / "schema" / "item-types"
    target.mkdir(parents=True)
    schema = json.loads((repo_root / "schema/item-types/industry.schema.json").read_text())
    schema["description"] = "Instance copy"
    (target / "industry.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    context = build_site_context(instance)
    assert context["schemas"]["item-types/industry.schema.json"]["description"] == "Instance copy"


def test_cli_writes_the_default_path(tmp_path: Path) -> None:
    instance = _instance(tmp_path, "language: en\n")
    result = runner.invoke(app, ["site", "context", "--instance", str(instance)])
    assert result.exit_code == 0, result.output
    path = default_context_path(instance)
    assert path == instance / ".pulse" / "site-context.json"
    assert json.loads(path.read_text(encoding="utf-8"))["schema_version"] == 1
    assert str(path) in result.output


def test_cli_honours_out(tmp_path: Path) -> None:
    out = tmp_path / "custom" / "context.json"
    result = runner.invoke(app, ["site", "context", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert out.is_file()


def test_cli_refuses_inconsistent_registries(engine_copy: Path, tmp_path: Path) -> None:
    locale = engine_copy / "locales" / "en.json"
    doc = json.loads(locale.read_text(encoding="utf-8"))
    del doc["strings"]["sections.models"]
    locale.write_text(json.dumps(doc), encoding="utf-8")
    out = tmp_path / "context.json"
    result = runner.invoke(app, ["site", "context", "--out", str(out)])
    assert result.exit_code == 1
    assert "missing locale string 'sections.models'" in result.output
    assert not out.exists()


def test_cli_missing_report_schema_is_unusable(engine_copy: Path, tmp_path: Path) -> None:
    (engine_copy / "schema" / "report.schema.json").unlink()
    result = runner.invoke(app, ["site", "context", "--out", str(tmp_path / "c.json")])
    assert result.exit_code == 2
    assert "cannot use schema 'report.schema.json'" in result.output


def test_examples_is_a_demo_instance(repo_root: Path) -> None:
    context = build_site_context(repo_root / "examples")
    assert context["config"]["site"]["url"] == "https://mordris.github.io/PulseAI/"
