"""Turn the configured local start time into settings for each host's scheduler."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Literal, get_args
from zoneinfo import ZoneInfo

from pulseai.models.config import ScheduleConfig

Host = Literal["routine", "actions", "systemd", "launchd"]
HOSTS: tuple[Host, ...] = get_args(Host)
CLOUD_HOSTS: frozenset[Host] = frozenset({"routine", "actions"})
_ANCHOR = date(2000, 1, 3)
_DAYS_IN_LEAP_YEAR = 366


def parse_hhmm(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def run_time(cfg: ScheduleConfig, host: Host) -> time:
    """Local wall-clock start time; cloud hosts shift on-the-hour times (they start late on :00)."""
    start = parse_hhmm(cfg.time)
    if host in CLOUD_HOSTS and start.minute == 0:
        shifted = datetime.combine(_ANCHOR, start) + timedelta(
            minutes=cfg.cloud_offset_minutes_when_on_hour
        )
        return shifted.time()
    return start


def utc_offsets(tz: str, year: int) -> list[timedelta]:
    """Distinct UTC offsets of a zone in a year, in the order they first apply.

    Every day of the year is checked at 12:00 local time, so short-lived offsets (such as
    Morocco's Ramadan break) are not missed.
    """
    zone = ZoneInfo(tz)
    noon = datetime(year, 1, 1, 12, tzinfo=zone)
    offsets: list[timedelta] = []
    for day in range(_DAYS_IN_LEAP_YEAR):
        moment = noon + timedelta(days=day)
        if moment.year != year:
            break
        offset = moment.utcoffset()
        if offset is not None and offset not in offsets:
            offsets.append(offset)
    return offsets


def observes_dst(tz: str, year: int) -> bool:
    return len(utc_offsets(tz, year)) > 1


def actions_crons(cfg: ScheduleConfig, year: int) -> list[str]:
    """UTC cron lines for GitHub Actions; two lines when the zone observes DST."""
    start = run_time(cfg, "actions")
    crons: list[str] = []
    for offset in utc_offsets(cfg.tz, year):
        utc = datetime.combine(_ANCHOR, start) - offset
        line = f"{utc.minute} {utc.hour} * * *"
        if line not in crons:
            crons.append(line)
    return crons


def systemd_on_calendar(cfg: ScheduleConfig) -> str:
    return f"*-*-* {run_time(cfg, 'systemd'):%H:%M}:00 {cfg.tz}"


def launchd_interval(cfg: ScheduleConfig, machine_tz: str, on: date) -> dict[str, int]:
    """launchd uses the machine's zone: convert the configured local time on a given date."""
    local = datetime.combine(on, run_time(cfg, "launchd"), tzinfo=ZoneInfo(cfg.tz))
    converted = local.astimezone(ZoneInfo(machine_tz))
    return {"Hour": converted.hour, "Minute": converted.minute}


def render_host(cfg: ScheduleConfig, host: Host, today: date, machine_tz: str) -> str:
    if host == "routine":
        start = run_time(cfg, host)
        return (
            f"Routine schedule: daily at {start:%H:%M} ({cfg.tz}).\n"
            "Set it at claude.ai/code/routines or with /schedule update.\n"
        )
    if host == "actions":
        lines = ["on:", "  schedule:"]
        lines += [f'    - cron: "{cron}"' for cron in actions_crons(cfg, today.year)]
        lines.append("  workflow_dispatch: {}")
        if observes_dst(cfg.tz, today.year):
            lines.append(
                f"# {cfg.tz} observes DST: both crons are listed; the workflow's guard step "
                "skips the run whose local time does not match."
            )
        return "\n".join(lines) + "\n"
    if host == "systemd":
        return f"[Timer]\nOnCalendar={systemd_on_calendar(cfg)}\nPersistent=true\n"
    interval = launchd_interval(cfg, machine_tz, today)
    return (
        "<key>StartCalendarInterval</key>\n"
        f"<dict><key>Hour</key><integer>{interval['Hour']}</integer>"
        f"<key>Minute</key><integer>{interval['Minute']}</integer></dict>\n"
        f"<!-- computed for machine time zone {machine_tz} on {today.isoformat()} -->\n"
    )
