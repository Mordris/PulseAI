import json
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
    with pytest.raises(ConfigError, match=r"PULSE__SCHEDULE__TIME \(schedule/time\): ") as info:
        load_config()
    assert "environment overrides are invalid" in str(info.value)


def test_env_override_nested_keys_name_the_whole_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PULSE__SECTIONS__MODELS__MAX_ITEMS", "many")
    with pytest.raises(ConfigError) as info:
        load_config()
    assert "PULSE__SECTIONS__MODELS__MAX_ITEMS (sections/models/max_items): " in str(info.value)


def test_env_override_rejected_by_the_schema_names_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The generated model accepts repeated values; only the JSON Schema (uniqueItems) rejects them.
    monkeypatch.setenv("PULSE__INTERESTS__HIGH", '["a", "a"]')
    with pytest.raises(ConfigError) as info:
        load_config()
    message = str(info.value)
    assert "after environment overrides" in message
    assert "PULSE__INTERESTS__HIGH (interests/high): " in message


def test_env_override_list_item_errors_name_the_variable_not_an_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The whole list is one variable; the index belongs in the field path only.
    monkeypatch.setenv("PULSE__INTERESTS__HIGH", "[1]")
    with pytest.raises(ConfigError) as info:
        load_config()
    message = str(info.value)
    assert "PULSE__INTERESTS__HIGH (interests/high/0): " in message
    assert "PULSE__INTERESTS__HIGH__0" not in message


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


def test_primary_tiers_default_and_override(tmp_path: Path) -> None:
    assert load_config().quality.primary_tiers == ["T1", "T1-data"]
    (tmp_path / "pulse.config.yaml").write_text(
        "quality:\n  primary_tiers: [T1]\n", encoding="utf-8"
    )
    assert load_config(tmp_path).quality.primary_tiers == ["T1"]


@pytest.mark.parametrize("value", ["[]", "[T1, T1]", "[T9]"], ids=["empty", "repeated", "unknown"])
def test_invalid_primary_tiers_are_rejected(tmp_path: Path, value: str) -> None:
    (tmp_path / "pulse.config.yaml").write_text(
        f"quality:\n  primary_tiers: {value}\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="primary_tiers"):
        load_config(tmp_path)


def test_feed_items_default_and_override(tmp_path: Path) -> None:
    assert load_config().site.feed_items == 30
    (tmp_path / "pulse.config.yaml").write_text("site:\n  feed_items: 7\n", encoding="utf-8")
    assert load_config(tmp_path).site.feed_items == 7


def test_feed_items_must_be_positive(tmp_path: Path) -> None:
    (tmp_path / "pulse.config.yaml").write_text("site:\n  feed_items: 0\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=r"feed_items.*less than the minimum"):
        load_config(tmp_path)


def test_collect_defaults_load() -> None:
    cfg = load_config(None)
    assert cfg.collect.respect_robots is True
    assert cfg.collect.concurrency >= 1
    assert "{version}" in cfg.collect.user_agent


def test_collect_defaults_are_the_documented_values() -> None:
    assert load_config().collect.model_dump() == {
        "user_agent": "PulseAI/{version} (+https://github.com/Mordris/PulseAI)",
        "concurrency": 8,
        "per_host_per_minute": 30,
        "timeout_seconds": 20,
        "retries": 3,
        "max_wait_seconds": 120,
        "max_redirects": 5,
        "max_response_bytes": 10485760,
        "summary_max_chars": 600,
        "title_max_chars": 300,
        "respect_robots": True,
        "cache_dir": ".pulse/http-cache",
        "snapshot_keep": 14,
        "meta_fetch_limit": 20,
        "max_child_sitemaps": 50,
    }


def test_collect_instance_and_env_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pulse.config.yaml").write_text(
        "collect:\n  concurrency: 2\n  respect_robots: false\n", encoding="utf-8"
    )
    monkeypatch.setenv("PULSE__COLLECT__PER_HOST_PER_MINUTE", "5")
    cfg = load_config(tmp_path)
    assert cfg.collect.concurrency == 2
    assert cfg.collect.respect_robots is False
    assert cfg.collect.per_host_per_minute == 5
    assert cfg.collect.retries == 3


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("user_agent", "PulseAI"),
        ("user_agent", "PulseAI/{version}\r\nX-Injected: 1"),
        ("concurrency", 0),
        ("per_host_per_minute", 0),
        ("timeout_seconds", 0),
        ("timeout_seconds", 301),
        ("retries", -1),
        ("retries", 11),
        ("max_wait_seconds", -1),
        ("max_redirects", -1),
        ("max_response_bytes", 0),
        ("summary_max_chars", 0),
        ("title_max_chars", 0),
        ("respect_robots", "sometimes"),
        ("cache_dir", ""),
        ("cache_dir", "/var/cache/pulse"),
        ("snapshot_keep", 1),
        ("meta_fetch_limit", 0),
        ("max_child_sitemaps", 0),
        ("surprise", 1),
    ],
)
def test_invalid_collect_values_are_rejected(tmp_path: Path, key: str, value: object) -> None:
    # JSON is valid YAML, so json.dumps writes any scalar the way YAML will read it back.
    (tmp_path / "pulse.config.yaml").write_text(
        f"collect:\n  {key}: {json.dumps(value)}\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError, match=key):
        load_config(tmp_path)
