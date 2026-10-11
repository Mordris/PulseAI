from datetime import date, time

from typer.testing import CliRunner

from pulseai.cli import app
from pulseai.models.config import ScheduleConfig
from pulseai.schedule import (
    actions_crons,
    launchd_interval,
    observes_dst,
    render_host,
    run_time,
    systemd_on_calendar,
)

runner = CliRunner()


def _cfg(t: str = "17:00", tz: str = "Europe/Istanbul", offset: int = 7) -> ScheduleConfig:
    return ScheduleConfig(time=t, tz=tz, cloud_offset_minutes_when_on_hour=offset)


def test_cloud_hosts_shift_on_the_hour_times() -> None:
    assert run_time(_cfg(), "routine") == time(17, 7)
    assert run_time(_cfg(), "actions") == time(17, 7)
    assert run_time(_cfg(), "systemd") == time(17, 0)


def test_off_hour_times_are_not_shifted() -> None:
    assert run_time(_cfg("17:30"), "actions") == time(17, 30)


def test_istanbul_single_cron() -> None:
    assert not observes_dst("Europe/Istanbul", 2026)
    assert actions_crons(_cfg(), 2026) == ["7 14 * * *"]


def test_new_york_two_crons() -> None:
    cfg = _cfg("09:00", "America/New_York")
    assert observes_dst("America/New_York", 2026)
    assert actions_crons(cfg, 2026) == ["7 14 * * *", "7 13 * * *"]


def test_midnight_wrap() -> None:
    assert actions_crons(_cfg("01:00"), 2026) == ["7 22 * * *"]


def test_systemd_on_calendar_uses_exact_time() -> None:
    assert systemd_on_calendar(_cfg()) == "*-*-* 17:00:00 Europe/Istanbul"


def test_launchd_converts_to_machine_zone() -> None:
    assert launchd_interval(_cfg(), "Europe/Berlin", date(2026, 1, 15)) == {"Hour": 15, "Minute": 0}


def test_render_actions_mentions_dst_guard_only_when_needed() -> None:
    assert "DST" not in render_host(_cfg(), "actions", date(2026, 10, 11), "Europe/Istanbul")
    ny = render_host(_cfg("09:00", "America/New_York"), "actions", date(2026, 10, 11), "UTC")
    assert "DST" in ny


def test_cli_schedule_print() -> None:
    result = runner.invoke(app, ["schedule", "print", "--host", "actions"])
    assert result.exit_code == 0
    assert '"7 14 * * *"' in result.output
    bad = runner.invoke(app, ["schedule", "print", "--host", "cron-ish"])
    assert bad.exit_code == 2
