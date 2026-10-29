from typing import Any

import httpx
import pytest
import respx
from collect_helpers import (
    ITEM,
    RECORDED_ON,
    RECORDED_WINDOW,
    collect,
    serving,
)

from pulseai.collect.fetch import FetchError
from pulseai.collect.kinds import KindResult
from pulseai.collect.normalize import parse_timestamp
from pulseai.config import load_config

pytestmark = pytest.mark.anyio

# The same collectors as the default registry's arXiv, Simon Willison, Hugging Face and GitHub
# entries, written out so that registry changes cannot break these tests.
ARXIV: dict[str, Any] = {"kind": "rss", "url": "https://rss.arxiv.org/rss/cs.AI"}
ATOM: dict[str, Any] = {"kind": "atom", "url": "https://simonwillison.net/atom/everything/"}
HF_DAILY_PAPERS: dict[str, Any] = {
    "kind": "json",
    "url": "https://huggingface.co/api/daily_papers?date={date}",
    "items": "[*]",
    "fields": {
        "id": "paper.id",
        "title": "paper.title",
        "url": "join('', ['https://huggingface.co/papers/', paper.id])",
        "published": "publishedAt",
        "summary": "paper.summary",
        "signal": "paper.upvotes",
    },
}
GITHUB_RELEASES: dict[str, Any] = {
    "kind": "json",
    "url": "https://api.github.com/repos/anthropics/claude-code/releases?per_page=10",
    "items": "[?draft==`false`]",
    "fields": {
        "id": "id",
        "title": "name || tag_name",
        "url": "html_url",
        "published": "published_at",
        "summary": "body",
        "extra": {"prerelease": "prerelease", "tag": "tag_name"},
    },
    "http": {"auth_env": "GITHUB_TOKEN", "auth_prefix": "Bearer ", "auth_optional": True},
}


def validated(result: KindResult) -> None:
    """Every item is a valid CollectedItem of the test source, dated inside the window."""
    for item in result.items:
        assert ITEM.validate_python(item.model_dump(mode="json")) == item
        assert item.source_id == "test-source"
        assert item.id.startswith("test-source:")
        assert item.canonical_url.startswith("https://")
        assert item.undated is False
        assert item.published is not None
        published = parse_timestamp(item.published)
        assert published is not None
        assert RECORDED_WINDOW.contains(published)
    assert len({item.id for item in result.items}) == len(result.items)


# --- recorded responses ------------------------------------------------------------------------


@pytest.mark.vcr
@pytest.mark.default_cassette("rss-arxiv.yaml")
async def test_rss_source_from_cassette() -> None:
    result = await collect(ARXIV)

    assert result.url == "https://rss.arxiv.org/rss/cs.AI"
    assert len(result.items) > 0
    assert result.http_status == 200
    assert (result.from_cache, result.redirected_to, result.note, result.unread) == (
        False,
        None,
        None,
        0,
    )
    validated(result)


@pytest.mark.vcr
@pytest.mark.default_cassette("atom-simonwillison.yaml")
async def test_atom_source_from_cassette() -> None:
    result = await collect(ATOM)

    assert result.url == "https://simonwillison.net/atom/everything/"
    assert len(result.items) > 0
    assert result.http_status == 200
    validated(result)
    assert result.dropped_window > 0  # the feed reaches back beyond the window


@pytest.mark.vcr
@pytest.mark.default_cassette("json-hf-daily-papers.yaml")
async def test_json_source_from_cassette() -> None:
    result = await collect(HF_DAILY_PAPERS)

    assert result.url == f"https://huggingface.co/api/daily_papers?date={RECORDED_ON.isoformat()}"
    assert len(result.items) > 0
    validated(result)
    assert all(item.url.startswith("https://huggingface.co/papers/") for item in result.items)
    assert all(item.signal is not None for item in result.items)
    assert result.dropped_window > 0  # some papers were published before the window


@pytest.mark.vcr
@pytest.mark.default_cassette("json-github-releases.yaml")
async def test_github_releases_drop_drafts_keep_prereleases() -> None:
    result = await collect(GITHUB_RELEASES)

    assert len(result.items) > 0
    validated(result)
    # The extra values come through for every release. The API never shows a draft to a
    # request without credentials, so the test below puts one in the data.
    assert all(isinstance(item.extra["prerelease"], bool) for item in result.items)
    assert all(item.extra["tag"] for item in result.items)
    assert result.dropped_window > 0  # older releases


# --- drafts and prereleases, with both in the data ---------------------------------------------

GITHUB_URL = "https://api.github.com/repos/o/r/releases?per_page=10"


def release(number: int, *, draft: bool = False, prerelease: bool = False) -> dict[str, Any]:
    return {
        "id": number,
        "tag_name": f"v{number}",
        "name": None,
        "html_url": f"https://github.com/o/r/releases/tag/v{number}",
        "published_at": "2026-10-28T09:00:00Z",
        "body": f"Release {number}",
        "draft": draft,
        "prerelease": prerelease,
    }


async def test_drafts_are_dropped_and_prereleases_kept() -> None:
    releases = [release(1), release(2, draft=True), release(3, prerelease=True)]
    collector = GITHUB_RELEASES | {"url": GITHUB_URL}

    result = await collect(collector, serving(GITHUB_URL, releases), robots=False)

    assert [(item.title, item.extra) for item in result.items] == [
        ("v1", {"prerelease": False, "tag": "v1"}),
        ("v3", {"prerelease": True, "tag": "v3"}),
    ]
    assert (result.dropped_window, result.dropped_invalid) == (0, 0)


# --- invalid items -----------------------------------------------------------------------------

JSON_URL = "https://api.example.com/v1/items"
FEED_URL = "https://example.com/feed.xml"
JSON_COLLECTOR: dict[str, Any] = {
    "kind": "json",
    "url": JSON_URL,
    "items": "items",
    "fields": {"title": "title", "url": "url", "published": "date"},
}


def rss(*entries: str) -> bytes:
    body = "".join(f"<item>{entry}</item>" for entry in entries)
    return f'<?xml version="1.0"?><rss version="2.0"><channel>{body}</channel></rss>'.encode()


FRESH = "<pubDate>Wed, 28 Oct 2026 10:00:00 GMT</pubDate>"


async def test_source_with_only_invalid_items_fails_invalid_items() -> None:
    document = {"items": [{"title": "No url", "date": "2026-10-28"}, {"title": "Also none"}]}

    with pytest.raises(FetchError) as caught:
        await collect(JSON_COLLECTOR, serving(JSON_URL, document), robots=False)

    assert caught.value.reason == "invalid_items"
    assert caught.value.detail.startswith("all 2 entries")


async def test_feed_with_only_invalid_items_fails_invalid_items() -> None:
    body = rss(f"<title>No link</title>{FRESH}", f"<link>https://example.com/x</link>{FRESH}")
    collector = {"kind": "rss", "url": FEED_URL}

    with pytest.raises(FetchError) as caught:
        await collect(collector, serving(FEED_URL, body), robots=False)

    assert caught.value.reason == "invalid_items"


async def test_source_with_some_invalid_items_succeeds() -> None:
    document = {
        "items": [
            {"title": "No url", "date": "2026-10-28"},
            {"title": "Good", "url": "https://example.com/good", "date": "2026-10-28T10:00:00Z"},
            {"url": "https://example.com/no-title", "date": "2026-10-28"},
            {"title": "Plain http", "url": "http://example.com/http", "date": "2026-10-28"},
        ]
    }

    result = await collect(JSON_COLLECTOR, serving(JSON_URL, document), robots=False)

    assert [item.title for item in result.items] == ["Good"]
    assert (result.dropped_invalid, result.dropped_window) == (3, 0)


async def test_a_valid_entry_outside_the_window_and_an_invalid_one_is_an_empty_success() -> None:
    """Design §12: a source fails only when every entry is malformed; this one has a good entry."""
    document = {
        "items": [
            {"title": "Old", "url": "https://example.com/old", "date": "2020-01-01"},
            {"title": "No url", "date": "2026-10-28"},
        ]
    }

    result = await collect(JSON_COLLECTOR, serving(JSON_URL, document), robots=False)

    assert result.items == []
    assert (result.dropped_window, result.dropped_invalid) == (1, 1)


async def test_the_same_holds_for_a_feed() -> None:
    body = rss(
        "<title>Old</title><link>https://example.com/old</link>"
        "<pubDate>Wed, 01 Jan 2020 10:00:00 GMT</pubDate>",
        f"<title>No link</title>{FRESH}",
    )
    collector = {"kind": "rss", "url": FEED_URL}

    result = await collect(collector, serving(FEED_URL, body), robots=False)

    assert result.items == []
    assert (result.dropped_window, result.dropped_invalid) == (1, 1)


async def test_a_source_with_nothing_in_the_window_is_not_an_error() -> None:
    document = {"items": [{"title": "Old", "url": "https://example.com/old", "date": "2020-01-01"}]}

    result = await collect(JSON_COLLECTOR, serving(JSON_URL, document), robots=False)

    assert (result.items, result.dropped_window, result.dropped_invalid) == ([], 1, 0)


async def test_an_empty_source_is_not_an_error() -> None:
    result = await collect(JSON_COLLECTOR, serving(JSON_URL, {"items": []}), robots=False)

    assert (result.items, result.dropped_window, result.dropped_invalid) == ([], 0, 0)


# --- what run_collector hands on ---------------------------------------------------------------


async def test_the_changelog_flag_keeps_undated_items() -> None:
    document = {"items": [{"title": "Notes", "url": "https://example.com/notes"}]}
    transport = serving(JSON_URL, document)

    kept = await collect(JSON_COLLECTOR, transport, changelog=True, robots=False)
    dropped = await collect(JSON_COLLECTOR, transport, changelog=False, robots=False)

    assert [(item.undated, item.published) for item in kept.items] == [(True, None)]
    assert (dropped.items, dropped.dropped_window) == ([], 1)


async def test_the_url_template_is_expanded_from_the_run() -> None:
    template = "https://api.example.com/v1/items?day={date}&from={since}&n={config.collect.retries}"
    retries = load_config().collect.retries
    expanded = (
        f"https://api.example.com/v1/items?day=2026-10-29&from=2026-10-22T00:00:00Z&n={retries}"
    )
    router = respx.Router()
    route = router.get(expanded).respond(200, json={"items": []})
    collector = JSON_COLLECTOR | {"url": template}

    result = await collect(collector, httpx.MockTransport(router.handler), robots=False)

    assert route.called
    assert result.url == expanded


async def test_a_redirect_to_another_host_is_recorded_by_host() -> None:
    router = respx.Router()
    router.get(FEED_URL).respond(301, headers={"Location": "https://cdn.example.net:8443/f.xml"})
    router.get("https://cdn.example.net:8443/f.xml").respond(
        200, content=rss(f"<title>T</title><link>https://example.com/t</link>{FRESH}")
    )
    collector = {"kind": "rss", "url": FEED_URL}

    result = await collect(collector, httpx.MockTransport(router.handler), robots=False)

    assert result.url == FEED_URL
    assert result.redirected_to == "cdn.example.net:8443"
    assert len(result.items) == 1


async def test_a_redirect_within_the_host_is_not_recorded() -> None:
    router = respx.Router()
    router.get(FEED_URL).respond(301, headers={"Location": "/other.xml"})
    router.get("https://example.com/other.xml").respond(
        200, content=rss(f"<title>T</title><link>https://example.com/t</link>{FRESH}")
    )
    collector = {"kind": "rss", "url": FEED_URL}

    result = await collect(collector, httpx.MockTransport(router.handler), robots=False)

    assert result.redirected_to is None


async def test_a_body_that_is_not_a_feed_fails_parse_error() -> None:
    collector = {"kind": "atom", "url": FEED_URL}

    with pytest.raises(FetchError) as caught:
        await collect(collector, serving(FEED_URL, b"<html>Sorry</html>"), robots=False)

    assert caught.value.reason == "parse_error"


async def test_the_source_http_options_reach_the_fetcher() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"items": []})

    collector = JSON_COLLECTOR | {
        "http": {"auth_env": "SOME_TOKEN", "auth_prefix": "Bearer ", "auth_optional": True}
    }

    await collect(collector, httpx.MockTransport(handler), robots=False)
    await collect(
        collector, httpx.MockTransport(handler), robots=False, environ={"SOME_TOKEN": "tok"}
    )

    assert [request.headers.get("Authorization") for request in seen] == [None, "Bearer tok"]
