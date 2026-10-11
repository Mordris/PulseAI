import sys
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from pulseai.cli import app
from pulseai.doctor import Finding, Runner, check_tools, doctor

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
    assert "tool:python" in result.output
