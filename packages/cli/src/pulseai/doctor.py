"""Environment and setup checks for `pulse doctor`. Requirements come from defaults/engine.yaml.

The doctor reports problems; it never crashes on a broken requirement, command, or registry.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Literal

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from pulseai.config import unknown_env_overrides
from pulseai.paths import EngineDataError
from pulseai.registry.checks import check_registries
from pulseai.registry.loader import RegistryError, load_catalog, load_registry

PYTHON_TOKEN = "{python}"  # noqa: S105 - command placeholder in the registry, not a secret

Status = Literal["ok", "warn", "fail"]
Runner = Callable[[list[str]], str | None]


@dataclass(frozen=True)
class Finding:
    check: str
    status: Status
    detail: str
    hint: str | None = None


def format_finding(finding: Finding) -> str:
    line = f"{finding.status:4} {finding.check}: {finding.detail}"
    if finding.hint and finding.status != "ok":
        line += f" (hint: {finding.hint})"
    return line


def infrastructure_finding(exc: EngineDataError | RegistryError) -> Finding:
    """The finding for engine data or the registry catalog being unusable."""
    check = "engine:data" if isinstance(exc, EngineDataError) else "registry:catalog"
    return Finding(check, "fail", str(exc))


def run_tool(command: list[str], timeout: float | None = None) -> str | None:
    """Combined stdout/stderr of a version command, or None when it cannot run or times out."""
    try:
        result = subprocess.run(  # noqa: S603 - commands come from the engine registry
            command,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    return f"{result.stdout}\n{result.stderr}"


def _missing(tool: dict[str, Any]) -> Status:
    return "fail" if tool["required"] else "warn"


def _check_tool(tool: dict[str, Any], runner: Runner) -> Finding:
    name = f"tool:{tool['id']}"
    hint: str = tool["hint"]
    problem = _missing(tool)
    try:
        pattern = re.compile(tool["version_regex"])
    except re.error as exc:
        return Finding(name, problem, f"invalid version_regex: {exc}", hint)
    if pattern.groups < 1:
        return Finding(name, problem, "version_regex needs a capture group", hint)
    try:
        specifier = SpecifierSet(tool["specifier"])
    except InvalidSpecifier:
        return Finding(name, problem, f"invalid specifier {tool['specifier']!r}", hint)

    command = [sys.executable if part == PYTHON_TOKEN else part for part in tool["command"]]
    output = runner(command)
    if output is None:
        return Finding(name, problem, "not found or did not respond", hint)
    match = pattern.search(output)
    raw = match.group(1) if match else None
    if raw is None:
        return Finding(name, "warn", "could not read the version", hint)
    try:
        found = Version(raw)
    except InvalidVersion:
        return Finding(name, "warn", f"unrecognized version {raw!r}", hint)
    if found in specifier:
        return Finding(name, "ok", f"{found} ({tool['specifier']})")
    return Finding(name, problem, f"{found} does not satisfy {tool['specifier']}", hint)


def check_tools(tools: list[dict[str, Any]], runner: Runner = run_tool) -> list[Finding]:
    return [_check_tool(tool, runner) for tool in tools]


def doctor(
    instance_dir: Path | None = None,
    runner: Runner | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[Finding]:
    try:
        load_catalog()
    except (EngineDataError, RegistryError) as exc:
        return [infrastructure_finding(exc)]  # nothing else can be checked without the catalog
    findings: list[Finding] = []
    engine_error: str | None = None
    try:
        engine = load_registry("engine", instance_dir).data
    except RegistryError as exc:
        engine_error = str(exc)
        findings.append(Finding("registry:engine", "fail", engine_error))
    else:
        run = runner or partial(run_tool, timeout=engine["tool_timeout_seconds"])
        findings += check_tools(engine["tools"], run)
    for issue in check_registries(instance_dir):
        if issue.where == "load" and issue.message == engine_error:
            continue  # the engine load failure is already reported above
        status: Status = "fail" if issue.level == "error" else "warn"
        findings.append(Finding(f"registry:{issue.where}", status, issue.message))
    unknown = unknown_env_overrides(environ)
    if unknown:
        findings.append(
            Finding("env", "warn", f"unknown overrides: {', '.join(unknown)}", "check for typos")
        )
    return findings
