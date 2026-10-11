"""Command-line interface for the PulseAI engine (`pulse`)."""

from __future__ import annotations

import functools
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import typer
import yaml

from pulseai import __version__
from pulseai.config import ConfigError, load_config
from pulseai.doctor import doctor as run_doctor
from pulseai.doctor import format_finding, infrastructure_finding
from pulseai.issues import Issue, format_issue, has_errors, is_unusable
from pulseai.paths import EngineDataError
from pulseai.registry.checks import check_registries
from pulseai.registry.loader import RegistryError, registry_spec
from pulseai.report.validate import validate_report_file
from pulseai.schedule import HOSTS, render_host

# Exit codes: 0 fine; 1 validation issues in input that loaded (doctor: any failing check);
# 2 unusable input (engine data, catalog, config, registries that fail to load, unreadable files).
EXIT_ISSUES = 1
EXIT_UNUSABLE = 2

app = typer.Typer(
    name="pulse",
    no_args_is_help=True,
    add_completion=False,
    help="PulseAI engine: check configuration, registries, reports, and schedules.",
)


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"pulse {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_show_version, is_eager=True, help="Show the version and exit."
    ),
) -> None:
    """PulseAI engine CLI."""


@app.command("version")
def version_command() -> None:
    """Show the version."""
    typer.echo(f"pulse {__version__}")


InstanceOption = Annotated[
    Path | None,
    typer.Option(
        "--instance",
        "-i",
        help=(
            "Instance directory. Defaults to the current directory when it has an instance config."
        ),
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
]


def unusable_input_exits[**P, R](command: Callable[P, R]) -> Callable[P, R]:
    """Run a command; engine data, catalog, registry, or config failures end it with exit 2.

    Every command that reads engine data or an instance is wrapped, so none can print a traceback
    for input it cannot use.
    """

    @functools.wraps(command)
    def run(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return command(*args, **kwargs)
        except (EngineDataError, RegistryError, ConfigError) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(EXIT_UNUSABLE) from None

    return run


def resolve_instance(path: Path | None) -> Path | None:
    if path is not None:
        return path
    spec = registry_spec("config")
    markers = spec.instance_paths or spec.paths
    cwd = Path.cwd()
    return cwd if any((cwd / marker).is_file() for marker in markers) else None


config_app = typer.Typer(help="Inspect the effective configuration.", no_args_is_help=True)
app.add_typer(config_app, name="config")


@config_app.command("show")
@unusable_input_exits
def config_show(instance: InstanceOption = None) -> None:
    """Print the effective configuration (defaults + instance + environment) as YAML."""
    cfg = load_config(resolve_instance(instance))
    effective = cfg.model_dump(mode="json", exclude_unset=True)
    text = yaml.safe_dump(effective, sort_keys=False, allow_unicode=True)
    typer.echo(text, nl=False)


@config_app.command("check")
@unusable_input_exits
def config_check(instance: InstanceOption = None) -> None:
    """Validate the effective configuration."""
    load_config(resolve_instance(instance))
    typer.echo("Configuration is valid.")


def print_issues(issues: list[Issue]) -> None:
    for issue in issues:
        typer.echo(format_issue(issue), err=issue.level == "error")


def exit_for(issues: list[Issue]) -> None:
    """Print the issues, then exit 2 for unusable input or 1 for validation errors."""
    print_issues(issues)
    if is_unusable(issues):
        raise typer.Exit(EXIT_UNUSABLE)
    if has_errors(issues):
        raise typer.Exit(EXIT_ISSUES)


registry_app = typer.Typer(help="Check registries.", no_args_is_help=True)
app.add_typer(registry_app, name="registry")


@registry_app.command("check")
@unusable_input_exits
def registry_check(instance: InstanceOption = None) -> None:
    """Check that registries and config are consistent with each other."""
    exit_for(check_registries(resolve_instance(instance)))
    typer.echo("Registries are consistent.")


@app.command("validate")
@unusable_input_exits
def validate_command(
    report: Annotated[
        Path, typer.Argument(exists=True, dir_okay=False, help="report.json to check")
    ],
    instance: InstanceOption = None,
) -> None:
    """Validate a report.json against the schemas, registries, and config."""
    exit_for(validate_report_file(report, resolve_instance(instance)))
    typer.echo(f"{report}: valid")


@app.command("doctor")
def doctor_command(instance: InstanceOption = None) -> None:
    """Check tools, versions, registries, config, and environment overrides.

    The doctor is a report: problems with the engine data or catalog are findings, not crashes,
    and any failing check exits 1.
    """
    try:
        findings = run_doctor(resolve_instance(instance))
    except (EngineDataError, RegistryError) as exc:
        findings = [infrastructure_finding(exc)]
    for finding in findings:
        typer.echo(format_finding(finding))
    if any(f.status == "fail" for f in findings):
        raise typer.Exit(EXIT_ISSUES)


schedule_app = typer.Typer(help="Show scheduler settings for each host.", no_args_is_help=True)
app.add_typer(schedule_app, name="schedule")


def require_time_zone(name: str) -> None:
    """Exit with code 2 unless `name` is a known IANA time zone."""
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        typer.echo(f"unknown time zone {name!r}", err=True)
        raise typer.Exit(EXIT_UNUSABLE) from None


@schedule_app.command("print")
@unusable_input_exits
def schedule_print(
    host: Annotated[str, typer.Option("--host", help=f"One of: {', '.join(HOSTS)}")],
    machine_tz: Annotated[
        str | None, typer.Option("--machine-tz", help="Machine time zone (launchd only).")
    ] = None,
    instance: InstanceOption = None,
) -> None:
    """Print the schedule for a host, derived from schedule.time and schedule.tz."""
    if host not in HOSTS:
        typer.echo(f"unknown host {host!r}; choose one of: {', '.join(HOSTS)}", err=True)
        raise typer.Exit(EXIT_UNUSABLE)
    cfg = load_config(resolve_instance(instance))
    zone = machine_tz or cfg.schedule.tz
    require_time_zone(cfg.schedule.tz)
    require_time_zone(zone)
    typer.echo(render_host(cfg.schedule, host, date.today(), zone), nl=False)
