"""Command-line interface for the PulseAI engine (`pulse`)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml

from pulseai import __version__
from pulseai.config import ConfigError, load_config
from pulseai.issues import Issue, format_issue, has_errors
from pulseai.models.config import PulseConfig
from pulseai.registry.checks import check_registries
from pulseai.registry.loader import registry_spec

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


def resolve_instance(path: Path | None) -> Path | None:
    if path is not None:
        return path
    spec = registry_spec("config")
    markers = spec.instance_paths or spec.paths
    cwd = Path.cwd()
    return cwd if any((cwd / marker).is_file() for marker in markers) else None


def load_config_or_exit(instance: Path | None) -> PulseConfig:
    try:
        return load_config(resolve_instance(instance))
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from None


config_app = typer.Typer(help="Inspect the effective configuration.", no_args_is_help=True)
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show(instance: InstanceOption = None) -> None:
    """Print the effective configuration (defaults + instance + environment) as YAML."""
    cfg = load_config_or_exit(instance)
    effective = cfg.model_dump(mode="json", exclude_unset=True)
    text = yaml.safe_dump(effective, sort_keys=False, allow_unicode=True)
    typer.echo(text, nl=False)


@config_app.command("check")
def config_check(instance: InstanceOption = None) -> None:
    """Validate the effective configuration."""
    load_config_or_exit(instance)
    typer.echo("Configuration is valid.")


def print_issues(issues: list[Issue]) -> None:
    for issue in issues:
        typer.echo(format_issue(issue), err=issue.level == "error")


registry_app = typer.Typer(help="Check registries.", no_args_is_help=True)
app.add_typer(registry_app, name="registry")


@registry_app.command("check")
def registry_check(instance: InstanceOption = None) -> None:
    """Check that registries and config are consistent with each other."""
    issues = check_registries(resolve_instance(instance))
    print_issues(issues)
    if has_errors(issues):
        raise typer.Exit(1)
    typer.echo("Registries are consistent.")
