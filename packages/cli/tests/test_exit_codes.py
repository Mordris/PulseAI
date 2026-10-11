"""The CLI exit-code contract, pinned for every command and every kind of input.

- 0: the input is fine.
- 1: validation issues in input that loaded (doctor: any failing check, because it is a report).
- 2: unusable input: engine data, the registry catalog, config, a registry that fails to load, or
  an unreadable or unparseable file.

Errors go to stderr and warnings to stdout, except the doctor report, which always goes to stdout.
"""

import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
import typer.main
from typer.core import TyperGroup
from typer.testing import CliRunner

from pulseai.cli import app
from pulseai.paths import ENGINE_DATA_ENV

runner = CliRunner()

(
    VALID,
    ISSUE,
    BROKEN_CONFIG,
    NO_ENGINE_DATA,
    BROKEN_CATALOG,
    BROKEN_REPORT,
    BROKEN_LOCALE,
    BROKEN_SECTIONS,
) = (
    "valid",
    "validation-issue",
    "broken-config",
    "no-engine-data",
    "broken-catalog",
    "broken-report",
    "broken-locale",
    "broken-sections",
)


@dataclass(frozen=True)
class Setup:
    instance: Path
    report: Path


@dataclass(frozen=True)
class Expect:
    exit_code: int
    stream: str
    text: str


def _doctor_tools(command: list[str], timeout: float | None = None) -> str | None:
    outputs = {
        "uv": "uv 0.11.5",
        "node": "v24.1.0",
        "pnpm": "12.11.2",
        "claude": "2.1.300 (Claude Code)",
        "git": "git version 2.45.0",
    }
    if command[0] == sys.executable:
        return "Python 3.14.0"
    return outputs.get(Path(command[0]).name)


def _prepare(
    scenario: str,
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> Setup:
    monkeypatch.setattr("pulseai.doctor.run_tool", _doctor_tools)
    instance = tmp_path / "instance"
    instance.mkdir()
    report = repo_root / "schema/examples/report/valid/minimal.json"
    config = instance / "pulse.config.yaml"
    if scenario == ISSUE:
        config.write_text("models_by_role: { intern: x }\n", encoding="utf-8")
        report = tmp_path / "report.json"
        report.write_text("{}", encoding="utf-8")
    elif scenario == BROKEN_CONFIG:
        config.write_text("schedule: { time: '99:99' }\n", encoding="utf-8")
    elif scenario == NO_ENGINE_DATA:
        monkeypatch.setenv(ENGINE_DATA_ENV, str(tmp_path / "nonexistent"))
    elif scenario == BROKEN_CATALOG:
        engine: Path = request.getfixturevalue("engine_copy")
        (engine / "defaults/registries.yaml").write_text("registries: [", encoding="utf-8")
    elif scenario == BROKEN_REPORT:
        report = tmp_path / "report.json"
        report.write_text("{not json", encoding="utf-8")
    elif scenario == BROKEN_LOCALE:
        # An instance override of the default language's locale that is not even JSON.
        (instance / "locales").mkdir()
        (instance / "locales/en.json").write_text("{not json", encoding="utf-8")
    elif scenario == BROKEN_SECTIONS:
        (instance / "taxonomy").mkdir()
        (instance / "taxonomy/sections.yaml").write_text("sections: [", encoding="utf-8")
    return Setup(instance, report)


def _args(*words: str) -> Callable[[Setup], list[str]]:
    return lambda setup: [*words, "--instance", str(setup.instance)]


def _validate_args(setup: Setup) -> list[str]:
    return ["validate", str(setup.report), "--instance", str(setup.instance)]


def _config_cases(valid_text: str) -> dict[str, Expect]:
    # A config is either loadable or unusable: there is no "validation issue" in between.
    return {
        VALID: Expect(0, "stdout", valid_text),
        BROKEN_CONFIG: Expect(2, "stderr", "schedule/time"),
        NO_ENGINE_DATA: Expect(2, "stderr", ENGINE_DATA_ENV),
        BROKEN_CATALOG: Expect(2, "stderr", "registries.yaml"),
    }


COMMANDS: dict[str, tuple[Callable[[Setup], list[str]], dict[str, Expect]]] = {
    "config show": (_args("config", "show"), _config_cases("schedule:")),
    "config check": (_args("config", "check"), _config_cases("Configuration is valid.")),
    "schedule print": (
        _args("schedule", "print", "--host", "actions"),
        _config_cases("cron"),
    ),
    "registry check": (
        _args("registry", "check"),
        {
            VALID: Expect(0, "stdout", "Registries are consistent."),
            ISSUE: Expect(1, "stderr", "unknown role 'intern'"),
            BROKEN_CONFIG: Expect(2, "stderr", "schedule/time"),
            NO_ENGINE_DATA: Expect(2, "stderr", ENGINE_DATA_ENV),
            BROKEN_CATALOG: Expect(2, "stderr", "registries.yaml"),
            BROKEN_LOCALE: Expect(2, "stderr", "locales/en.json"),
            BROKEN_SECTIONS: Expect(2, "stderr", "taxonomy/sections.yaml"),
        },
    ),
    "validate": (
        _validate_args,
        {
            VALID: Expect(0, "stdout", ": valid"),
            ISSUE: Expect(1, "stderr", "error schema: "),
            BROKEN_CONFIG: Expect(2, "stderr", "schedule/time"),
            NO_ENGINE_DATA: Expect(2, "stderr", ENGINE_DATA_ENV),
            BROKEN_CATALOG: Expect(2, "stderr", "registries.yaml"),
            BROKEN_REPORT: Expect(2, "stderr", "error file: "),
        },
    ),
    # The doctor is a report: any failing check is exit 1 and everything goes to stdout.
    "doctor": (
        _args("doctor"),
        {
            VALID: Expect(0, "stdout", "ok   tool:python"),
            ISSUE: Expect(1, "stdout", "fail registry:config/models_by_role/intern"),
            BROKEN_CONFIG: Expect(1, "stdout", "fail registry:load: "),
            NO_ENGINE_DATA: Expect(1, "stdout", f"fail engine:data: {ENGINE_DATA_ENV}"),
            BROKEN_CATALOG: Expect(1, "stdout", "fail registry:catalog: "),
            BROKEN_LOCALE: Expect(1, "stdout", "fail registry:language: "),
            BROKEN_SECTIONS: Expect(1, "stdout", "fail registry:load: "),
        },
    ),
}
NO_INPUT_COMMANDS = {"version"}

CASES = [
    pytest.param(command, scenario, id=f"{command}-{scenario}")
    for command, (_, expectations) in COMMANDS.items()
    for scenario in expectations
]


@pytest.mark.parametrize(("command", "scenario"), CASES)
def test_exit_code_and_stream(
    command: str,
    scenario: str,
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    build_args, expectations = COMMANDS[command]
    expect = expectations[scenario]
    setup = _prepare(scenario, tmp_path, repo_root, monkeypatch, request)
    result = runner.invoke(app, build_args(setup))
    assert result.exception is None or isinstance(result.exception, SystemExit), result.exception
    assert result.exit_code == expect.exit_code, result.output
    streams = {"stdout": result.stdout, "stderr": result.stderr}
    assert expect.text in streams[expect.stream], streams
    other = streams["stderr" if expect.stream == "stdout" else "stdout"]
    assert other == "", streams
    assert "Traceback" not in result.output


def _leaf_commands(group: TyperGroup, prefix: tuple[str, ...] = ()) -> Iterator[str]:
    for name, command in group.commands.items():
        if isinstance(command, TyperGroup):
            yield from _leaf_commands(command, (*prefix, name))
        else:
            yield " ".join((*prefix, name))


def test_every_command_is_in_the_exit_code_matrix() -> None:
    root = typer.main.get_command(app)
    assert isinstance(root, TyperGroup)
    assert set(_leaf_commands(root)) == set(COMMANDS) | NO_INPUT_COMMANDS


def test_the_matrix_covers_every_scenario_for_commands_that_read_input() -> None:
    for command, (_, expectations) in COMMANDS.items():
        assert {VALID, BROKEN_CONFIG, NO_ENGINE_DATA, BROKEN_CATALOG} <= set(expectations), command


NO_INSTANCE_ARGS = {
    "config show": ["config", "show"],
    "config check": ["config", "check"],
    "schedule print": ["schedule", "print", "--host", "actions"],
    "registry check": ["registry", "check"],
    "doctor": ["doctor"],
}


@pytest.mark.parametrize("scenario", [NO_ENGINE_DATA, BROKEN_CATALOG])
@pytest.mark.parametrize("command", [*NO_INSTANCE_ARGS, "validate"])
def test_finding_the_default_instance_never_crashes(
    command: str,
    scenario: str,
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    # Without --instance the CLI reads the catalog just to find the instance in the current
    # directory, before any command logic runs.
    setup = _prepare(scenario, tmp_path, repo_root, monkeypatch, request)
    if scenario == NO_ENGINE_DATA:
        monkeypatch.setenv(ENGINE_DATA_ENV, "/nonexistent")
    args = NO_INSTANCE_ARGS.get(command) or ["validate", str(setup.report)]
    result = runner.invoke(app, args)
    assert result.exception is None or isinstance(result.exception, SystemExit), result.exception
    assert result.exit_code == (1 if command == "doctor" else 2), result.output
    assert "Traceback" not in result.output
