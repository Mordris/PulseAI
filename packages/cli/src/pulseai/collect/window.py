"""The collection window, the run date, and the expansion of URL templates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, tzinfo
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pulseai.collect.normalize import format_timestamp, to_utc
from pulseai.templates import (
    MISSING,
    config_variable,
    field_problem,
    is_template_value,
    template_parts,
)

# Characters a template value may keep unencoded: RFC 3986 unreserved, plus ":" for timestamps.
URL_SAFE_CHARS = "-._~:"


@dataclass(frozen=True)
class Window:
    """The times to collect, `[since, until)`, both timezone-aware UTC."""

    since: datetime
    until: datetime

    def contains(self, at: datetime) -> bool:
        return self.since <= at < self.until


def _zone(tz: str) -> ZoneInfo:
    """The named time zone. Raises ValueError, not the lookup error, when there is no such zone."""
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        # ValueError is a malformed key and OSError one the file system rejects (too long).
        msg = f"unknown time zone {tz!r}"
        raise ValueError(msg) from None


def default_run_date(tz: str, now: datetime) -> date:
    """The calendar date of `now` in the schedule's time zone. Raises ValueError for a bad zone."""
    return to_utc(now).astimezone(_zone(tz)).date()


def _bound(option: str, text: str, zone: tzinfo) -> datetime:
    """An ISO 8601 date or date and time as UTC; one without a time zone is read in `zone`."""
    try:
        parsed = datetime.fromisoformat(text.strip())
        if parsed.utcoffset() is None:
            parsed = parsed.replace(tzinfo=zone)
        return parsed.astimezone(UTC)
    except (ValueError, OverflowError):
        msg = f"invalid {option} {text!r}: expected an ISO 8601 date or date and time"
        raise ValueError(msg) from None


def resolve_window(
    *, since: str | None, until: str | None, max_hours: int, tz: str, now: datetime
) -> Window:
    """The window for a run.

    `until` defaults to `now` and `since` to `max_hours` before `until`. Bounds without a time zone
    are read in `tz`. Raises ValueError for an unknown time zone, a bound that does not parse, or a
    window that is empty.
    """
    zone = _zone(tz)
    window_end = to_utc(now) if until is None else _bound("until", until, zone)
    try:
        window_start = (
            window_end - timedelta(hours=max_hours)
            if since is None
            else _bound("since", since, zone)
        )
    except OverflowError:
        msg = f"a window of {max_hours} hours before {format_timestamp(window_end)} is out of range"
        raise ValueError(msg) from None
    if window_start >= window_end:
        msg = (
            f"since ({format_timestamp(window_start)}) must be before "
            f"until ({format_timestamp(window_end)})"
        )
        raise ValueError(msg)
    return Window(since=window_start, until=window_end)


def _field_value(
    field: str, variables: Mapping[str, str], config: Mapping[str, Any], template: str
) -> str:
    if field in variables:
        return variables[field]
    value = config_variable(field, config)
    if value is MISSING:
        msg = f"unknown template variable {field!r} in {template!r}"
        raise ValueError(msg)
    if not is_template_value(value):
        msg = f"template variable {field!r} must be a string or number in {template!r}"
        raise ValueError(msg)
    return str(value)


def expand_url(template: str, *, run_date: date, window: Window, config: Mapping[str, Any]) -> str:
    """Fill a URL template's `{date}`, `{since}`, `{until}` and `{config.<path>}` fields.

    Each value is percent-encoded; the template's own text is left as written. Raises ValueError
    for an unknown field, a config value that is not a string or number (a bool is not), a field
    with a format spec or conversion, or unbalanced braces.
    """
    variables = {
        "date": run_date.isoformat(),
        "since": format_timestamp(window.since),
        "until": format_timestamp(window.until),
    }
    pieces: list[str] = []
    for part in template_parts(template):
        pieces.append(part.literal)
        if part.field is None:
            continue
        problem = field_problem(part)
        if problem is not None:
            msg = f"template field {part.field!r} {problem} in {template!r}"
            raise ValueError(msg)
        value = _field_value(part.field, variables, config, template)
        pieces.append(quote(value, safe=URL_SAFE_CHARS))
    return "".join(pieces)
