"""Environment and setup checks for `pulse doctor`. Requirements come from defaults/engine.yaml."""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from pulseai.config import unknown_env_overrides
from pulseai.registry.checks import check_registries
from pulseai.registry.loader import RegistryError, load_registry

PYTHON_TOKEN = "{python}"  # noqa: S105 - command placeholder in the registry, not a secret
TOOL_TIMEOUT_SECONDS = 15

Status = Literal["ok", "warn", "fail"]
Runner = Callable[[list[str]], str | None]


@dataclass(frozen=True)
class Finding:
    check: str
    status: Status
    detail: str
    hint: str | None = None


def run_tool(command: list[str]) -> str | None:
    """Combined stdout/stderr of a version command, or None when it cannot run."""
    try:
        result = subprocess.run(  # noqa: S603 - commands come from the engine registry
            command, capture_output=True, text=True, timeout=TOOL_TIMEOUT_SECONDS, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return f"{result.stdout}\n{result.stderr}"


def _missing(tool: dict[str, Any]) -> Status:
    return "fail" if tool["required"] else "warn"


def check_tools(tools: list[dict[str, Any]], runner: Runner = run_tool) -> list[Finding]:
    findings: list[Finding] = []
    for tool in tools:
        name = f"tool:{tool['id']}"
        command = [sys.executable if part == PYTHON_TOKEN else part for part in tool["command"]]
        output = runner(command)
        if output is None:
            findings.append(Finding(name, _missing(tool), "not found", tool["hint"]))
            continue
        match = re.search(tool["version_regex"], output)
        if match is None:
            findings.append(Finding(name, "warn", "could not read the version", tool["hint"]))
            continue
        try:
            found = Version(match.group(1))
        except InvalidVersion:
            findings.append(
                Finding(name, "warn", f"unrecognized version {match.group(1)!r}", tool["hint"])
            )
            continue
        if found in SpecifierSet(tool["specifier"]):
            findings.append(Finding(name, "ok", f"{found} ({tool['specifier']})"))
        else:
            detail = f"{found} does not satisfy {tool['specifier']}"
            findings.append(Finding(name, _missing(tool), detail, tool["hint"]))
    return findings


def doctor(
    instance_dir: Path | None = None,
    runner: Runner = run_tool,
    environ: Mapping[str, str] | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    try:
        tools = load_registry("engine", instance_dir).data["tools"]
        findings += check_tools(tools, runner)
    except RegistryError as exc:
        findings.append(Finding("registry:engine", "fail", str(exc)))
    for issue in check_registries(instance_dir):
        status: Status = "fail" if issue.level == "error" else "warn"
        findings.append(Finding(f"registry:{issue.where}", status, issue.message))
    unknown = unknown_env_overrides(environ)
    if unknown:
        findings.append(
            Finding("env", "warn", f"unknown overrides: {', '.join(unknown)}", "check for typos")
        )
    return findings
