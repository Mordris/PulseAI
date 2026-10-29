import math
import time
from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Any

import pytest
from pydantic import TypeAdapter

from pulseai.collect.items import BuildResult, build_items
from pulseai.collect.normalize import format_timestamp
from pulseai.collect.parsers import RawEntry
from pulseai.collect.window import Window
from pulseai.config import load_config
from pulseai.models.collected import (
    CollectedItem,
    CollectedSource,
    DatedItem,
    ItemChange,
    UndatedItem,
)
from pulseai.models.config import CollectConfig
from pulseai.schemas import validate_document

SOURCE = "test-source"
SINCE = datetime(2026, 10, 28, 0, 0, tzinfo=UTC)
UNTIL = datetime(2026, 10, 29, 0, 0, tzinfo=UTC)
WINDOW = Window(since=SINCE, until=UNTIL)
NOON = "2026-10-28T12:00:00Z"
COLLECTED_SCHEMA = "collected.schema.json"

ITEM = TypeAdapter(CollectedItem)


@cache
def engine_defaults() -> CollectConfig:
    """Read on first use inside a test, where the autouse fixture has cleared PULSE__ variables."""
    return load_config().collect


def entry(**fields: Any) -> RawEntry:
    """A valid entry inside the window, with the given fields replaced."""
    values: dict[str, Any] = {
        "id": None,
        "title": "A title",
        "url": "https://example.com/a",
        "published": NOON,
        "summary": None,
        "signal": None,
        "extra": {},
    }
    return RawEntry(**(values | fields))


def build(*entries: RawEntry, **options: Any) -> BuildResult:
    defaults: dict[str, Any] = {
        "source_id": SOURCE,
        "window": WINDOW,
        "changelog": False,
        "settings": engine_defaults(),
    }
    return build_items(entries, **(defaults | options))


def only(result: BuildResult) -> DatedItem | UndatedItem:
    assert len(result.items) == 1
    return result.items[0]


# --- the item itself ---------------------------------------------------------------------------


def test_a_complete_entry_becomes_a_dated_item() -> None:
    result = build(
        entry(
            id="2510.01234",
            title="  A   title ",
            url=" https://example.com/a?utm_source=feed&id=7 ",
            summary="<p>Hello <b>there</b></p>",
            signal=12,
            extra={"prerelease": True},
        )
    )

    item = only(result)
    assert isinstance(item, DatedItem)
    assert item.model_dump(mode="json") == {
        "id": "test-source:2510-01234",
        "source_id": "test-source",
        "title": "A title",
        "url": "https://example.com/a?utm_source=feed&id=7",
        "canonical_url": "https://example.com/a?id=7",
        "published": NOON,
        "undated": False,
        "summary": "Hello there",
        "signal": 12.0,
        "extra": {"prerelease": True},
        "detected_at": None,
        "change": None,
    }
    assert (result.dropped_window, result.dropped_invalid) == (0, 0)


def test_an_entry_without_an_id_gets_one_from_its_url() -> None:
    first = only(build(entry(url="https://example.com/a")))
    again = only(build(entry(url="https://example.com/a?utm_medium=email")))
    other = only(build(entry(url="https://example.com/b")))

    assert first.id == again.id
    assert first.id != other.id
    assert first.id.startswith("test-source:")


def test_every_item_validates_as_a_collected_item() -> None:
    result = build(entry(), entry(published=None), window=None)

    for item in result.items:
        assert ITEM.validate_python(item.model_dump(mode="json")) == item


def test_items_keep_the_order_of_the_entries() -> None:
    entries = [entry(url=f"https://example.com/{n}", title=f"Item {n}") for n in (3, 1, 2)]

    assert [item.title for item in build(*entries).items] == ["Item 3", "Item 1", "Item 2"]


@pytest.mark.parametrize(
    ("published", "expected"),
    [
        ("2026-10-28T12:00:00Z", NOON),
        ("2026-10-28T14:00:00+02:00", NOON),
        ("2026-10-28T12:00:00", NOON),
        ("Wed, 28 Oct 2026 12:00:00 GMT", NOON),
        ("2026-10-28", "2026-10-28T00:00:00Z"),
        (datetime(2026, 10, 28, 12, tzinfo=UTC).timestamp(), NOON),
        (time.gmtime(datetime(2026, 10, 28, 12, tzinfo=UTC).timestamp()), NOON),
    ],
    ids=["utc", "offset", "naive", "rfc822", "date", "epoch", "struct_time"],
)
def test_published_is_written_in_utc(published: object, expected: str) -> None:
    assert only(build(entry(published=published))).published == expected


def test_detected_at_and_change_are_attached() -> None:
    change = ItemChange.model_validate({"kind": "added", "fields": []})
    seen: list[RawEntry] = []

    def describe(raw: RawEntry) -> ItemChange | None:
        seen.append(raw)
        return change if raw.title == "Changed" else None

    detected = datetime(2026, 10, 28, 15, 30, 45, 123456, tzinfo=UTC)
    result = build(
        entry(title="Changed", url="https://example.com/1"),
        entry(title="Same", url="https://example.com/2"),
        detected_at=detected,
        change=describe,
    )

    assert [(i.title, i.change, i.detected_at) for i in result.items] == [
        ("Changed", change, "2026-10-28T15:30:45Z"),
        ("Same", None, "2026-10-28T15:30:45Z"),
    ]
    assert [raw.title for raw in seen] == ["Changed", "Same"]


# --- the window and the changelog rule ---------------------------------------------------------


def test_window_bounds_are_half_open() -> None:
    entries = [
        entry(title="Before", url="https://example.com/1", published=SINCE - timedelta(seconds=1)),
        entry(title="At since", url="https://example.com/2", published=SINCE),
        entry(
            title="Last second", url="https://example.com/3", published=UNTIL - timedelta(seconds=1)
        ),
        entry(title="At until", url="https://example.com/4", published=UNTIL),
    ]

    result = build(*entries)

    assert [item.title for item in result.items] == ["At since", "Last second"]
    assert (result.dropped_window, result.dropped_invalid) == (2, 0)


def test_undated_dropped_unless_changelog() -> None:
    undated = entry(published=None)

    dropped = build(undated)
    kept = only(build(undated, changelog=True))

    assert dropped.items == []
    assert (dropped.dropped_window, dropped.dropped_invalid) == (1, 0)
    assert isinstance(kept, UndatedItem)
    assert (kept.undated, kept.published) == (True, None)


@pytest.mark.parametrize(
    "published", ["not a date", "", "2026-13-45", "yesterday", [1], 1e30, True]
)
def test_unparseable_date_is_undated(published: object) -> None:
    undated = entry(published=published)

    assert build(undated).items == []
    assert build(undated).dropped_window == 1
    kept = only(build(undated, changelog=True))
    assert isinstance(kept, UndatedItem)
    assert kept.published is None


def test_a_dated_entry_outside_the_window_is_dropped_even_for_a_changelog() -> None:
    old = entry(published="2026-01-01T00:00:00Z")

    result = build(old, changelog=True)

    assert (result.items, result.dropped_window) == ([], 1)


def test_without_a_window_nothing_is_dropped_for_its_date() -> None:
    result = build(
        entry(title="Old", url="https://example.com/1", published="2020-01-01T00:00:00Z"),
        entry(title="Undated", url="https://example.com/2", published=None),
        window=None,
    )

    assert [(item.title, item.undated) for item in result.items] == [
        ("Old", False),
        ("Undated", True),
    ]
    assert result.dropped_window == 0


# --- entries that cannot become items ----------------------------------------------------------


@pytest.mark.parametrize(
    "fields",
    [
        {"title": None},
        {"title": ""},
        {"title": "   \n "},
        {"title": "<p></p>"},
        {"title": "<script>alert(1)</script>"},
        {"url": None},
        {"url": ""},
        {"url": "   "},
        {"url": "not a url"},
        {"url": "/relative/path"},
        {"url": "//example.com/protocol-relative"},
        {"url": "javascript:alert(1)"},
        {"url": "data:text/html,<p>hi</p>"},
        {"url": "file:///etc/passwd"},
        {"url": "ftp://example.com/file"},
        {"url": "https://"},
        {"url": "https://example.com:99999/a"},
        {"url": "https://example.com/a b"},
    ],
    ids=lambda fields: repr(fields)[:40],
)
def test_missing_title_or_url_is_dropped_invalid(fields: dict[str, Any]) -> None:
    result = build(entry(**fields), entry(url="https://example.com/ok", title="Fine"))

    assert [item.title for item in result.items] == ["Fine"]
    assert (result.dropped_invalid, result.dropped_window) == (1, 0)


def test_non_https_canonical_url_is_dropped_invalid() -> None:
    result = build(
        entry(title="Plain http", url="http://example.com/a"),
        entry(title="Secure", url="https://example.com/b"),
    )

    assert [item.title for item in result.items] == ["Secure"]
    assert result.dropped_invalid == 1


def test_an_invalid_entry_is_invalid_whatever_its_date() -> None:
    result = build(entry(url=None, published=None), entry(url=None, published="2020-01-01"))

    assert (result.dropped_invalid, result.dropped_window) == (2, 0)


def test_duplicate_ids_within_a_source_keep_the_first() -> None:
    result = build(
        entry(id="same", title="First", url="https://example.com/1"),
        entry(id="same", title="Second", url="https://example.com/2"),
        entry(title="Third", url="https://example.com/3"),
        entry(title="Fourth", url="https://example.com/3?utm_source=x"),
    )

    assert [item.title for item in result.items] == ["First", "Third"]
    assert len({item.id for item in result.items}) == 2
    assert (result.dropped_window, result.dropped_invalid) == (0, 0)


# --- text and numbers --------------------------------------------------------------------------


def test_title_and_summary_are_cleaned_and_capped() -> None:
    settings = engine_defaults().model_copy(update={"title_max_chars": 20, "summary_max_chars": 30})
    result = build(
        entry(
            title="<b>Hello</b>   world &amp; more words after it",
            summary="<p>One</p><p>two three four five six seven eight nine</p><script>x()</script>",
        ),
        settings=settings,
    )

    item = only(result)
    assert item.title == "Hello world & more…"
    assert item.summary == "One two three four five six…"
    assert len(item.title) <= 20
    assert item.summary is not None
    assert len(item.summary) <= 30


def test_empty_summary_is_null() -> None:
    assert only(build(entry(summary="<br>  "))).summary is None
    assert only(build(entry(summary=None))).summary is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("12", 12.0),
        (12, 12.0),
        (3.5, 3.5),
        (" 7 ", 7.0),
        ("-2.5", -2.5),
        ("1e3", 1000.0),
        (0, 0.0),
        ("many", None),
        ("", None),
        (None, None),
        (True, None),
        (False, None),
        (float("nan"), None),
        (math.inf, None),
        ("nan", None),
        ("inf", None),
        ("١٢", None),
        ([1], None),
        ({"n": 1}, None),
    ],
)
def test_signal_must_be_numeric_or_null(raw: object, expected: float | None) -> None:
    assert only(build(entry(signal=raw))).signal == expected


def test_extra_keeps_scalars_and_drops_other_values() -> None:
    extra = {
        "text": "x",
        "number": 3,
        "decimal": 2.5,
        "flag": False,
        "nothing": None,
        "list": [1, 2],
        "object": {"a": 1},
        "not-a-number": math.nan,
    }

    item = only(build(entry(extra=extra)))

    assert item.extra == {
        "text": "x",
        "number": 3,
        "decimal": 2.5,
        "flag": False,
        "nothing": None,
    }


def test_the_collected_item_type_accepts_what_build_items_returns() -> None:
    item = only(build(entry(published=None), changelog=True))

    assert ITEM.validate_python(item.model_dump()).undated is True


def test_text_with_a_lone_surrogate_can_still_be_written() -> None:
    """JSON allows "\\ud800" on its own, but it cannot be encoded as UTF-8, so it is replaced."""
    result = build(
        entry(
            id="a\ud800b",
            title="t\ud800",
            url="https://example.com/a\ud800b",
            summary="s\ud800",
            extra={"k": "x\ud800"},
        )
    )

    item = only(result)
    assert item.model_dump_json().encode("utf-8")
    assert item.extra == {"k": "x?"}


# --- items dumped into a collected file --------------------------------------------------------


def collected_file(items: list[CollectedItem]) -> dict[str, Any]:
    """A whole collected file, dumped the way the repo dumps models (`exclude_unset`)."""
    document = CollectedSource.model_validate(
        {
            "schema_version": 1,
            "source": {
                "id": SOURCE,
                "name": "Test source",
                "tier": "T1",
                "trust": 3,
                "sections": ["research"],
                "kind": "json",
                "url": "https://example.com/feed",
            },
            "window": {"since": format_timestamp(SINCE), "until": format_timestamp(UNTIL)},
            "collected_at": NOON,
            "items": items,
        }
    )
    return document.model_dump(mode="json", exclude_unset=True)


def test_dumped_items_validate_against_the_collected_schema() -> None:
    change = ItemChange.model_validate(
        {"kind": "changed", "fields": [{"path": "pricing", "old": None, "new": 2}]}
    )
    detected = datetime(2026, 10, 28, 15, 30, tzinfo=UTC)
    dated = build(entry(title="Dated", url="https://example.com/1"))
    undated = build(
        entry(title="Undated", url="https://example.com/2", published=None), changelog=True
    )
    changed = build(
        entry(title="Changed", url="https://example.com/3"),
        detected_at=detected,
        change=lambda _: change,
    )
    detected_only = build(
        entry(title="Detected only", url="https://example.com/4"),
        detected_at=detected,
        change=lambda _: None,
    )
    items = [*dated.items, *undated.items, *changed.items, *detected_only.items]
    assert len(items) == 4

    document = collected_file(items)

    assert validate_document(document, COLLECTED_SCHEMA) == []
    assert [item["undated"] for item in document["items"]] == [False, True, False, False]


def test_an_item_without_a_change_or_detection_time_dumps_without_those_keys() -> None:
    """The schema allows neither key to be null, so an item that has none must not carry them."""
    item = only(build(entry()))

    dumped = item.model_dump(mode="json", exclude_unset=True)

    assert "change" not in dumped
    assert "detected_at" not in dumped
    # Required but nullable: present as null, not left out.
    assert (dumped["summary"], dumped["signal"]) == (None, None)


def test_change_and_detection_time_dump_when_given() -> None:
    change = ItemChange.model_validate({"kind": "added", "fields": []})
    detected = datetime(2026, 10, 28, 15, 30, tzinfo=UTC)

    item = only(build(entry(), detected_at=detected, change=lambda _: change))

    dumped = item.model_dump(mode="json", exclude_unset=True)
    assert dumped["detected_at"] == "2026-10-28T15:30:00Z"
    assert dumped["change"] == {"kind": "added", "fields": []}
