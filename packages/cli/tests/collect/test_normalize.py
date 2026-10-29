import hashlib
import re
import time
from datetime import UTC, datetime, timedelta, timezone

import pytest

from pulseai.collect.normalize import (
    canonical_url,
    clean_text,
    format_timestamp,
    item_id,
    parse_timestamp,
)
from pulseai.schemas import load_schema

COLLECTED_SCHEMA = "collected.schema.json"
SOURCE = "hf-daily-papers"
URL = "https://example.com/post"


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def test_parse_timestamp_naive_is_utc() -> None:
    assert parse_timestamp(datetime(2026, 10, 28, 14, 30)) == utc(2026, 10, 28, 14, 30)
    assert parse_timestamp("2026-10-28T14:30:00") == utc(2026, 10, 28, 14, 30)
    assert parse_timestamp("2026-10-28 14:30") == utc(2026, 10, 28, 14, 30)


def test_parse_timestamp_converts_aware_values_to_utc() -> None:
    east = timezone(timedelta(hours=3))
    parsed = parse_timestamp(datetime(2026, 10, 28, 14, 30, tzinfo=east))
    assert parsed == utc(2026, 10, 28, 11, 30)
    assert parsed is not None
    assert parsed.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2026-10-28T14:30:00Z", utc(2026, 10, 28, 14, 30)),
        ("2026-10-28T14:30:00+03:00", utc(2026, 10, 28, 11, 30)),
        ("2026-10-28T14:30:00.250-05:00", datetime(2026, 10, 28, 19, 30, 0, 250000, tzinfo=UTC)),
        ("  2026-10-28T14:30:00Z\n", utc(2026, 10, 28, 14, 30)),
    ],
)
def test_parse_timestamp_iso_8601(text: str, expected: datetime) -> None:
    assert parse_timestamp(text) == expected


def test_parse_timestamp_date_only_is_midnight_utc() -> None:
    assert parse_timestamp("2026-10-28") == utc(2026, 10, 28)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Tue, 28 Oct 2026 14:30:00 GMT", utc(2026, 10, 28, 14, 30)),
        ("Tue, 28 Oct 2026 14:30:00 +0300", utc(2026, 10, 28, 11, 30)),
        ("Tue, 28 Oct 2026 14:30:00 -0000", utc(2026, 10, 28, 14, 30)),
        ("28 Oct 2026 14:30 EST", utc(2026, 10, 28, 19, 30)),
    ],
)
def test_parse_timestamp_rfc822(text: str, expected: datetime) -> None:
    assert parse_timestamp(text) == expected


def test_parse_timestamp_rfc822_and_struct_time() -> None:
    # feedparser gives a UTC time.struct_time in its *_parsed fields.
    parsed = time.strptime("2026-10-28 14:30:15", "%Y-%m-%d %H:%M:%S")
    assert parse_timestamp(parsed) == utc(2026, 10, 28, 14, 30, 15)
    assert parse_timestamp(time.gmtime(0)) == utc(1970, 1, 1)
    assert parse_timestamp("Tue, 28 Oct 2026 14:30:00 GMT") == utc(2026, 10, 28, 14, 30)


def test_parse_timestamp_struct_time_leap_second_rolls_over() -> None:
    leap = time.struct_time((2026, 12, 31, 23, 59, 60, 3, 365, 0))
    assert parse_timestamp(leap) == utc(2027, 1, 1)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "not a date",
        "2026-13-45",
        "Tue, 31 Feb 2026 10:00:00 GMT",
        "Tue, 28 Oct 2026",
        "12",
        "0001-01-01T00:00:00+05:00",  # before the first UTC instant
        None,
        True,  # a bool is an int, but not a number of seconds
        False,
        float("nan"),
        float("inf"),
        1761746400000,  # milliseconds: far beyond year 9999 when read as seconds
        10**30,
        [],
        b"2026-10-28",
        time.struct_time((99999, 1, 1, 0, 0, 0, 0, 1, 0)),
    ],
)
def test_parse_timestamp_garbage_is_none(value: object) -> None:
    assert parse_timestamp(value) is None


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (1793282400, utc(2026, 10, 29, 14)),
        (1761746400, utc(2025, 10, 29, 14)),
        (0, utc(1970, 1, 1)),
        (-86400, utc(1969, 12, 31)),
        (1793282400.0, utc(2026, 10, 29, 14)),
        (1793282400.5, datetime(2026, 10, 29, 14, 0, 0, 500000, tzinfo=UTC)),
    ],
)
def test_parse_timestamp_number_is_unix_epoch_seconds_in_utc(
    seconds: float, expected: datetime
) -> None:
    parsed = parse_timestamp(seconds)
    assert parsed == expected
    assert parsed is not None
    assert parsed.utcoffset() == timedelta(0)


def test_format_timestamp_is_utc_with_z_and_no_microseconds() -> None:
    east = timezone(timedelta(hours=3))
    assert format_timestamp(datetime(2026, 10, 28, 14, 30, 5, 999999, tzinfo=east)) == (
        "2026-10-28T11:30:05Z"
    )
    assert format_timestamp(utc(2026, 10, 28)) == "2026-10-28T00:00:00Z"


def test_format_timestamp_reads_naive_as_utc() -> None:
    assert format_timestamp(datetime(2026, 10, 28, 14, 30)) == "2026-10-28T14:30:00Z"


def test_format_timestamp_matches_the_schema_timestamp_pattern() -> None:
    pattern = load_schema(COLLECTED_SCHEMA)["$defs"]["timestamp"]["pattern"]
    assert re.search(pattern, format_timestamp(datetime(2026, 1, 2, 3, 4, 5, 6, tzinfo=UTC)))


def test_format_timestamp_round_trips_through_parse_timestamp() -> None:
    at = utc(2026, 10, 28, 14, 30, 5)
    assert parse_timestamp(format_timestamp(at)) == at


def test_canonical_url_drops_tracking_params() -> None:
    assert canonical_url("https://example.com/a?utm_source=x&id=3") == "https://example.com/a?id=3"
    assert canonical_url("https://example.com/a?fbclid=z&utm_medium=m") == "https://example.com/a"


def test_canonical_url_keeps_only_the_non_tracking_params() -> None:
    assert canonical_url("https://example.com/a?utm_source=x&id=3&fbclid=z") == (
        "https://example.com/a?id=3"
    )


def test_canonical_url_is_the_same_for_variants_of_one_page() -> None:
    variants = [
        "https://example.com/a/b?id=3",
        "HTTPS://Example.COM/a/b?utm_source=x&id=3",
        "https://example.com:443/a/b?id=3&utm_campaign=y",
        "https://example.com/a/b?id=3&fbclid=z",
        "  https://example.com/a/b?id=3\n",
    ]
    assert len({canonical_url(variant) for variant in variants}) == 1


def test_canonical_url_keeps_params_that_tell_pages_apart() -> None:
    # A query parameter is dropped only when it tracks; ?v= and ?slug= pick the page.
    assert canonical_url("https://video.test/watch?v=abc") == "https://video.test/watch?v=abc"
    assert canonical_url("https://video.test/watch?v=abc") != canonical_url(
        "https://video.test/watch?v=xyz"
    )
    assert canonical_url("https://example.com/blog?slug=foo") != canonical_url(
        "https://example.com/blog?slug=bar"
    )


def test_canonical_url_keeps_the_fragment_that_tells_entries_apart() -> None:
    # A changelog page lists its releases under fragments of one URL.
    first = canonical_url("https://example.com/changelog#v1.2.0")
    second = canonical_url("https://example.com/changelog#v1.3.0")
    assert first == "https://example.com/changelog#v1.2.0"
    assert first != second


def test_canonical_url_keeps_the_scheme() -> None:
    assert canonical_url("http://example.com/x") == "http://example.com/x"
    assert canonical_url("https://example.com/x") == "https://example.com/x"


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "ftp://example.com/x",
        "mailto:a@example.com",
        "data:text/html,hi",
        "file:///etc/passwd",
        "//example.com/x",
        "example.com/x",
        "/relative/path",
        "",
        "   ",
    ],
)
def test_canonical_url_rejects_non_http(url: str) -> None:
    assert canonical_url(url) is None


@pytest.mark.parametrize(
    "url",
    ["https://", "http:///x", "https://[::1/x", "https://example.com:abc/x", "https://:443/x"],
)
def test_canonical_url_rejects_unparseable_urls(url: str) -> None:
    assert canonical_url(url) is None


def test_item_id_from_mapped_id_is_slugged() -> None:
    assert item_id(SOURCE, mapped_id="2510.01234", canonical=URL) == "hf-daily-papers:2510-01234"
    assert item_id("gh", mapped_id="Release v1.2.3 (GA)", canonical=URL) == "gh:release-v1-2-3-ga"


def test_item_id_from_mapped_id_ignores_the_url() -> None:
    first = item_id(SOURCE, mapped_id="2510.01234", canonical="https://example.com/a")
    second = item_id(SOURCE, mapped_id="2510.01234", canonical="https://example.com/b")
    assert first == second


def test_item_id_without_mapped_id_hashes_canonical_url() -> None:
    first = item_id(SOURCE, mapped_id=None, canonical=URL)
    assert first == f"{SOURCE}:{hashlib.sha256(URL.encode()).hexdigest()[:16]}"
    assert re.fullmatch(rf"{SOURCE}:[0-9a-f]{{16}}", first)
    assert item_id(SOURCE, mapped_id=None, canonical=URL) == first
    assert item_id(SOURCE, mapped_id=None, canonical=URL + "2") != first


@pytest.mark.parametrize("mapped_id", ["", "   ", "!!!", "..."])
def test_item_id_falls_back_to_the_hash_when_the_mapped_id_has_no_slug(mapped_id: str) -> None:
    assert item_id(SOURCE, mapped_id=mapped_id, canonical=URL) == item_id(
        SOURCE, mapped_id=None, canonical=URL
    )


def test_item_id_falls_back_to_the_hash_when_the_slug_would_not_fit() -> None:
    limit = load_schema(COLLECTED_SCHEMA)["$defs"]["itemId"]["maxLength"]
    fits = "a" * (limit - len(SOURCE) - 1)
    assert item_id(SOURCE, mapped_id=fits, canonical=URL) == f"{SOURCE}:{fits}"
    too_long = item_id(SOURCE, mapped_id=fits + "a", canonical=URL)
    assert too_long == item_id(SOURCE, mapped_id=None, canonical=URL)


@pytest.mark.parametrize(
    "mapped_id", ["2510.01234", "日本語", "ÄÖÜ ß", "a_b", "x" * 500, None, "!!"]
)
def test_item_id_matches_the_schema(mapped_id: str | None) -> None:
    id_schema = load_schema(COLLECTED_SCHEMA)["$defs"]["itemId"]
    result = item_id(SOURCE, mapped_id=mapped_id, canonical=URL)
    assert re.search(id_schema["pattern"], result)
    assert len(result) <= id_schema["maxLength"]
    assert result.isascii()


def test_summary_strips_markup_scripts_and_entities() -> None:
    assert (
        clean_text("<p>Hi <script>x()</script><b>there</b> &amp; you</p>", 100) == "Hi there & you"
    )


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<style>p{color:red}</style>text<!-- note -->more", "text more"),
        ('<a href="javascript:alert(1)" onclick="x()">link</a>', "link"),
        ('<img src=x onerror="alert(1)">caption', "caption"),
        ("<iframe src='https://evil.test'></iframe>safe", "safe"),
    ],
)
def test_clean_text_removes_hostile_markup(html: str, expected: str) -> None:
    assert clean_text(html, 100) == expected


@pytest.mark.parametrize(
    "html",
    [
        "<scr<script>ipt>alert(1)</script>",
        "<<script>script>alert(1)<</script>/script>",
        "<SCRIPT SRC=//evil.test/x.js></SCRIPT>after",
        "<svg onload=alert(1)>x</svg>",
        "<img src=x onerror=alert(1)//",
        "<script>alert(1)",
    ],
)
def test_clean_text_leaves_no_tag_from_evasion_payloads(html: str) -> None:
    result = clean_text(html, 100) or ""
    # A "<" that no tag name follows is plain text (as in "1 < 2"), not the start of a tag.
    assert not re.search(r"<[A-Za-z/!?]", result)


def test_clean_text_replaces_a_lone_surrogate_instead_of_failing() -> None:
    # JSON allows "\ud800" on its own, but it cannot be encoded as UTF-8.
    assert clean_text("a\ud800b", 100) == "a?b"


def test_clean_text_separates_text_that_markup_separated() -> None:
    assert clean_text("<p>First.</p><p>Second.</p>", 100) == "First. Second."
    assert clean_text("one<br>two<br/>three", 100) == "one two three"
    assert clean_text("<ul><li>a</li><li>b</li></ul>", 100) == "a b"


def test_clean_text_collapses_whitespace() -> None:
    raw = "  one \n\n two\t three\N{NO-BREAK SPACE} four&nbsp;five  "
    assert clean_text(raw, 100) == "one two three four five"


def test_clean_text_keeps_a_lone_angle_bracket_as_text() -> None:
    assert clean_text("1 < 2 and 3 > 2", 100) == "1 < 2 and 3 > 2"


def test_clean_text_keeps_escaped_markup_as_plain_text() -> None:
    # Entities decode once: the result is plain text, which a renderer must still escape.
    assert clean_text("Adds &lt;think&gt; tokens", 100) == "Adds <think> tokens"


def test_clean_text_decodes_entities() -> None:
    assert clean_text("caf&eacute; &#169; &quot;q&quot;", 100) == 'café © "q"'


@pytest.mark.parametrize("value", [None, "", "   ", "<p></p>", "<script>x()</script>", "&nbsp;"])
def test_clean_text_without_text_is_none(value: str | None) -> None:
    assert clean_text(value, 100) is None


def test_clean_text_truncates_on_a_word_boundary() -> None:
    result = clean_text("alpha beta gamma delta", 12)
    assert result == "alpha beta…"
    assert result is not None
    assert len(result) <= 12


def test_clean_text_keeps_text_that_fits() -> None:
    assert clean_text("alpha beta", 10) == "alpha beta"
    assert clean_text("alpha betas", 10) == "alpha…"


def test_clean_text_cuts_a_long_word_when_there_is_no_space() -> None:
    assert clean_text("a" * 50, 10) == "a" * 9 + "…"


def test_clean_text_can_cut_at_a_space_in_the_last_position() -> None:
    assert clean_text("abcd efgh ijkl", 10) == "abcd efgh…"


@pytest.mark.parametrize("max_chars", range(1, 40))
def test_clean_text_never_exceeds_max_chars(max_chars: int) -> None:
    text = "The quick brown fox jumps over the lazy dog, then naps for a while."
    result = clean_text(text, max_chars)
    assert result is not None
    assert len(result) <= max_chars
    assert result == text or result.endswith("…")


def test_clean_text_truncates_after_stripping_markup() -> None:
    result = clean_text("<p>" + "<b>word</b> " * 20 + "</p>", 14)
    assert result == "word word…"
