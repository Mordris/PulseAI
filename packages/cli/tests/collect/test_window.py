from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from pulseai.collect.window import Window, default_run_date, expand_url, resolve_window
from pulseai.registry.loader import load_catalog

NOW = datetime(2026, 10, 29, 15, 0, tzinfo=UTC)
ISTANBUL = "Europe/Istanbul"
RUN_DATE = date(2026, 10, 29)


def resolve(
    *,
    since: str | None = None,
    until: str | None = None,
    max_hours: int = 72,
    tz: str = ISTANBUL,
    now: datetime = NOW,
) -> Window:
    return resolve_window(since=since, until=until, max_hours=max_hours, tz=tz, now=now)


def test_default_window_is_max_hours_back_from_now() -> None:
    window = resolve()
    assert window.since == datetime(2026, 10, 26, 15, 0, tzinfo=UTC)
    assert window.until == NOW


def test_naive_since_is_read_in_schedule_tz() -> None:
    window = resolve(since="2026-10-28T17:00")
    assert window.since == datetime(2026, 10, 28, 14, 0, tzinfo=UTC)
    assert window.until == NOW


def test_naive_until_is_read_in_schedule_tz() -> None:
    window = resolve(since="2026-10-28T00:00+00:00", until="2026-10-29T12:00")
    assert window.until == datetime(2026, 10, 29, 9, 0, tzinfo=UTC)


def test_date_only_bound_is_midnight_in_schedule_tz() -> None:
    assert resolve(since="2026-10-28").since == datetime(2026, 10, 27, 21, 0, tzinfo=UTC)


def test_bound_with_an_offset_ignores_schedule_tz() -> None:
    window = resolve(since="2026-10-28T17:00+05:00", until="2026-10-29T10:00Z")
    assert window.since == datetime(2026, 10, 28, 12, 0, tzinfo=UTC)
    assert window.until == datetime(2026, 10, 29, 10, 0, tzinfo=UTC)


def test_naive_bounds_follow_the_zone_offset_on_that_date() -> None:
    # New York moves to daylight saving time on 2026-03-08, so the same wall-clock time differs.
    window = resolve(since="2026-03-07T12:00", until="2026-03-09T12:00", tz="America/New_York")
    assert window.since == datetime(2026, 3, 7, 17, 0, tzinfo=UTC)
    assert window.until == datetime(2026, 3, 9, 16, 0, tzinfo=UTC)


def test_until_alone_sets_the_start_max_hours_before_it() -> None:
    window = resolve(until="2026-10-29T12:00", max_hours=48)
    assert window.until == datetime(2026, 10, 29, 9, 0, tzinfo=UTC)
    assert window.since == window.until - timedelta(hours=48)


def test_window_bounds_are_utc() -> None:
    window = resolve(since="2026-10-28T17:00+05:00")
    assert window.since.utcoffset() == timedelta(0)
    assert window.until.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    ("since", "until"),
    [
        ("2026-10-29T10:00Z", "2026-10-29T10:00Z"),
        ("2026-10-29T11:00Z", "2026-10-29T10:00Z"),
        ("2026-10-29T15:00Z", None),  # until defaults to now
        ("2026-10-30", None),
    ],
)
def test_since_not_before_until_is_rejected(since: str, until: str | None) -> None:
    with pytest.raises(ValueError, match="before"):
        resolve(since=since, until=until)


def test_a_non_positive_max_hours_is_rejected() -> None:
    with pytest.raises(ValueError, match="before"):
        resolve(max_hours=0)


@pytest.mark.parametrize(
    ("since", "until", "name"),
    [("yesterday", None, "since"), ("2026-10-01", "2026-13-45", "until")],
)
def test_unparseable_bound_names_the_option(since: str, until: str | None, name: str) -> None:
    with pytest.raises(ValueError, match=name):
        resolve(since=since, until=until)


@pytest.mark.parametrize(
    ("since", "until"),
    [
        (None, "0001-01-02"),  # the default start would be before the first representable time
        ("0001-01-01", None),  # the first day, read in a zone ahead of UTC, is before year 1 in UTC
        ("9999-12-31T23:59:59-05:00", None),  # after the last representable time in UTC
    ],
)
def test_bounds_at_the_edge_of_the_calendar_are_rejected(
    since: str | None, until: str | None
) -> None:
    with pytest.raises(ValueError, match=r"out of range|invalid"):
        resolve(since=since, until=until)


def test_contains_is_half_open() -> None:
    window = Window(
        since=datetime(2026, 10, 26, tzinfo=UTC), until=datetime(2026, 10, 29, tzinfo=UTC)
    )
    assert window.contains(window.since)
    assert window.contains(window.until - timedelta(microseconds=1))
    assert not window.contains(window.until)
    assert not window.contains(window.since - timedelta(microseconds=1))
    assert not window.contains(window.until + timedelta(days=30))


def test_contains_compares_instants_across_offsets() -> None:
    window = resolve()
    assert window.contains(datetime.fromisoformat("2026-10-29T17:59:59+03:00"))  # 14:59:59Z
    assert not window.contains(datetime.fromisoformat("2026-10-29T18:00:00+03:00"))  # 15:00:00Z


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 10, 29, 22, 30, tzinfo=UTC), date(2026, 10, 30)),
        (datetime(2026, 10, 29, 20, 59, tzinfo=UTC), date(2026, 10, 29)),
        (datetime(2026, 10, 29, 21, 0, tzinfo=UTC), date(2026, 10, 30)),
    ],
)
def test_default_run_date_uses_schedule_tz(now: datetime, expected: date) -> None:
    assert default_run_date(ISTANBUL, now) == expected


def test_default_run_date_reads_an_aware_now_in_any_offset() -> None:
    now = datetime.fromisoformat("2026-10-29T23:30:00-05:00")  # 04:30Z on the 30th
    assert default_run_date("UTC", now) == date(2026, 10, 30)


@pytest.mark.parametrize("tz", ["Mars/Base", "", "../etc", "europe/istanbul", "UTC\0", "a" * 5000])
def test_unknown_time_zone_is_a_value_error(tz: str) -> None:
    with pytest.raises(ValueError, match="time zone"):
        resolve(tz=tz)
    with pytest.raises(ValueError, match="time zone"):
        default_run_date(tz, NOW)


def expand(
    template: str, config: dict[str, Any] | None = None, window: Window | None = None
) -> str:
    return expand_url(template, run_date=RUN_DATE, window=window or resolve(), config=config or {})


def test_expand_url_fills_date_since_until() -> None:
    assert expand("https://x.test/{date}") == "https://x.test/2026-10-29"
    assert expand("https://x.test/?s={since}&u={until}") == (
        "https://x.test/?s=2026-10-26T15:00:00Z&u=2026-10-29T15:00:00Z"
    )


def test_expand_url_drops_microseconds_from_window_bounds() -> None:
    window = Window(
        since=datetime(2026, 10, 26, 15, 0, 0, 999999, tzinfo=UTC),
        until=datetime(2026, 10, 29, 15, 0, tzinfo=UTC),
    )
    assert expand("{since}", window=window) == "2026-10-26T15:00:00Z"


def test_expand_url_reads_config_paths() -> None:
    config = {"window": {"max_hours": 72}, "ratio": 1.5, "name": "papers"}
    assert expand("{config.window.max_hours}", config) == "72"
    assert expand("{config.ratio}", config) == "1.5"
    assert (
        expand("https://x.test/{config.name}/{date}", config) == "https://x.test/papers/2026-10-29"
    )


def test_expand_url_percent_encodes_values() -> None:
    config = {"q": "a b&c", "path": "a/b?c=d", "word": "café"}
    assert expand("{config.q}", config) == "a%20b%26c"
    assert expand("{config.path}", config) == "a%2Fb%3Fc%3Dd"
    assert expand("{config.word}", config) == "caf%C3%A9"


def test_expand_url_leaves_literal_text_alone() -> None:
    assert expand("https://x.test/a b?x=1&y=2#top") == "https://x.test/a b?x=1&y=2#top"
    assert expand("https://x.test/{{literal}}/{date}") == "https://x.test/{literal}/2026-10-29"


def test_expand_url_encodes_percent_signs_in_values() -> None:
    assert expand("{config.q}", {"q": "100%"}) == "100%25"


def test_expand_url_covers_every_catalog_variable() -> None:
    for name in load_catalog().template_variables:
        assert expand("{" + name + "}")


@pytest.mark.parametrize("template", ["{nope}", "{0}", "{config}", "{config.nope}", "{config.a.b}"])
def test_expand_url_rejects_unknown_variables(template: str) -> None:
    with pytest.raises(ValueError, match="unknown template variable"):
        expand(template, {"a": "text"})


@pytest.mark.parametrize("name", ["flag", "table", "nothing", "items"])
def test_expand_url_rejects_booleans_and_non_scalars(name: str) -> None:
    config = {"flag": True, "table": {"a": 1}, "nothing": None, "items": [1, 2]}
    with pytest.raises(ValueError, match="must be a string or number"):
        expand("{config." + name + "}", config)


@pytest.mark.parametrize("template", ["{date:%Y}", "{date!r}", "{config.n:>5}"])
def test_expand_url_rejects_format_specs_and_conversions(template: str) -> None:
    with pytest.raises(ValueError, match="format"):
        expand(template, {"n": 1})


@pytest.mark.parametrize("template", ["{}", "x/{}/y", "{:>5}", "{!r}"])
def test_expand_url_rejects_a_field_without_a_name(template: str) -> None:
    with pytest.raises(ValueError, match="has no name"):
        expand(template)


@pytest.mark.parametrize("template", ["https://x.test/{date", "https://x.test/date}"])
def test_expand_url_rejects_unbalanced_braces(template: str) -> None:
    with pytest.raises(ValueError, match="}"):
        expand(template)
