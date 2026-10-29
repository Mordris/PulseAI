import gzip
import json
import logging
import warnings
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from collect_helpers import ITEM, NOW, collect

from pulseai.collect.fetch import FetchError
from pulseai.collect.kinds import EMPTY_NOTE, KindResult
from pulseai.collect.normalize import format_timestamp
from pulseai.collect.parsers import parse_sitemap
from pulseai.collect.snapshots import SnapshotStore
from pulseai.config import load_config
from pulseai.models.collected import CollectedItem, FieldChange
from pulseai.models.config import CollectConfig

pytestmark = pytest.mark.anyio

MAX_BYTES = load_config().collect.max_response_bytes
NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"

# --- parse_sitemap -----------------------------------------------------------------------------


def urlset(*entries: tuple[str, str | None]) -> bytes:
    """A sitemap of `(loc, lastmod)` entries; a lastmod of None leaves the element out."""
    rows = "".join(
        f"<url><loc>{loc}</loc>" + (f"<lastmod>{lastmod}</lastmod>" if lastmod else "") + "</url>"
        for loc, lastmod in entries
    )
    return f'<?xml version="1.0"?><urlset xmlns="{NAMESPACE}">{rows}</urlset>'.encode()


def index(*children: str) -> bytes:
    rows = "".join(f"<sitemap><loc>{loc}</loc></sitemap>" for loc in children)
    return f'<?xml version="1.0"?><sitemapindex xmlns="{NAMESPACE}">{rows}</sitemapindex>'.encode()


def test_parse_sitemap_urlset_and_lastmod() -> None:
    content = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
            xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
      <url><loc>  https://e.com/a  </loc><lastmod>2026-10-28</lastmod></url>
      <url>
        <loc>https://e.com/b</loc><lastmod>2026-10-27T10:30:00+02:00</lastmod>
        <image:image><image:loc>https://e.com/b.png</image:loc></image:image>
      </url>
      <url><loc>https://e.com/c</loc></url>
      <url><loc>https://e.com/d</loc><lastmod>soon</lastmod></url>
      <url><loc>https://e.com/e</loc><lastmod>2026-10-28T10:00:00.250Z</lastmod></url>
      <url><loc></loc></url>
      <url><lastmod>2026-10-28</lastmod></url>
      <url><loc>ftp://e.com/f</loc></url>
      <url><loc>https://e.com/a b</loc></url>
      <url><loc>https://e.com/line
break</loc></url>
      <url><loc>https:///g</loc></url>
      <url><loc>https://e.com/a</loc><lastmod>2020-01-01</lastmod></url>
    </urlset>"""

    document = parse_sitemap(content, MAX_BYTES)

    assert document.children == []
    # A date alone is midnight UTC; an offset is converted; a lastmod that is not a date is None;
    # an entry with no usable loc is left out; the first of two entries for a URL stays.
    assert document.urls == {
        "https://e.com/a": datetime(2026, 10, 28, tzinfo=UTC),
        "https://e.com/b": datetime(2026, 10, 27, 8, 30, tzinfo=UTC),
        "https://e.com/c": None,
        "https://e.com/d": None,
        "https://e.com/e": datetime(2026, 10, 28, 10, 0, 0, 250_000, tzinfo=UTC),
    }
    assert list(document.urls) == [f"https://e.com/{name}" for name in "abcde"]


def test_parse_sitemap_index_lists_children() -> None:
    content = b"""<?xml version="1.0"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://e.com/s1.xml</loc><lastmod>2026-10-28</lastmod></sitemap>
      <sitemap><loc> https://e.com/s2.xml.gz </loc></sitemap>
      <sitemap><loc>mailto:someone@e.com</loc></sitemap>
      <sitemap><lastmod>2026-10-28</lastmod></sitemap>
    </sitemapindex>"""

    document = parse_sitemap(content, MAX_BYTES)

    assert document.children == ["https://e.com/s1.xml", "https://e.com/s2.xml.gz"]
    assert document.urls == {}


@pytest.mark.parametrize(
    "content",
    [
        b"<urlset><url><loc>https://e.com/a</loc></url></urlset>",
        b'<ns0:urlset xmlns:ns0="urn:other"><ns0:url><ns0:loc>https://e.com/a</ns0:loc></ns0:url></ns0:urlset>',
    ],
    ids=["no-namespace", "other-prefix"],
)
def test_parse_sitemap_does_not_depend_on_the_namespace(content: bytes) -> None:
    assert parse_sitemap(content, MAX_BYTES).urls == {"https://e.com/a": None}


def test_parse_sitemap_gzip() -> None:
    plain = urlset(("https://e.com/a", "2026-10-28"))
    packed = gzip.compress(plain)

    assert packed.startswith(b"\x1f\x8b")
    assert parse_sitemap(packed, MAX_BYTES) == parse_sitemap(plain, MAX_BYTES)
    assert parse_sitemap(gzip.compress(index("https://e.com/s1.xml")), MAX_BYTES).children == [
        "https://e.com/s1.xml"
    ]


BILLION_LAUGHS = b"""<?xml version="1.0"?>
<!DOCTYPE urlset [
  <!ENTITY a "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa">
  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
  <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">
  <!ENTITY d "&c;&c;&c;&c;&c;&c;&c;&c;&c;&c;">
  <!ENTITY e "&d;&d;&d;&d;&d;&d;&d;&d;&d;&d;">
  <!ENTITY f "&e;&e;&e;&e;&e;&e;&e;&e;&e;&e;">
  <!ENTITY g "&f;&f;&f;&f;&f;&f;&f;&f;&f;&f;">
]>
<urlset><url><loc>https://e.com/&g;</loc></url></urlset>"""
EXTERNAL_ENTITY = b"""<?xml version="1.0"?>
<!DOCTYPE urlset [<!ENTITY secret SYSTEM "file:///etc/hostname">]>
<urlset><url><loc>https://e.com/&secret;</loc></url></urlset>"""
EXTERNAL_PARAMETER_ENTITY = b"""<?xml version="1.0"?>
<!DOCTYPE urlset [<!ENTITY % remote SYSTEM "http://evil.example/x.dtd"> %remote;]>
<urlset><url><loc>https://e.com/a</loc></url></urlset>"""


@pytest.mark.parametrize(
    "content",
    [BILLION_LAUGHS, EXTERNAL_ENTITY, EXTERNAL_PARAMETER_ENTITY],
    ids=["billion-laughs", "external-entity", "external-parameter-entity"],
)
def test_sitemap_entity_expansion_is_rejected(content: bytes) -> None:
    for sent in (content, gzip.compress(content)):
        with pytest.raises(FetchError) as caught:
            parse_sitemap(sent, MAX_BYTES)

        assert caught.value.reason == "parse_error"


def test_gzip_bomb_over_cap_is_too_large() -> None:
    cap = 10_000
    bomb = gzip.compress(b"<urlset>" + b" " * 5_000_000 + b"</urlset>")

    assert len(bomb) < cap  # it passes the size check on what was received
    with pytest.raises(FetchError) as caught:
        parse_sitemap(bomb, cap)

    assert caught.value.reason == "too_large"


def test_the_cap_applies_to_the_decompressed_document_byte_for_byte() -> None:
    body = urlset(("https://e.com/a", None))
    cap = len(body)

    assert parse_sitemap(gzip.compress(body), cap).urls == {"https://e.com/a": None}
    assert parse_sitemap(body, cap).urls == {"https://e.com/a": None}
    for sent in (body, gzip.compress(body)):
        with pytest.raises(FetchError) as caught:
            parse_sitemap(sent, cap - 1)

        assert caught.value.reason == "too_large"


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"not xml at all",
        b"<urlset><url>",
        b"<html><body>Sorry</body></html>",
        b"<urlset>\x00</urlset>",
        b'<?xml version="1.0" encoding="no-such-encoding"?><urlset/>',
        b"\x1f\x8b not really gzip",
        gzip.compress(b"<urlset></urlset>")[:-10],
        gzip.compress(b"x" * 100),
    ],
    ids=[
        "empty",
        "text",
        "truncated-xml",
        "not-a-sitemap",
        "nul",
        "unknown-encoding",
        "bad-gzip",
        "truncated-gzip",
        "gzip-of-text",
    ],
)
def test_parse_sitemap_fails_parse_error_for_what_is_not_a_sitemap(content: bytes) -> None:
    with pytest.raises(FetchError) as caught:
        parse_sitemap(content, MAX_BYTES)

    assert caught.value.reason == "parse_error"


# --- a site in memory --------------------------------------------------------------------------

HOST = "https://news.example.com"
SITEMAP = f"{HOST}/sitemap.xml"
ROBOTS = f"{HOST}/robots.txt"
COLLECTOR: dict[str, Any] = {"kind": "sitemap", "url": SITEMAP, "include": ["/news/*"]}
SOURCE = "test-source"

DAY_1 = date(2026, 10, 27)
DAY_2 = date(2026, 10, 28)
DAY_3 = date(2026, 10, 29)


def article(slug: str, host: str = HOST) -> str:
    return f"{host}/news/{slug}"


def page(
    title: str | None = "A title",
    *,
    published: str | None = "2026-10-28",
    description: str | None = "About it.",
) -> bytes:
    """An article page whose metadata is OpenGraph, as the sites this kind is for write it."""
    head = ""
    if title is not None:
        head += f'<title>{title} | Example</title><meta property="og:title" content="{title}">'
    if published is not None:
        head += f'<meta property="article:published_time" content="{published}">'
    if description is not None:
        head += f'<meta property="og:description" content="{description}">'
    return f"<html><head>{head}</head><body><p>The body.</p></body></html>".encode()


class Site:
    """Web servers in memory. `serve` sets a response; every request is recorded, and anything
    not served is a 404, robots.txt included (which allows everything).
    """

    def __init__(self) -> None:
        self.responses: dict[str, tuple[int, dict[str, str], bytes]] = {}
        self.requests: list[httpx.Request] = []
        self.transport = httpx.MockTransport(self._handle)

    def serve(
        self,
        url: str,
        body: bytes,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.responses[url] = (status, headers or {}, body)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, headers, body = self.responses.get(str(request.url), (404, {}, b""))
        return httpx.Response(status, headers=headers, content=body)

    @property
    def fetched(self) -> list[str]:
        """The URLs asked for, in order, without robots.txt."""
        return [str(r.url) for r in self.requests if r.url.path != "/robots.txt"]


@pytest.fixture
def site() -> Site:
    return Site()


@pytest.fixture
def store(tmp_path: Path) -> SnapshotStore:
    return SnapshotStore(tmp_path, keep=load_config().collect.snapshot_keep)


async def run_day(
    site: Site,
    store: SnapshotStore,
    run_date: date,
    *entries: tuple[str, str | None],
    collector: dict[str, Any] = COLLECTOR,
    settings: CollectConfig | None = None,
    environ: dict[str, str] | None = None,
) -> KindResult:
    """Run the source on a day whose sitemap holds `entries`."""
    site.serve(SITEMAP, urlset(*entries))
    return await collect(
        collector,
        site.transport,
        run_date=run_date,
        snapshots=store,
        settings=settings,
        environ=environ,
    )


def snapshot(tmp_path: Path, run_date: date) -> dict[str, Any]:
    path = tmp_path / "state" / "snapshots" / SOURCE / f"{run_date.isoformat()}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot_files(tmp_path: Path) -> list[str]:
    directory = tmp_path / "state" / "snapshots" / SOURCE
    return sorted(path.name for path in directory.iterdir()) if directory.exists() else []


def dumped(items: list[CollectedItem]) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in items]


def with_settings(**changes: int) -> CollectConfig:
    return load_config().collect.model_copy(update=changes)


# --- the first run -----------------------------------------------------------------------------


async def test_first_run_is_baseline(tmp_path: Path, site: Site, store: SnapshotStore) -> None:
    result = await run_day(
        site,
        store,
        DAY_1,
        (article("a"), "2026-10-20"),
        (article("b"), None),
        (f"{HOST}/careers/c", "2026-10-21"),  # outside include
    )

    assert result.items == []
    assert result.note == "baseline created"
    assert (result.dropped_window, result.dropped_invalid, result.unread) == (0, 0, 0)
    assert (result.url, result.http_status, result.from_cache) == (SITEMAP, 200, False)
    # Only the sitemap was read: with nothing to compare there is no candidate and no page read.
    assert site.fetched == [SITEMAP]
    assert snapshot(tmp_path, DAY_1) == {
        "entries": {article("a"): "2026-10-20T00:00:00Z", article("b"): None}
    }


async def test_a_sitemap_without_matching_urls_gets_an_empty_baseline(
    tmp_path: Path, site: Site, store: SnapshotStore
) -> None:
    result = await run_day(site, store, DAY_1, (f"{HOST}/careers/c", None))

    assert (result.items, result.note) == ([], "baseline created")
    assert snapshot(tmp_path, DAY_1) == {"entries": {}}


# --- later runs --------------------------------------------------------------------------------


async def test_new_url_under_include_becomes_item(
    tmp_path: Path, site: Site, store: SnapshotStore
) -> None:
    await run_day(site, store, DAY_1, (article("old"), "2026-10-01"))
    site.serve(
        article("new"),
        page("Claude gets a new model", published="2026-10-28", description="It is faster."),
    )

    result = await run_day(
        site,
        store,
        DAY_2,
        (article("old"), "2026-10-01"),
        (article("new"), "2026-10-28T09:30:00Z"),
        (f"{HOST}/careers/new", "2026-10-28"),
    )

    [item] = result.items
    assert item.title == "Claude gets a new model"
    assert item.summary == "It is faster."
    assert (item.published, item.undated) == ("2026-10-28T00:00:00Z", False)
    assert (item.url, item.canonical_url) == (article("new"), article("new"))
    assert item.source_id == SOURCE
    assert item.detected_at == format_timestamp(NOW)
    assert item.change is not None
    assert item.change.kind == "added"
    assert item.change.fields == [FieldChange(path="lastmod", old=None, new="2026-10-28T09:30:00Z")]
    assert ITEM.validate_python(item.model_dump(mode="json")) == item
    assert (result.note, result.dropped_window, result.dropped_invalid, result.unread) == (
        None,
        0,
        0,
        0,
    )
    # The old page is known and the careers page is outside include: neither is read.
    assert site.fetched == [SITEMAP, SITEMAP, article("new")]
    assert snapshot(tmp_path, DAY_2) == {
        "entries": {article("old"): "2026-10-01T00:00:00Z", article("new"): "2026-10-28T09:30:00Z"}
    }


async def test_a_new_url_without_lastmod_is_still_added(site: Site, store: SnapshotStore) -> None:
    await run_day(site, store, DAY_1, (article("old"), None))
    site.serve(article("new"), page())

    result = await run_day(site, store, DAY_2, (article("old"), None), (article("new"), None))

    [item] = result.items
    assert item.change is not None
    assert (item.change.kind, item.change.fields) == ("added", [])


async def test_the_window_does_not_filter_candidates(site: Site, store: SnapshotStore) -> None:
    await run_day(site, store, DAY_1, (article("old"), None))
    site.serve(article("new"), page(published="2019-03-04"))  # years before the window

    result = await run_day(site, store, DAY_2, (article("old"), None), (article("new"), None))

    [item] = result.items
    assert item.published == "2019-03-04T00:00:00Z"
    assert result.dropped_window == 0


async def test_a_page_without_a_date_is_reported_undated(site: Site, store: SnapshotStore) -> None:
    await run_day(site, store, DAY_1, (article("old"), None))
    site.serve(article("new"), page(published=None))

    result = await run_day(site, store, DAY_2, (article("old"), None), (article("new"), None))

    [item] = result.items
    assert (item.undated, item.published) == (True, None)
    assert ITEM.validate_python(item.model_dump(mode="json")) == item


async def test_exclude_glob_wins_over_include(
    tmp_path: Path, site: Site, store: SnapshotStore
) -> None:
    collector = COLLECTOR | {"exclude": ["/news/archive/*", "/news/*.pdf"]}
    archived = f"{HOST}/news/archive/2019"
    await run_day(site, store, DAY_1, (article("old"), None), collector=collector)
    site.serve(article("new"), page())
    site.serve(archived, page("Archived"))

    result = await run_day(
        site,
        store,
        DAY_2,
        (article("old"), None),
        (article("new"), None),
        (archived, "2026-10-28"),
        (article("report.pdf"), "2026-10-28"),
        collector=collector,
    )

    assert [item.url for item in result.items] == [article("new")]
    assert archived not in site.fetched
    assert sorted(snapshot(tmp_path, DAY_2)["entries"]) == [article("new"), article("old")]


async def test_include_matches_the_path_not_the_host_or_query(
    site: Site, store: SnapshotStore
) -> None:
    collector = COLLECTOR | {"include": ["/news/*", "/blog/?*"]}
    await run_day(site, store, DAY_1, collector=collector)
    for url in (article("a"), f"{HOST}/blog/x", f"{HOST}/blog/"):
        site.serve(url, page(f"Page {url[-3:]}"))

    result = await run_day(
        site,
        store,
        DAY_2,
        (article("a"), None),
        (f"{HOST}/blog/x", None),  # matches /blog/?*
        (f"{HOST}/blog/", None),  # does not: ? needs a character
        (f"{HOST}/other?ref=/news/a", None),  # the query is not part of the path
        collector=collector,
    )

    assert sorted(item.url for item in result.items) == [f"{HOST}/blog/x", article("a")]


async def test_only_http_urls_are_kept(tmp_path: Path, site: Site, store: SnapshotStore) -> None:
    await run_day(
        site, store, DAY_1, (article("old"), None), ("ftp://news.example.com/news/x", None)
    )

    assert list(snapshot(tmp_path, DAY_1)["entries"]) == [article("old")]


@pytest.mark.parametrize(
    ("before", "after", "reported"),
    [
        ("2026-10-01", "2026-10-20", True),
        ("2026-10-01T08:00:00Z", "2026-10-01T08:00:01Z", True),
        ("2026-10-20", "2026-10-20", False),
        ("2026-10-20", "2026-10-01", False),  # moved back
        ("2026-10-01", None, False),  # the lastmod went away
        (None, "2026-10-20", False),  # one appeared; there is nothing to say it moved forward
        ("2026-10-28T10:00:00Z", "2026-10-28T10:00:00.400Z", False),  # fractions are not kept
    ],
)
async def test_updated_lastmod_becomes_updated_item(
    site: Site, store: SnapshotStore, before: str | None, after: str | None, *, reported: bool
) -> None:
    await run_day(site, store, DAY_1, (article("a"), before))
    site.serve(article("a"), page("Changed page"))

    result = await run_day(site, store, DAY_2, (article("a"), after))

    if not reported:
        assert result.items == []
        assert site.fetched.count(article("a")) == 0
        return
    [item] = result.items
    assert item.title == "Changed page"
    assert item.change is not None
    assert item.change.kind == "updated"
    [field] = item.change.fields
    assert field.path == "lastmod"
    assert (field.old, field.new) == (
        format_timestamp(datetime.fromisoformat(before or "")),
        format_timestamp(datetime.fromisoformat(after or "")),
    )


async def test_unchanged_sitemap_emits_nothing(site: Site, store: SnapshotStore) -> None:
    entries = ((article("a"), "2026-10-01"), (article("b"), None))
    await run_day(site, store, DAY_1, *entries)

    result = await run_day(site, store, DAY_2, *reversed(entries))

    assert (result.items, result.note, result.unread) == ([], None, 0)


async def test_added_and_updated_together_are_read_newest_first(
    site: Site, store: SnapshotStore
) -> None:
    await run_day(site, store, DAY_1, (article("u"), "2026-10-01"))
    for slug in ("u", "n1", "n2", "n3"):
        site.serve(article(slug), page(f"Page {slug}"))

    result = await run_day(
        site,
        store,
        DAY_2,
        (article("u"), "2026-10-26"),  # updated
        (article("n1"), "2026-10-25"),
        (article("n2"), "2026-10-27"),
        (article("n3"), None),  # no lastmod: after every dated one
    )

    assert [(item.title, item.change.kind if item.change else None) for item in result.items] == [
        ("Page n2", "added"),
        ("Page u", "updated"),
        ("Page n1", "added"),
        ("Page n3", "added"),
    ]


async def test_candidates_with_the_same_lastmod_are_read_in_url_order(
    site: Site, store: SnapshotStore
) -> None:
    await run_day(site, store, DAY_1)
    for slug in "bca":
        site.serve(article(slug), page(f"Page {slug}"))

    result = await run_day(site, store, DAY_2, *((article(slug), "2026-10-27") for slug in "bca"))

    assert [item.title for item in result.items] == ["Page a", "Page b", "Page c"]


# --- the limits --------------------------------------------------------------------------------


async def test_meta_fetch_limit_counts_unread(
    tmp_path: Path, site: Site, store: SnapshotStore
) -> None:
    collector = COLLECTOR | {"meta_fetch_limit": 2}
    await run_day(site, store, DAY_1, collector=collector)
    entries = [(article(f"p{n}"), f"2026-10-{20 + n}") for n in range(1, 6)]
    for loc, _ in entries:
        site.serve(loc, page(f"Page {loc[-2:]}"))

    result = await run_day(site, store, DAY_2, *entries, collector=collector)

    assert [item.title for item in result.items] == ["Page p5", "Page p4"]  # the newest two
    assert result.unread == 3
    assert (result.dropped_invalid, result.note) == (0, None)
    assert site.fetched == [SITEMAP, SITEMAP, article("p5"), article("p4")]
    # The snapshot still lists every matching URL, so the unread ones are not candidates again.
    assert list(snapshot(tmp_path, DAY_2)["entries"]) == [loc for loc, _ in entries]


async def test_meta_fetch_limit_defaults_to_the_config(site: Site, store: SnapshotStore) -> None:
    settings = with_settings(meta_fetch_limit=1)
    await run_day(site, store, DAY_1, settings=settings)
    entries = [(article("a"), "2026-10-20"), (article("b"), "2026-10-21")]
    for loc, _ in entries:
        site.serve(loc, page(f"Page {loc[-1]}"))

    result = await run_day(site, store, DAY_2, *entries, settings=settings)

    assert [item.title for item in result.items] == ["Page b"]
    assert result.unread == 1


async def test_pages_that_fail_use_up_the_limit(site: Site, store: SnapshotStore) -> None:
    collector = COLLECTOR | {"meta_fetch_limit": 2}
    await run_day(site, store, DAY_1, collector=collector)
    site.serve(article("b"), b"", status=404)
    site.serve(article("a"), page("Page a"))

    result = await run_day(
        site,
        store,
        DAY_2,
        (article("b"), "2026-10-27"),
        (article("a"), "2026-10-26"),
        (article("c"), "2026-10-25"),
        collector=collector,
    )

    assert [item.title for item in result.items] == ["Page a"]
    assert (result.dropped_invalid, result.unread) == (1, 1)
    assert article("c") not in site.fetched


# --- sitemap indexes ---------------------------------------------------------------------------

CHILD_1 = f"{HOST}/sitemaps/news-1.xml"
CHILD_2 = f"{HOST}/sitemaps/news-2.xml.gz"
CHILD_3 = f"{HOST}/sitemaps/news-3.xml"


def serve_children(site: Site) -> None:
    """An index of three children: a plain sitemap, a gzipped one, and another plain one."""
    site.serve(SITEMAP, index(CHILD_1, CHILD_2, CHILD_3))
    site.serve(CHILD_1, urlset((article("one"), "2026-10-20")))
    # A .xml.gz file is gzip bytes whatever the server says about them: no Content-Encoding.
    site.serve(
        CHILD_2,
        gzip.compress(urlset((article("two"), "2026-10-21"))),
        headers={"Content-Type": "application/gzip"},
    )
    site.serve(CHILD_3, urlset((article("three"), "2026-10-22")))


async def test_a_sitemap_index_is_followed_one_level_including_gzip(
    tmp_path: Path, site: Site, store: SnapshotStore
) -> None:
    serve_children(site)
    await collect(COLLECTOR, site.transport, run_date=DAY_1, snapshots=store)
    site.serve(CHILD_1, urlset((article("one"), "2026-10-20"), (article("four"), "2026-10-23")))
    site.serve(article("four"), page("Page four"))

    result = await collect(COLLECTOR, site.transport, run_date=DAY_2, snapshots=store)

    assert [item.title for item in result.items] == ["Page four"]
    assert (result.url, result.http_status) == (SITEMAP, 200)  # the index is the source's response
    assert snapshot(tmp_path, DAY_1)["entries"] == {
        article("one"): "2026-10-20T00:00:00Z",
        article("two"): "2026-10-21T00:00:00Z",
        article("three"): "2026-10-22T00:00:00Z",
    }
    assert result.unread == 0


async def test_children_capped_by_max_child_sitemaps(
    tmp_path: Path, site: Site, store: SnapshotStore
) -> None:
    serve_children(site)
    settings = with_settings(max_child_sitemaps=2)

    result = await collect(
        COLLECTOR, site.transport, run_date=DAY_1, snapshots=store, settings=settings
    )

    assert CHILD_3 not in site.fetched
    assert list(snapshot(tmp_path, DAY_1)["entries"]) == [article("one"), article("two")]
    assert result.note == "baseline created; 1 of 3 child sitemaps not read (max_child_sitemaps 2)"
    assert result.items == []


async def test_a_nested_index_inside_a_child_is_not_followed(
    tmp_path: Path, site: Site, store: SnapshotStore
) -> None:
    nested = f"{HOST}/sitemaps/nested.xml"
    site.serve(SITEMAP, index(CHILD_1, CHILD_2))
    site.serve(CHILD_1, index(nested))
    site.serve(nested, urlset((article("deep"), None)))
    site.serve(CHILD_2, urlset((article("two"), None)))

    await collect(COLLECTOR, site.transport, run_date=DAY_1, snapshots=store)

    assert nested not in site.fetched
    assert list(snapshot(tmp_path, DAY_1)["entries"]) == [article("two")]


@pytest.mark.parametrize(
    ("status", "body", "reason"),
    [(404, b"", "http_error"), (200, b"<html>Sorry</html>", "parse_error")],
    ids=["missing", "not-a-sitemap"],
)
async def test_a_child_that_fails_fails_the_source(
    tmp_path: Path, site: Site, store: SnapshotStore, status: int, body: bytes, reason: str
) -> None:
    # Skipping it would drop its URLs from the snapshot, and report them all as new on the day
    # it comes back.
    serve_children(site)
    site.serve(CHILD_2, body, status=status)

    with pytest.raises(FetchError) as caught:
        await collect(COLLECTOR, site.transport, run_date=DAY_1, snapshots=store)

    assert caught.value.reason == reason
    assert snapshot_files(tmp_path) == []


# --- pages that cannot be read -----------------------------------------------------------------


async def test_page_without_title_is_dropped_invalid(site: Site, store: SnapshotStore) -> None:
    await run_day(site, store, DAY_1)
    site.serve(article("good"), page("Good page"))
    site.serve(article("bare"), page(None))

    result = await run_day(site, store, DAY_2, (article("good"), None), (article("bare"), None))

    assert [item.title for item in result.items] == ["Good page"]
    assert (result.dropped_invalid, result.dropped_window) == (1, 0)


async def test_when_no_page_gives_an_item_the_source_fails_and_writes_nothing(
    tmp_path: Path, site: Site, store: SnapshotStore
) -> None:
    await run_day(site, store, DAY_1)
    site.serve(article("bare"), page(None))

    with pytest.raises(FetchError) as caught:
        await run_day(site, store, DAY_2, (article("bare"), None), (article("gone"), None))

    assert caught.value.reason == "invalid_items"
    assert "all 2 entries" in caught.value.detail
    assert snapshot_files(tmp_path) == ["2026-10-27.json"]


async def test_robots_disallowed_page_is_skipped_not_fatal(
    site: Site, store: SnapshotStore
) -> None:
    site.serve(ROBOTS, b"User-agent: *\nDisallow: /news/private\n")
    await run_day(site, store, DAY_1)
    site.serve(article("open"), page("Open page"))
    site.serve(article("private-plans"), page("Private page"))

    result = await run_day(
        site, store, DAY_2, (article("open"), None), (article("private-plans"), None)
    )

    assert [item.title for item in result.items] == ["Open page"]
    assert (result.dropped_invalid, result.note) == (1, None)
    assert article("private-plans") not in site.fetched


@pytest.mark.parametrize(
    ("status", "body"),
    [(404, b""), (500, b""), (200, b"x" * 1_500)],
    ids=["missing", "server-error", "too-large"],
)
async def test_a_page_that_cannot_be_fetched_is_skipped_not_fatal(
    site: Site, store: SnapshotStore, status: int, body: bytes
) -> None:
    settings = with_settings(max_response_bytes=1_000, retries=0)
    await run_day(site, store, DAY_1, settings=settings)
    site.serve(article("open"), page("Open page"))
    site.serve(article("broken"), body, status=status)

    result = await run_day(
        site, store, DAY_2, (article("open"), None), (article("broken"), None), settings=settings
    )

    assert [item.title for item in result.items] == ["Open page"]
    assert result.dropped_invalid == 1


async def test_a_page_comes_through_the_charset_its_response_names(
    site: Site, store: SnapshotStore
) -> None:
    await run_day(site, store, DAY_1)
    latin1 = page("Café noté").decode().encode("iso-8859-1")
    site.serve(article("latin"), latin1, headers={"Content-Type": "text/html; charset=ISO-8859-1"})
    # Bytes that are not valid in the charset assumed (UTF-8) are replaced, not fatal.
    site.serve(article("broken"), latin1)
    site.serve(
        article("odd"), page("Odd page"), headers={"Content-Type": "text/html; charset=nope"}
    )

    result = await run_day(
        site, store, DAY_2, *((article(slug), None) for slug in ("latin", "broken", "odd"))
    )

    titles = {item.url: item.title for item in result.items}
    assert titles[article("latin")] == "Café noté"
    assert titles[article("broken")].startswith("Caf\N{REPLACEMENT CHARACTER}")
    assert titles[article("odd")] == "Odd page"


async def test_reading_pages_raises_no_warning_and_logs_nothing(
    site: Site, store: SnapshotStore, caplog: pytest.LogCaptureFixture
) -> None:
    await run_day(site, store, DAY_1)
    junk = (b"", b"\x00\x01\x02", b"<<<>>>", b"<html", "\N{REPLACEMENT CHARACTER}".encode() * 50)
    slugs = [f"junk{n}" for n in range(len(junk))]
    for slug, body in zip(slugs, junk, strict=True):
        site.serve(article(slug), body)
    site.serve(article("fine"), page("Fine page", published="not a date"))

    with warnings.catch_warnings(record=True) as raised, caplog.at_level(logging.DEBUG):
        warnings.simplefilter("always")
        result = await run_day(site, store, DAY_2, *((article(s), None) for s in [*slugs, "fine"]))

    assert [item.title for item in result.items] == ["Fine page"]
    assert result.dropped_invalid == len(junk)
    assert [str(w.message) for w in raised] == []
    noisy = [
        r for r in caplog.records if r.name.split(".")[0] in {"trafilatura", "htmldate", "lxml"}
    ]
    assert [r.getMessage() for r in noisy if r.levelno >= logging.WARNING] == []


# --- re-runs and the empty response ------------------------------------------------------------


async def test_sitemap_same_date_rerun_gives_same_items(
    tmp_path: Path, site: Site, store: SnapshotStore
) -> None:
    await run_day(site, store, DAY_1, (article("a"), "2026-10-01"))
    site.serve(article("a"), page("Page a"))
    site.serve(article("b"), page("Page b"))
    today = ((article("a"), "2026-10-20"), (article("b"), None))

    first = await run_day(site, store, DAY_2, *today)
    first_file = (tmp_path / "state/snapshots/test-source/2026-10-28.json").read_bytes()
    second = await run_day(site, store, DAY_2, *today)

    assert len(first.items) == 2
    assert dumped(second.items) == dumped(first.items)
    assert (tmp_path / "state/snapshots/test-source/2026-10-28.json").read_bytes() == first_file
    assert snapshot_files(tmp_path) == ["2026-10-27.json", "2026-10-28.json"]


async def test_a_run_compares_with_the_latest_snapshot_before_its_date(
    site: Site, store: SnapshotStore
) -> None:
    await run_day(site, store, DAY_1, (article("a"), None))
    site.serve(article("b"), page("Page b"))
    await run_day(site, store, DAY_2, (article("a"), None), (article("b"), None))
    site.serve(article("c"), page("Page c"))

    result = await run_day(
        site, store, DAY_3, (article("a"), None), (article("b"), None), (article("c"), None)
    )

    assert [item.title for item in result.items] == ["Page c"]


async def test_an_empty_sitemap_keeps_the_previous_snapshot(
    tmp_path: Path, site: Site, store: SnapshotStore
) -> None:
    """A transient empty sitemap must not report every page new on the day it comes back."""
    entries = ((article("a"), "2026-10-01"), (article("b"), None))
    await run_day(site, store, DAY_1, *entries)

    emptied = await run_day(site, store, DAY_2, (f"{HOST}/careers/x", None))
    recovered = await run_day(site, store, DAY_3, *entries)

    assert (emptied.items, emptied.note, emptied.unread) == ([], EMPTY_NOTE, 0)
    assert (emptied.dropped_invalid, emptied.http_status) == (0, 200)
    assert snapshot_files(tmp_path) == ["2026-10-27.json", "2026-10-29.json"]
    assert (recovered.items, recovered.note) == ([], None)
    assert site.fetched.count(article("a")) == 0


async def test_an_empty_sitemap_leaves_the_snapshot_the_date_already_has(
    tmp_path: Path, site: Site, store: SnapshotStore
) -> None:
    entries = ((article("a"), None),)
    await run_day(site, store, DAY_1, *entries)
    site.serve(article("b"), page("Page b"))
    await run_day(site, store, DAY_2, *entries, (article("b"), None))
    before = (tmp_path / "state/snapshots/test-source/2026-10-28.json").read_bytes()

    result = await run_day(site, store, DAY_2)

    assert (result.items, result.note) == ([], EMPTY_NOTE)
    assert (tmp_path / "state/snapshots/test-source/2026-10-28.json").read_bytes() == before


async def test_the_sitemap_root_failing_fails_the_source(
    tmp_path: Path, site: Site, store: SnapshotStore
) -> None:
    site.serve(SITEMAP, b"<html>Sorry</html>")

    with pytest.raises(FetchError) as caught:
        await collect(COLLECTOR, site.transport, run_date=DAY_1, snapshots=store)

    assert caught.value.reason == "parse_error"
    assert snapshot_files(tmp_path) == []


# --- credentials -------------------------------------------------------------------------------


async def test_credentials_go_only_to_the_origin_of_the_sitemap(
    site: Site, store: SnapshotStore
) -> None:
    """The sitemap names the pages and child sitemaps, so it also names where they are fetched."""
    collector = COLLECTOR | {"http": {"auth_env": "SITE_TOKEN", "auth_prefix": "Bearer "}}
    environ = {"SITE_TOKEN": "s3cret"}
    other = "https://elsewhere.example.net"
    site.serve(SITEMAP, index(CHILD_1, f"{other}/sitemap-more.xml"))
    site.serve(CHILD_1, urlset((article("old"), None)))
    site.serve(f"{other}/sitemap-more.xml", urlset((article("far", other), None)))
    await collect(collector, site.transport, run_date=DAY_1, snapshots=store, environ=environ)
    site.serve(article("new"), page("Near page"))
    site.serve(article("fresh", other), page("Far page"))
    site.serve(CHILD_1, urlset((article("old"), None), (article("new"), None)))
    site.serve(
        f"{other}/sitemap-more.xml",
        urlset((article("far", other), None), (article("fresh", other), None)),
    )
    site.requests.clear()

    result = await collect(
        collector, site.transport, run_date=DAY_2, snapshots=store, environ=environ
    )

    assert sorted(item.title for item in result.items) == ["Far page", "Near page"]
    sent = {
        str(request.url): request.headers.get("Authorization")
        for request in site.requests
        if request.url.path != "/robots.txt"
    }
    assert sent[SITEMAP] == "Bearer s3cret"
    assert sent[CHILD_1] == "Bearer s3cret"
    assert sent[article("new")] == "Bearer s3cret"
    assert sent[f"{other}/sitemap-more.xml"] is None
    assert sent[article("fresh", other)] is None
    assert "s3cret" not in repr(result)
