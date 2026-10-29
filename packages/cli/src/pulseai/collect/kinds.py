"""Run one collector source: fetch it, parse it by its kind, and build its items."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, assert_never
from urllib.parse import urlsplit

from pulseai.collect.fetch import Fetcher, FetchError, FetchResult
from pulseai.collect.items import BuildResult, build_items
from pulseai.collect.parsers import RawEntry, parse_feed, parse_json
from pulseai.collect.window import Window, expand_url
from pulseai.models.collected import CollectedItem
from pulseai.models.config import CollectConfig
from pulseai.models.sources import (
    Collector,
    CollectorSource,
    FeedCollector,
    JsonCollector,
    SitemapCollector,
    SnapshotCollector,
)


@dataclass(frozen=True)
class SourceContext:
    """What every source run shares: the fetcher, the window, the run, and the settings."""

    fetcher: Fetcher
    window: Window
    run_date: date
    settings: CollectConfig
    config: Mapping[str, Any]  # the effective config as plain data, for {config.*} in URLs
    now: datetime


@dataclass(frozen=True)
class KindResult:
    """What one source gave: its items, what was dropped, and how the fetch went."""

    url: str  # the URL asked for, with its template variables expanded
    items: list[CollectedItem]
    dropped_window: int
    dropped_invalid: int
    from_cache: bool
    http_status: int | None
    redirected_to: str | None  # the host a redirect ended on, when not the one asked for
    note: str | None = None
    unread: int = 0


async def run_collector(source: CollectorSource, ctx: SourceContext) -> KindResult:
    """Collect one source by the kind of its collector. Raises FetchError when it fails."""
    collector = source.collector
    match collector:
        case FeedCollector():
            url, fetched = await _fetch(collector, ctx)
            entries = parse_feed(fetched.content, collector.fields)
            return _windowed(source, ctx, url, fetched, entries)
        case JsonCollector():
            url, fetched = await _fetch(collector, ctx)
            entries = parse_json(fetched.content, collector.items, collector.fields)
            return _windowed(source, ctx, url, fetched, entries)
        case SnapshotCollector():
            msg = "json-snapshot-diff sources are not collected yet"
            raise NotImplementedError(msg)
        case SitemapCollector():
            msg = "sitemap sources are not collected yet"
            raise NotImplementedError(msg)
        case _:  # pyright reports a collector kind that no case above handles
            assert_never(collector)


async def _fetch(collector: Collector, ctx: SourceContext) -> tuple[str, FetchResult]:
    """The expanded URL and its response, fetched under the source's own http options."""
    url = expand_url(collector.url, run_date=ctx.run_date, window=ctx.window, config=ctx.config)
    return url, await ctx.fetcher.get(url, collector.http)


def _windowed(
    source: CollectorSource,
    ctx: SourceContext,
    url: str,
    fetched: FetchResult,
    entries: list[RawEntry],
) -> KindResult:
    """The result for a kind whose items are filtered by the window (rss, atom and json)."""
    built = build_items(
        entries,
        source_id=source.id,
        window=ctx.window,
        changelog=bool(source.changelog),
        settings=ctx.settings,
    )
    return _result(url, fetched, built)


def _result(url: str, fetched: FetchResult, built: BuildResult) -> KindResult:
    """The source's result, or a failure when nothing was kept and some entries were invalid.

    Each kind goes through this, so a source whose entries are all malformed fails the same way
    whatever its kind.
    """
    if not built.items and built.dropped_invalid:
        msg = (
            f"{built.dropped_invalid} entries had no usable title or https URL, "
            "and no item was kept"
        )
        raise FetchError("invalid_items", msg)
    return KindResult(
        url=url,
        items=built.items,
        dropped_window=built.dropped_window,
        dropped_invalid=built.dropped_invalid,
        from_cache=fetched.from_cache,
        http_status=fetched.status,
        redirected_to=_redirected_to(url, fetched.final_url),
    )


def _redirected_to(requested: str, final: str) -> str | None:
    """The host (and port, when not the default) the response came from, if not the one asked."""
    asked, ended = urlsplit(requested), urlsplit(final)
    if ended.hostname is None or ended.hostname == asked.hostname:
        return None
    return f"{ended.hostname}:{ended.port}" if ended.port else ended.hostname
