from pathlib import Path

import pytest
from typer.testing import CliRunner

from pulseai.cli import app
from pulseai.config import ConfigError, load_config, unknown_env_overrides

runner = CliRunner()


def test_defaults_without_instance() -> None:
    cfg = load_config()
    assert cfg.schedule.time == "17:00"
    assert cfg.sections["tooling"].max_items == 10


def test_instance_file_overrides_defaults(tmp_path: Path) -> None:
    (tmp_path / "pulse.config.yaml").write_text("schedule:\n  time: '18:30'\n", encoding="utf-8")
    cfg = load_config(tmp_path)
    assert cfg.schedule.time == "18:30"
    assert cfg.schedule.tz == "Europe/Istanbul"


def test_env_override_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "pulse.config.yaml").write_text("schedule:\n  time: '18:30'\n", encoding="utf-8")
    monkeypatch.setenv("PULSE__SCHEDULE__TIME", "06:15")
    monkeypatch.setenv("PULSE__SECTIONS__MODELS__MAX_ITEMS", "3")
    cfg = load_config(tmp_path)
    assert cfg.schedule.time == "06:15"
    assert cfg.sections["models"].max_items == 3


def test_env_override_invalid_value_names_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PULSE__SCHEDULE__TIME", "99:99")
    with pytest.raises(ConfigError, match="schedule/time"):
        load_config()


def test_unknown_instance_key_names_file(tmp_path: Path) -> None:
    path = tmp_path / "pulse.config.yaml"
    path.write_text("schedul:\n  time: '18:30'\n", encoding="utf-8")
    with pytest.raises(ConfigError) as info:
        load_config(tmp_path)
    assert str(path) in str(info.value)


def test_unknown_env_overrides() -> None:
    env = {"PULSE__SCHEDULE__TIME": "1", "PULSE__SCHEDUL__TIME": "2", "PULSE_NOTIFY_URLS": "x"}
    assert unknown_env_overrides(env) == ["PULSE__SCHEDUL__TIME"]


def test_template_instance_config_is_valid(repo_root: Path) -> None:
    cfg = load_config(repo_root / "templates/instance")
    assert cfg.publish.repo == "your-github-user/pulse-instance"


def test_cli_config_show_prints_effective_yaml(tmp_path: Path) -> None:
    (tmp_path / "pulse.config.yaml").write_text("language: tr\n", encoding="utf-8")
    result = runner.invoke(app, ["config", "show", "--instance", str(tmp_path)])
    assert result.exit_code == 0
    assert "language: tr" in result.output


def test_cli_config_check_fails_with_exit_2(tmp_path: Path) -> None:
    (tmp_path / "pulse.config.yaml").write_text("language: english\n", encoding="utf-8")
    result = runner.invoke(app, ["config", "check", "--instance", str(tmp_path)])
    assert result.exit_code == 2
    assert "language" in result.output
