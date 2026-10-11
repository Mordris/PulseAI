import copy
import json
from pathlib import Path
from typing import Any

import jsonpatch
import pytest
from typer.testing import CliRunner

from pulseai.cli import app
from pulseai.issues import Issue
from pulseai.paths import ENGINE_DATA_ENV
from pulseai.report.validate import validate_report, validate_report_file

runner = CliRunner()
TESTS = Path(__file__).parent


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _errors(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.level == "error"]


def _config(directory: Path, text: str) -> None:
    (directory / "pulse.config.yaml").write_text(text, encoding="utf-8")


def _routed(minimal: dict[str, Any], source: int, item_id: str, **fields: Any) -> dict[str, Any]:
    """A copy of one of the minimal report's items with a new id and no visuals (ids are unique)."""
    return {**copy.deepcopy(minimal["items"][source]), "id": item_id, "visuals": [], **fields}


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
    errors = [i.message for i in _errors(validate_report(minimal, tmp_path))]
    assert errors == ["section 'models' is disabled but has 1 item"]


def test_primary_tiers_come_from_the_config(tmp_path: Path, minimal: dict[str, Any]) -> None:
    assert validate_report(minimal, tmp_path) == []
    _config(tmp_path, "quality:\n  primary_tiers: [T1-data]\n")
    errors = _errors(validate_report(minimal, tmp_path))
    assert errors
    assert {i.where for i in errors} <= {"items/0", "items/1"}
    assert {i.message for i in errors} == {
        "confirmed items need a primary source of tier T1-data",
    }


def test_a_wider_primary_tier_list_accepts_more_sources(
    tmp_path: Path, minimal: dict[str, Any]
) -> None:
    for item in minimal["items"]:
        for source in item["sources"]:
            source["tier"] = "T2"
    assert _errors(validate_report(minimal, tmp_path))
    _config(tmp_path, "quality:\n  primary_tiers: [T1, T1-data, T2]\n")
    assert validate_report(minimal, tmp_path) == []


def test_the_default_message_names_the_configured_tiers(minimal: dict[str, Any]) -> None:
    minimal["items"][0]["sources"][0]["kind"] = "secondary"
    messages = [i.message for i in _errors(validate_report(minimal))]
    assert "confirmed items need a primary source of tier T1 or T1-data" in messages


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


@pytest.mark.parametrize(
    ("content", "problem"),
    [
        (b"{not json", "Expecting property name"),
        (b'{"type": "nonsense"}', "'nonsense' is not valid"),
        (b"\xff\xfe\x00", "codec can't decode"),
    ],
    ids=["not-json", "invalid-schema", "not-utf8"],
)
def test_broken_detail_schema_is_an_issue(
    tmp_path: Path, minimal: dict[str, Any], content: bytes, problem: str
) -> None:
    broken = tmp_path / "schema/item-types/industry.schema.json"
    broken.parent.mkdir(parents=True)
    broken.write_bytes(content)
    errors = _errors(validate_report(minimal, tmp_path))
    assert [i.where for i in errors] == ["items/0/detail"]
    assert str(broken) in errors[0].message
    assert problem in errors[0].message


def _write_industry_schema(directory: Path, schema: dict[str, Any]) -> Path:
    path = directory / "schema/item-types/industry.schema.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(schema), encoding="utf-8")
    return path


def test_unresolvable_ref_in_a_detail_schema_is_an_issue(
    tmp_path: Path, minimal: dict[str, Any]
) -> None:
    broken = _write_industry_schema(
        tmp_path,
        {"type": "object", "properties": {"who": {"$ref": "#/$defs/missing"}}},
    )
    errors = _errors(validate_report(minimal, tmp_path))
    assert [i.where for i in errors] == ["items/0/detail"]
    assert str(broken) in errors[0].message
    assert "unresolvable $ref '#/$defs/missing'" in errors[0].message


def test_unreadable_detail_schema_is_an_issue(
    tmp_path: Path, minimal: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = _write_industry_schema(tmp_path, {"type": "object"})
    real_read_text = Path.read_text

    def read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        if self == broken:
            raise PermissionError(13, "Permission denied")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    errors = _errors(validate_report(minimal, tmp_path))
    assert [i.where for i in errors] == ["items/0/detail"]
    assert str(broken) in errors[0].message
    assert "cannot read (Permission denied)" in errors[0].message


REPORTED_MAIN = "confidence:\n  reported: main\n"
REPORTED_EXCLUDE = "confidence:\n  reported: exclude\n"
ROUTING_CASES = [
    # (id, config, destination, item confidence, expected error substring or None)
    ("signal-reported-default", None, "signals", "reported", None),
    (
        "signal-confirmed",
        None,
        "signals",
        "confirmed",
        "confirmed items belong in items, not signals",
    ),
    (
        "signal-rumor-excluded",
        None,
        "signals",
        "rumor",
        "rumors are excluded (confidence.rumor = exclude)",
    ),
    (
        "item-reported-signals-box",
        None,
        "items",
        "reported",
        "reported items go in signals (confidence.reported = signals_box)",
    ),
    ("item-rumor", None, "items", "rumor", "rumors never go in items"),
    ("signal-rumor-signals-box", "confidence:\n  rumor: signals_box\n", "signals", "rumor", None),
    (
        "item-reported-exclude",
        REPORTED_EXCLUDE,
        "items",
        "reported",
        "reported items are excluded (confidence.reported = exclude)",
    ),
    (
        "signal-reported-exclude",
        REPORTED_EXCLUDE,
        "signals",
        "reported",
        "reported items are excluded (confidence.reported = exclude)",
    ),
    ("item-reported-main", REPORTED_MAIN, "items", "reported", None),
    (
        "signal-reported-main",
        REPORTED_MAIN,
        "signals",
        "reported",
        "reported items go in items (confidence.reported = main)",
    ),
]


@pytest.mark.parametrize(
    ("config", "destination", "confidence", "expected"),
    [pytest.param(*case[1:], id=case[0]) for case in ROUTING_CASES],
)
def test_confidence_routing(
    tmp_path: Path,
    minimal: dict[str, Any],
    config: str | None,
    destination: str,
    confidence: str,
    expected: str | None,
) -> None:
    if config:
        _config(tmp_path, config)
    report = copy.deepcopy(minimal)
    report[destination].append(_routed(minimal, 0, "routed-item", confidence=confidence))
    issues = validate_report(report, tmp_path)
    if expected is None:
        assert issues == []
        return
    assert [(i.level, i.where) for i in issues] == [
        ("error", f"{destination}/{len(report[destination]) - 1}")
    ]
    assert expected in issues[0].message


def test_shared_checks_run_on_signals(minimal: dict[str, Any]) -> None:
    signal = _routed(minimal, 0, "example-co-launch", confidence="reported", section="weather")
    signal["facts"][0]["source_ref"] = 5
    table = {**minimal["items"][0]["visuals"][0], "id": "signal-table", "rows": [["EU", "extra"]]}
    signal["visuals"] = [table]
    del signal["detail"]["who"]
    minimal["signals"].append(signal)
    found = {(i.where, i.message) for i in _errors(validate_report(minimal))}
    assert ("signals/0/section", "unknown section 'weather'") in found
    assert ("items", "duplicate item id 'example-co-launch'") in found
    assert any(w == "signals/0/detail" and "who" in m for w, m in found), found
    assert any(w == "signals/0/facts/0/source_ref" for w, _ in found), found
    assert ("signals/0/visuals/0/rows/0", "2 cells, expected 1") in found


@pytest.mark.parametrize(
    ("patch", "where"),
    [
        ([{"op": "replace", "path": "/tldr/0/item_id", "value": "signal-paper"}], "tldr/0/item_id"),
        (
            [{"op": "replace", "path": "/action_list/0/item_id", "value": "signal-paper"}],
            "action_list/0/item_id",
        ),
        (
            [
                {
                    "op": "add",
                    "path": "/adoption_radar/-",
                    "value": {"item_id": "signal-paper", "ring": "assess", "rationale": "Watch."},
                }
            ],
            "adoption_radar/0/item_id",
        ),
        (
            [{"op": "replace", "path": "/featured/paper_of_the_day", "value": "signal-paper"}],
            "featured/paper_of_the_day",
        ),
    ],
    ids=["tldr", "action_list", "adoption_radar", "featured"],
)
def test_references_never_resolve_to_signals(
    minimal: dict[str, Any], patch: list[dict[str, Any]], where: str
) -> None:
    minimal["signals"].append(_routed(minimal, 1, "signal-paper", confidence="reported"))
    issues = _errors(validate_report(jsonpatch.apply_patch(minimal, patch)))
    assert [(i.where, i.message) for i in issues] == [
        (where, "item 'signal-paper' is a signal; references must point at a published item")
    ]


def test_signals_count_toward_a_disabled_section(tmp_path: Path, minimal: dict[str, Any]) -> None:
    _config(tmp_path, "sections:\n  tooling: { enabled: false, max_items: 10 }\n")
    signal = _routed(minimal, 0, "tooling-signal", section="tooling", confidence="reported")
    minimal["signals"].append(signal)
    issues = _errors(validate_report(minimal, tmp_path))
    assert [(i.where, i.message) for i in issues] == [
        ("signals", "section 'tooling' is disabled but has 1 signal")
    ]


def test_disabled_section_message_counts_items_and_signals(
    tmp_path: Path, minimal: dict[str, Any]
) -> None:
    _config(tmp_path, "sections:\n  models: { enabled: false, max_items: 8 }\n")
    minimal["items"].append(_routed(minimal, 0, "second-launch"))
    minimal["signals"].append(_routed(minimal, 0, "signal-launch", confidence="reported"))
    issues = _errors(validate_report(minimal, tmp_path))
    assert [(i.where, i.message) for i in issues] == [
        ("items", "section 'models' is disabled but has 2 items and 1 signal")
    ]


def test_unknown_section_is_not_also_reported_disabled(minimal: dict[str, Any]) -> None:
    minimal["items"][0]["section"] = "weather"
    issues = _errors(validate_report(minimal))
    assert [(i.where, i.message) for i in issues] == [
        ("items/0/section", "unknown section 'weather'")
    ]


@pytest.mark.parametrize(
    "content",
    [
        "{}".encode("utf-16"),
        b"{broken",
        b'{"schema_version": NaN}',
        b'{"schema_version": Infinity}',
        b'{"schema_version": -Infinity}',
        b'{"schema_version": 1e999}',
        b'{"schema_version": -1e999}',
        b"[" * 100_000,
    ],
    ids=[
        "utf-16",
        "malformed",
        "nan",
        "infinity",
        "negative-infinity",
        "overflow",
        "negative-overflow",
        "too-deep",
    ],
)
def test_unreadable_report_file_is_a_file_issue(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "report.json"
    path.write_bytes(content)
    issues = validate_report_file(path)
    assert [(i.where, i.unusable) for i in issues] == [("file", True)]
    result = runner.invoke(app, ["validate", str(path)])
    assert result.exit_code == 2
    assert "error file:" in result.stderr


def test_recursion_while_checking_a_report_is_a_file_issue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repo_root: Path
) -> None:
    # Python 3.12's JSON parser accepts nesting deeper than the Python-level checks can walk.
    def too_deep(*_args: object) -> str | None:
        raise RecursionError

    monkeypatch.setattr("pulseai.report.validate.validate_report", too_deep)
    good = repo_root / "schema/examples/report/valid/minimal.json"
    issues = validate_report_file(good)
    assert [(i.where, i.unusable) for i in issues] == [("file", True)]
    assert "nested too deeply" in issues[0].message


def test_missing_report_file_is_a_file_issue(tmp_path: Path) -> None:
    issues = validate_report_file(tmp_path / "missing.json")
    assert [(i.where, i.unusable) for i in issues] == [("file", True)]


def test_validation_problems_are_not_unusable(minimal: dict[str, Any]) -> None:
    minimal["items"][0]["section"] = "weather"
    issues = validate_report(minimal)
    assert issues
    assert not any(i.unusable for i in issues)


def test_unusable_config_is_a_load_issue_not_a_validation_issue(
    tmp_path: Path, minimal: dict[str, Any]
) -> None:
    _config(tmp_path, "schedule: { time: '99:99' }\n")
    issues = validate_report(minimal, tmp_path)
    assert [(i.where, i.unusable) for i in issues] == [("load", True)]


def test_missing_engine_data_is_a_load_issue(
    tmp_path: Path, minimal: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENGINE_DATA_ENV, str(tmp_path / "nowhere"))
    issues = validate_report(minimal, tmp_path)
    assert [(i.where, i.unusable) for i in issues] == [("load", True)]
    assert ENGINE_DATA_ENV in issues[0].message


def test_missing_engine_report_schema_is_a_load_issue(
    engine_copy: Path, minimal: dict[str, Any]
) -> None:
    (engine_copy / "schema/report.schema.json").unlink()
    issues = validate_report(minimal)
    assert [(i.where, i.unusable) for i in issues] == [("load", True)]
    assert "report.schema.json" in issues[0].message
