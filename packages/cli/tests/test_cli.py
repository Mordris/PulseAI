from typer.testing import CliRunner

from pulseai import __version__
from pulseai.cli import app

runner = CliRunner()


def test_version_option_prints_package_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"pulse {__version__}"


def test_version_comes_from_installed_metadata() -> None:
    assert not __version__.endswith("+unknown")
