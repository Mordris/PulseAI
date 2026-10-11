import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _load_script(repo_root: Path) -> ModuleType:
    path = repo_root / "scripts/github/apply_repo_settings.py"
    spec = importlib.util.spec_from_file_location("apply_repo_settings", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["apply_repo_settings"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script(repo_root: Path) -> ModuleType:
    return _load_script(repo_root)


@pytest.fixture
def settings(script: ModuleType) -> dict[str, Any]:
    return script.load_settings(script.SETTINGS_FILE)


def test_settings_file_is_valid(settings: dict[str, Any]) -> None:
    assert settings["topics"]
    assert len(settings["description"]) <= 350


def test_invalid_settings_are_rejected(script: ModuleType, tmp_path: Path) -> None:
    bad = tmp_path / "repository.yml"
    bad.write_text("description: x\ntopics: [Not Valid]\n", encoding="utf-8")
    with pytest.raises(script.SettingsError, match="topics"):
        script.load_settings(bad)


def test_booleans_use_typed_fields(script: ModuleType, settings: dict[str, Any]) -> None:
    patch = script.build_calls(settings, "owner/name")[0]
    argv = patch.argv()
    assert argv[:5] == ["gh", "api", "-X", "PATCH", "repos/owner/name"]
    assert "-F" in argv and "has_discussions=true" in argv
    assert "-f" in argv and any(a.startswith("description=") for a in argv)


def test_topics_call_lists_every_topic(script: ModuleType, settings: dict[str, Any]) -> None:
    topics = next(c for c in script.build_calls(settings, "o/n") if c.endpoint.endswith("/topics"))
    names = [value for key, value in topics.fields if key == "names[]"]
    assert names == settings["topics"]


def test_ruleset_requires_checks_and_pull_requests(
    script: ModuleType, settings: dict[str, Any]
) -> None:
    body = script.ruleset_body(settings)
    types = {rule["type"] for rule in body["rules"]}
    assert {"pull_request", "required_status_checks", "deletion", "non_fast_forward"} <= types
    checks = next(r for r in body["rules"] if r["type"] == "required_status_checks")
    contexts = [c["context"] for c in checks["parameters"]["required_status_checks"]]
    assert contexts == settings["ruleset"]["required_checks"]
    json.dumps(body)


def test_dry_run_never_calls_github(
    script: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(*_: object, **__: object) -> None:
        raise AssertionError("dry run must not execute commands")

    monkeypatch.setattr(script.subprocess, "run", forbidden)
    assert script.main(["--repo", "owner/name", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "repos/owner/name/topics" in out
    assert "rulesets" in out


def test_repo_argument_is_validated(script: ModuleType) -> None:
    with pytest.raises(SystemExit):
        script.main(["--repo", "not-a-repo", "--dry-run"])
