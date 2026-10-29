import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pulseai.collect.fetch import FetchError
from pulseai.collect.normalize import parse_timestamp
from pulseai.collect.parsers import RawEntry, parse_feed, parse_json
from pulseai.models.sources import FieldMap

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example</title>
    <link>https://example.com/</link>
    <description>A feed</description>
    <item>
      <title>First post</title>
      <link>https://example.com/first</link>
      <comments>https://example.com/first#comments</comments>
      <category>ai</category>
      <pubDate>Tue, 28 Oct 2026 10:30:00 GMT</pubDate>
      <description>&lt;p&gt;Hello &lt;b&gt;world&lt;/b&gt;&lt;/p&gt;</description>
    </item>
    <item>
      <title>Second post</title>
      <link>https://example.com/second</link>
    </item>
  </channel>
</rss>
"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example</title>
  <id>https://example.com/</id>
  <updated>2026-10-28T12:00:00Z</updated>
  <entry>
    <title>First post</title>
    <link href="https://example.com/first" rel="alternate"/>
    <id>tag:example.com,2026:first</id>
    <published>2026-10-28T10:30:00Z</published>
    <updated>2026-10-28T11:00:00Z</updated>
    <summary>Hello world</summary>
  </entry>
  <entry>
    <title>Second post</title>
    <link href="https://example.com/second" rel="alternate"/>
    <id>tag:example.com,2026:second</id>
    <updated>2026-10-27T08:00:00+02:00</updated>
  </entry>
</feed>
"""

PUBLISHED = datetime(2026, 10, 28, 10, 30, tzinfo=UTC)


def titles_and_urls(entries: list[RawEntry]) -> list[tuple[str | None, str | None]]:
    return [(entry.title, entry.url) for entry in entries]


# --- parse_feed --------------------------------------------------------------------------------


@pytest.mark.parametrize("document", [RSS, ATOM], ids=["rss", "atom"])
def test_parse_feed_rss_and_atom_give_title_url_published(document: bytes) -> None:
    entries = parse_feed(document, None)

    assert titles_and_urls(entries) == [
        ("First post", "https://example.com/first"),
        ("Second post", "https://example.com/second"),
    ]
    assert parse_timestamp(entries[0].published) == PUBLISHED
    assert entries[0].summary is not None
    assert "Hello" in entries[0].summary
    # Nothing in a feed gives an id or a signal, and no fields.extra was asked for.
    assert (entries[0].id, entries[0].signal, dict(entries[0].extra)) == (None, None, {})


def test_parse_feed_entry_without_a_date_has_no_published() -> None:
    entries = parse_feed(RSS, None)

    assert entries[1].published is None
    assert entries[1].summary is None


def test_parse_feed_falls_back_to_updated_and_reads_its_offset() -> None:
    entries = parse_feed(ATOM, None)

    assert parse_timestamp(entries[1].published) == datetime(2026, 10, 27, 6, 0, tzinfo=UTC)


def test_parse_feed_fields_override_picks_other_element() -> None:
    fields = FieldMap.model_validate(
        {
            "title": "title",
            "url": "comments",
            "summary": "tags[0].term",
            "extra": {"first-tag": "tags[0].term"},
        }
    )

    entries = parse_feed(RSS, fields)

    assert entries[0].title == "First post"
    assert entries[0].url == "https://example.com/first#comments"
    assert entries[0].summary == "ai"
    assert dict(entries[0].extra) == {"first-tag": "ai"}
    # The second item has none of these elements.
    assert (entries[1].url, entries[1].summary) == (None, None)
    assert dict(entries[1].extra) == {"first-tag": None}


def test_parse_feed_fields_override_only_what_it_sets() -> None:
    """A fields block that sets title and url still gets the feed's own date and summary."""
    fields = FieldMap.model_validate({"title": "title", "url": "link"})

    entries = parse_feed(RSS, fields)

    assert parse_timestamp(entries[0].published) == PUBLISHED
    assert entries[0].summary is not None


def test_parse_feed_fields_can_map_published_and_id() -> None:
    fields = FieldMap.model_validate(
        {"id": "id", "title": "title", "url": "link", "published": "updated", "signal": "`5`"}
    )

    entries = parse_feed(ATOM, fields)

    assert entries[0].id == "tag:example.com,2026:first"
    assert entries[0].published == "2026-10-28T11:00:00Z"
    assert entries[0].signal == 5


@pytest.mark.parametrize(
    "document",
    [
        b"<html><body><p>Not a feed</p></body></html>",
        b'{"items": []}',
        b"",
        b"<rss><channel><title>cut off",
    ],
    ids=["html", "json", "empty", "truncated"],
)
def test_parse_feed_malformed_raises_fetch_parse_error(document: bytes) -> None:
    with pytest.raises(FetchError) as caught:
        parse_feed(document, None)

    assert caught.value.reason == "parse_error"


def test_parse_feed_keeps_entries_from_a_slightly_broken_feed() -> None:
    """feedparser reads past some XML errors; a bozo feed that still has entries is used."""
    broken = RSS.replace(b"</channel>", b"<stray>&oops;</channel>")

    entries = parse_feed(broken, None)

    assert len(entries) == 2


def test_parse_feed_valid_feed_without_entries_is_empty() -> None:
    document = b'<?xml version="1.0"?><rss version="2.0"><channel><title>T</title></channel></rss>'

    assert parse_feed(document, None) == []


def test_parse_feed_never_treats_content_as_a_path(tmp_path: Path) -> None:
    """feedparser opens a bytes argument as a file name when one exists; fetched text is data."""
    feed = tmp_path / "feed.xml"
    feed.write_bytes(RSS)

    with pytest.raises(FetchError) as caught:
        parse_feed(str(feed).encode(), None)

    assert caught.value.reason == "parse_error"


def test_parse_feed_invalid_fields_expression_is_parse_error() -> None:
    fields = FieldMap.model_validate({"title": "title", "url": "link[["})

    with pytest.raises(FetchError) as caught:
        parse_feed(RSS, fields)

    assert caught.value.reason == "parse_error"


# --- parse_json --------------------------------------------------------------------------------

HF_FIELDS = FieldMap.model_validate(
    {
        "id": "paper.id",
        "title": "paper.title",
        "url": "join('', ['https://huggingface.co/papers/', paper.id])",
        "published": "publishedAt",
        "summary": "paper.summary",
        "signal": "paper.upvotes",
    }
)

HF_DAILY_PAPERS: list[dict[str, Any]] = [
    {
        "paper": {
            "id": "2510.01234",
            "title": "A Paper",
            "summary": "What it does.",
            "upvotes": 12,
        },
        "publishedAt": "2026-10-28T03:00:00.000Z",
    },
    {
        "paper": {"id": "2510.05678", "title": "Another", "summary": None, "upvotes": 0},
        "publishedAt": "2026-10-28T04:30:00.000Z",
    },
]


def encode(document: object) -> bytes:
    return json.dumps(document).encode()


def test_parse_json_maps_items_and_fields() -> None:
    entries = parse_json(encode(HF_DAILY_PAPERS), "[*]", HF_FIELDS)

    assert entries == [
        RawEntry(
            id="2510.01234",
            title="A Paper",
            url="https://huggingface.co/papers/2510.01234",
            published="2026-10-28T03:00:00.000Z",
            summary="What it does.",
            signal=12,
            extra={},
        ),
        RawEntry(
            id="2510.05678",
            title="Another",
            url="https://huggingface.co/papers/2510.05678",
            published="2026-10-28T04:30:00.000Z",
            summary=None,
            signal=0,
            extra={},
        ),
    ]


def test_parse_json_selects_items_with_the_items_expression() -> None:
    document = {"hits": [{"t": "A", "u": "https://example.com/a"}], "meta": {"total": 1}}
    fields = FieldMap.model_validate({"title": "t", "url": "u"})

    entries = parse_json(encode(document), "hits[*]", fields)

    assert titles_and_urls(entries) == [("A", "https://example.com/a")]


def test_parse_json_extra_fields() -> None:
    """GitHub: extra {"prerelease": "prerelease"} lands in RawEntry.extra."""
    releases = [
        {
            "id": 1,
            "name": "v2.0.0-rc1",
            "html_url": "https://github.com/o/r/releases/tag/v2.0.0-rc1",
        }
        | {"draft": False, "prerelease": True, "published_at": "2026-10-28T09:00:00Z"},
        {"id": 2, "name": "v1.9.0", "html_url": "https://github.com/o/r/releases/tag/v1.9.0"}
        | {"draft": False, "prerelease": False, "published_at": "2026-10-20T09:00:00Z"},
        {"id": 3, "name": "v2.1.0", "html_url": "https://github.com/o/r/releases/tag/v2.1.0"}
        | {"draft": True, "prerelease": False, "published_at": None},
    ]
    fields = FieldMap.model_validate(
        {
            "id": "id",
            "title": "name",
            "url": "html_url",
            "published": "published_at",
            "extra": {"prerelease": "prerelease", "missing": "no_such_key"},
        }
    )

    entries = parse_json(encode(releases), "[?draft==`false`]", fields)

    assert [(e.id, e.title) for e in entries] == [("1", "v2.0.0-rc1"), ("2", "v1.9.0")]
    assert [dict(e.extra) for e in entries] == [
        {"prerelease": True, "missing": None},
        {"prerelease": False, "missing": None},
    ]


def test_parse_json_an_error_in_one_entry_leaves_that_field_empty() -> None:
    """join() cannot take a number, so that entry has no url; the others are mapped."""
    document = [
        {"paper": {"id": 7, "title": "Number id"}},
        {"paper": {"id": "8", "title": "String id"}},
    ]

    entries = parse_json(encode(document), "[*]", HF_FIELDS)

    assert [(e.id, e.title, e.url) for e in entries] == [
        ("7", "Number id", None),
        ("8", "String id", "https://huggingface.co/papers/8"),
    ]


def test_parse_json_entries_that_are_not_objects_have_nothing_mapped() -> None:
    # JMESPath projections leave out null, so the null is not an entry.
    entries = parse_json(encode([1, "x", None, {"paper": {"title": "T"}}]), "[*]", HF_FIELDS)

    assert [entry.title for entry in entries] == [None, None, "T"]


@pytest.mark.parametrize(
    "content",
    [b"not json", b"", b"\xff\xfe\x00", b"[" * 100_000, b'{"a": 1,}'],
    ids=["text", "empty", "not-utf8", "too-deep", "trailing-comma"],
)
def test_parse_json_invalid_json_is_parse_error(content: bytes) -> None:
    with pytest.raises(FetchError) as caught:
        parse_json(content, "[*]", HF_FIELDS)

    assert caught.value.reason == "parse_error"


@pytest.mark.parametrize(
    ("document", "items"),
    [
        ({"data": {"a": 1}}, "data"),
        ({"data": "text"}, "data"),
        ({"data": []}, "missing"),
        ([1, 2], "length(@)"),
        ({"hits": [1]}, "[*]"),
    ],
    ids=["object", "string", "missing-key", "number", "wrong-shape"],
)
def test_parse_json_items_not_a_list_is_parse_error(document: object, items: str) -> None:
    with pytest.raises(FetchError) as caught:
        parse_json(encode(document), items, HF_FIELDS)

    assert caught.value.reason == "parse_error"


def test_parse_json_an_empty_list_of_items_is_fine() -> None:
    assert parse_json(encode({"hits": []}), "hits", HF_FIELDS) == []


@pytest.mark.parametrize("expression", ["((", "no_such_function(@)", "length(@, @)"])
def test_parse_json_bad_expression_is_parse_error(expression: str) -> None:
    for items, fields in (
        (expression, HF_FIELDS),
        ("[*]", FieldMap.model_validate({"title": expression, "url": "x"})),
    ):
        with pytest.raises(FetchError) as caught:
            parse_json(encode([{"x": 1}]), items, fields)

        assert caught.value.reason == "parse_error"
