import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

POLICY_FLAGS = (
    "dismiss_stale_reviews_on_push",
    "required_review_thread_resolution",
    "require_code_owner_review",
    "require_last_push_approval",
    "strict_required_status_checks_policy",
)


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


def test_ruleset_policy_flags_come_from_settings(
    script: ModuleType, settings: dict[str, Any]
) -> None:
    flipped = copy.deepcopy(settings)
    for flag in POLICY_FLAGS:
        flipped["ruleset"][flag] = not settings["ruleset"][flag]
    rules = {
        rule["type"]: rule["parameters"]
        for rule in script.ruleset_body(flipped)["rules"]
        if "parameters" in rule
    }
    pull_request = rules["pull_request"]
    checks = rules["required_status_checks"]
    assert (
        pull_request["dismiss_stale_reviews_on_push"]
        is flipped["ruleset"]["dismiss_stale_reviews_on_push"]
    )
    assert (
        pull_request["required_review_thread_resolution"]
        is flipped["ruleset"]["required_review_thread_resolution"]
    )
    assert (
        pull_request["require_code_owner_review"] is flipped["ruleset"]["require_code_owner_review"]
    )
    assert (
        pull_request["require_last_push_approval"]
        is flipped["ruleset"]["require_last_push_approval"]
    )
    assert (
        checks["strict_required_status_checks_policy"]
        is flipped["ruleset"]["strict_required_status_checks_policy"]
    )


@pytest.mark.parametrize("flag", POLICY_FLAGS)
def test_ruleset_policy_flags_are_required(
    script: ModuleType, settings: dict[str, Any], tmp_path: Path, flag: str
) -> None:
    incomplete = copy.deepcopy(settings)
    del incomplete["ruleset"][flag]
    path = tmp_path / "repository.yml"
    path.write_text(yaml.safe_dump(incomplete), encoding="utf-8")
    with pytest.raises(script.SettingsError, match=flag):
        script.load_settings(path)


class _FakeGh:
    """Stands in for subprocess.run: records every gh call and answers the rulesets listing."""

    def __init__(self, rulesets: list[dict[str, Any]] | None = None) -> None:
        self.rulesets = rulesets or []
        self.calls: list[tuple[list[str], str | None]] = []
        self.fail_on = ""
        self.stderr = ""
        self.missing_gh = False

    def __call__(self, argv: list[str], input: str | None = None, **_: object) -> Any:
        self.calls.append((argv, input))
        if self.missing_gh:
            raise FileNotFoundError(2, "No such file or directory", "gh")
        if self.fail_on and self.fail_on in argv[4]:
            raise subprocess.CalledProcessError(1, argv, output="", stderr=self.stderr)
        stdout = json.dumps(self.rulesets) if argv[3] == "GET" else ""
        return subprocess.CompletedProcess(argv, 0, stdout, "")

    @property
    def requests(self) -> list[tuple[str, str]]:
        return [(argv[3], argv[4]) for argv, _ in self.calls]


@pytest.fixture
def gh(script: ModuleType, monkeypatch: pytest.MonkeyPatch) -> _FakeGh:
    fake = _FakeGh()
    monkeypatch.setattr(script.subprocess, "run", fake)
    return fake


def test_apply_creates_the_ruleset_when_none_exists(
    script: ModuleType, settings: dict[str, Any], gh: _FakeGh
) -> None:
    assert script.main(["--repo", "owner/name"]) == 0
    assert gh.requests == [
        ("PATCH", "repos/owner/name"),
        ("PUT", "repos/owner/name/topics"),
        ("PUT", "repos/owner/name/private-vulnerability-reporting"),
        ("PUT", "repos/owner/name/vulnerability-alerts"),
        ("GET", "repos/owner/name/rulesets"),
        ("POST", "repos/owner/name/rulesets"),
    ]
    argv, stdin = gh.calls[-1]
    assert argv[-2:] == ["--input", "-"]
    assert stdin is not None
    assert json.loads(stdin) == script.ruleset_body(settings)


def test_apply_updates_the_ruleset_with_the_same_name(
    script: ModuleType, settings: dict[str, Any], gh: _FakeGh
) -> None:
    name = settings["ruleset"]["name"]
    gh.rulesets = [{"id": 3, "name": "other"}, {"id": 7, "name": name}]
    assert script.main(["--repo", "owner/name"]) == 0
    assert gh.requests[-2:] == [
        ("GET", "repos/owner/name/rulesets"),
        ("PUT", "repos/owner/name/rulesets/7"),
    ]
    assert json.loads(gh.calls[-1][1] or "{}") == script.ruleset_body(settings)


def test_failing_gh_call_prints_its_error_and_stops(
    script: ModuleType, gh: _FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    gh.fail_on = "/topics"
    gh.stderr = "gh: Resource not accessible by integration (HTTP 403)"
    assert script.main(["--repo", "owner/name"]) == 1
    captured = capsys.readouterr()
    assert "Resource not accessible by integration (HTTP 403)" in captured.err
    assert "repos/owner/name/topics" in captured.err
    assert gh.requests == [("PATCH", "repos/owner/name"), ("PUT", "repos/owner/name/topics")]


def test_missing_gh_is_reported(
    script: ModuleType, gh: _FakeGh, capsys: pytest.CaptureFixture[str]
) -> None:
    gh.missing_gh = True
    assert script.main(["--repo", "owner/name"]) == 1
    assert "could not run gh" in capsys.readouterr().err
