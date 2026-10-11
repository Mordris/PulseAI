import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from pulseai.cli import app
from pulseai.doctor import Finding, Runner, check_tools, doctor, format_finding, run_tool
from pulseai.paths import ENGINE_DATA_ENV

runner = CliRunner()


def _tool(
    tool_id: str, command: list[str], regex: str, spec: str, required: bool
) -> dict[str, Any]:
    return {
        "id": tool_id,
        "command": command,
        "version_regex": regex,
        "specifier": spec,
        "required": required,
        "hint": f"fix {tool_id}",
    }


TOOLS = [
    _tool("python", ["{python}", "--version"], r"Python (\d+\.\d+\.\d+)", ">=3.12", True),
    _tool("claude", ["claude", "--version"], r"(\d+\.\d+\.\d+)", ">=2.1.259", True),
    _tool("extra", ["extra"], r"(\d+\.\d+)", ">=1.0", False),
]


def _fake(outputs: dict[str, str | None]) -> Runner:
    def run(command: list[str]) -> str | None:
        name = "python" if command[0] == sys.executable else Path(command[0]).name
        return outputs.get(name)

    return run


def _status(findings: list[Finding]) -> dict[str, str]:
    return {f.check: f.status for f in findings}


def _write_engine(instance: Path, data: dict[str, Any]) -> None:
    path = instance / "defaults" / "engine.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


PYTHON_OUTPUT = "Python 3.12.3"
PYTHON_REGEX = r"Python (\d+\.\d+\.\d+)"


def test_python_token_uses_running_interpreter() -> None:
    seen: list[list[str]] = []

    def run(command: list[str]) -> str | None:
        seen.append(command)
        return "Python 3.12.3"

    check_tools(TOOLS[:1], run)
    assert seen[0][0] == sys.executable


def test_tool_statuses() -> None:
    outputs = {"python": "Python 3.12.3", "claude": "2.1.220 (Claude Code)", "extra": None}
    findings = check_tools(TOOLS, _fake(outputs))
    assert _status(findings) == {"tool:python": "ok", "tool:claude": "fail", "tool:extra": "warn"}
    claude = next(f for f in findings if f.check == "tool:claude")
    assert claude.hint == "fix claude"


def test_unreadable_version_is_a_warning() -> None:
    findings = check_tools(TOOLS[1:2], _fake({"claude": "something odd"}))
    assert _status(findings) == {"tool:claude": "warn"}


@pytest.mark.parametrize("required", [True, False], ids=["required", "optional"])
@pytest.mark.parametrize(
    ("overrides", "output", "expected"),
    [
        ({"specifier": ">=3.12 totally bogus"}, PYTHON_OUTPUT, "invalid specifier"),
        ({"version_regex": "Python ("}, PYTHON_OUTPUT, "invalid version_regex"),
        ({"version_regex": r"Python \d+\.\d+"}, PYTHON_OUTPUT, "needs a capture group"),
        ({"specifier": ">=4"}, PYTHON_OUTPUT, "does not satisfy >=4"),
        (dict[str, str](), None, "not found or did not respond"),
    ],
    ids=["bad-specifier", "bad-regex", "no-capture-group", "unsatisfied", "no-output"],
)
def test_broken_requirement_is_reported_not_raised(
    overrides: dict[str, str], output: str | None, expected: str, required: bool
) -> None:
    tool = {**TOOLS[0], **overrides, "required": required}
    findings = check_tools([tool], lambda _: output)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.status == ("fail" if required else "warn")
    assert expected in finding.detail
    assert finding.hint == "fix python"


@pytest.mark.parametrize(
    ("regex", "output", "expected"),
    [
        (r"(x)?Python", PYTHON_OUTPUT, "could not read the version"),
        (PYTHON_REGEX, "Python 3.12.3", None),
        (r"(\w+) \d", "Python 3", "unrecognized version 'Python'"),
    ],
    ids=["group-did-not-match", "matches", "not-a-version"],
)
def test_unreadable_versions_do_not_raise(regex: str, output: str, expected: str | None) -> None:
    tool = {**TOOLS[0], "version_regex": regex}
    (finding,) = check_tools([tool], lambda _: output)
    if expected is None:
        assert finding.status == "ok"
    else:
        assert finding.status == "warn"
        assert expected in finding.detail


def test_run_tool_replaces_undecodable_output() -> None:
    code = "import sys; sys.stdout.buffer.write(b'v1.2.3 \\xff\\xfe')"
    output = run_tool([sys.executable, "-c", code], timeout=30)
    assert output is not None
    assert "v1.2.3" in output
    assert "\ufffd" in output


def test_run_tool_never_waits_on_the_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.update(kwargs)
        return subprocess.CompletedProcess(command, 0, "tool 1.0", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert run_tool(["tool"], timeout=3) is not None
    assert seen["stdin"] == subprocess.DEVNULL
    assert seen["timeout"] == 3


def test_run_tool_gives_up_after_the_timeout() -> None:
    assert run_tool([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.2) is None


@pytest.mark.parametrize(
    "command", [["pulse-no-such-command-xyz"], ["bad\0name"]], ids=["missing", "null-byte"]
)
def test_run_tool_returns_none_when_it_cannot_run(command: list[str]) -> None:
    assert run_tool(command, timeout=5) is None


def test_doctor_passes_the_registry_timeout_to_the_default_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    timeouts: list[float | None] = []

    def fake(command: list[str], timeout: float | None = None) -> str | None:
        timeouts.append(timeout)
        return None

    monkeypatch.setattr("pulseai.doctor.run_tool", fake)
    _write_engine(tmp_path, {"tool_timeout_seconds": 7.5})
    findings = doctor(tmp_path, environ={})
    assert timeouts
    assert set(timeouts) == {7.5}
    assert all(
        "not found or did not respond" in f.detail for f in findings if f.check[:5] == "tool:"
    )


def test_broken_engine_registry_is_reported_once(tmp_path: Path) -> None:
    _write_engine(tmp_path, {"tool_timeout_seconds": 0})
    findings = doctor(tmp_path, runner=lambda _: "9.9.9", environ={})
    failures = [f for f in findings if f.status == "fail"]
    assert [f.check for f in failures] == ["registry:engine"]
    assert not any(f.check.startswith("tool:") for f in findings)


def test_doctor_reports_config_errors(tmp_path: Path) -> None:
    (tmp_path / "pulse.config.yaml").write_text("models_by_role: { intern: x }\n", encoding="utf-8")
    findings = doctor(tmp_path, runner=lambda _: "Python 3.99.0", environ={})
    assert any(f.check.startswith("registry") and f.status == "fail" for f in findings)


def test_doctor_warns_on_unknown_env() -> None:
    findings = doctor(None, runner=lambda _: "9.9.9", environ={"PULSE__SCHEDUL__TIME": "1"})
    env = [f for f in findings if f.check == "env"]
    assert env and env[0].status == "warn"
    assert "PULSE__SCHEDUL__TIME" in env[0].detail


def test_cli_doctor_runs() -> None:
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code in (0, 1)
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "tool:python" in result.output


def test_cli_doctor_reports_an_invalid_specifier_without_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("pulseai.doctor.run_tool", lambda *_args, **_kwargs: "Python 3.12.3")
    _write_engine(tmp_path, {"tools": [{"id": "python", "specifier": ">=3.12 totally bogus"}]})
    result = runner.invoke(app, ["doctor", "--instance", str(tmp_path)])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "fail tool:python: invalid specifier" in result.output
    assert "(hint: " in result.output


def test_cli_doctor_reports_an_unreadable_catalog(engine_copy: Path) -> None:
    (engine_copy / "defaults" / "registries.yaml").write_text("registries: [", encoding="utf-8")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert result.output.startswith("fail registry:catalog: ")


def test_format_finding_shows_the_hint_only_for_problems() -> None:
    assert format_finding(Finding("tool:x", "ok", "1.0", "ignored")) == "ok   tool:x: 1.0"
    assert format_finding(Finding("tool:x", "warn", "odd", "try this")) == (
        "warn tool:x: odd (hint: try this)"
    )


def test_missing_engine_data_is_one_finding_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENGINE_DATA_ENV, str(tmp_path / "nowhere"))
    findings = doctor(tmp_path, runner=lambda _: "9.9.9", environ={})
    assert [(f.check, f.status) for f in findings] == [("engine:data", "fail")]
    assert ENGINE_DATA_ENV in findings[0].detail


def test_unreadable_catalog_is_one_finding_not_a_crash(engine_copy: Path, tmp_path: Path) -> None:
    (engine_copy / "defaults" / "registries.yaml").write_text("registries: [", encoding="utf-8")
    findings = doctor(tmp_path, runner=lambda _: "9.9.9", environ={})
    assert [(f.check, f.status) for f in findings] == [("registry:catalog", "fail")]


def test_missing_catalog_schema_is_one_finding_not_a_crash(
    engine_copy: Path, tmp_path: Path
) -> None:
    (engine_copy / "schema" / "registries.schema.json").unlink()
    findings = doctor(tmp_path, runner=lambda _: "9.9.9", environ={})
    assert [(f.check, f.status) for f in findings] == [("registry:catalog", "fail")]
