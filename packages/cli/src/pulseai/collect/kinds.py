"""Run one collector source: fetch it, parse it by its kind, and build its items."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, assert_never
from urllib.parse import urlsplit

from pulseai.collect.fetch import Fetcher, FetchError, FetchResult
from pulseai.collect.items import BuildResult, build_items
from pulseai.collect.parsers import RawEntry, parse_feed, parse_json, parse_json_keyed
from pulseai.collect.snapshots import (
    SnapshotStore,
    diff_snapshot,
    snapshot_document,
    stored_entry,
)
from pulseai.collect.window import Window, expand_url
from pulseai.models.collected import CollectedItem, ItemChange
from pulseai.models.config import CollectConfig
from pulseai.models.sources import (
    Collector,
    CollectorSource,
    FeedCollector,
    JsonCollector,
    SitemapCollector,
    SnapshotCollector,
)

# The note on the result of a snapshot source's first run: it has nothing to compare with yet.
BASELINE_NOTE = "baseline created"


@dataclass(frozen=True)
class SourceContext:
    """What every source run shares: the fetcher, the window, the run, and the settings."""

    fetcher: Fetcher
    window: Window
    run_date: date
    settings: CollectConfig
    config: Mapping[str, Any]  # the effective config as plain data, for {config.*} in URLs
    snapshots: SnapshotStore
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
    """Collect one source by the kind of its collector. Raises FetchError when it fails.

    A snapshot source also writes its snapshot, but only once it has succeeded. That raises
    OSError when the snapshot directory cannot be written.
    """
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
            return await _snapshot(source, collector, ctx)
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


def _result(
    url: str,
    fetched: FetchResult,
    built: BuildResult,
    *,
    valid: int | None = None,
    note: str | None = None,
    malformed: str = "no usable title or https URL",
) -> KindResult:
    """The source's result, or a failure when every entry it returned was invalid (design §12).

    Each kind goes through this, so a source whose entries are all malformed fails the same way
    whatever its kind. `dropped_window` counts only valid entries, so any of them means the
    source did return something usable and an empty result is a success.

    `valid` is how many valid entries the response held, for a kind whose items are not simply
    those entries: a snapshot source gives no item for an entry that did not change, and gives
    one for an entry the response no longer holds. By default it is the items and the entries the
    window dropped.
    """
    held = len(built.items) + built.dropped_window if valid is None else valid
    if built.dropped_invalid and not held:
        msg = f"all {built.dropped_invalid} entries had {malformed}, so no item was kept"
        raise FetchError("invalid_items", msg)
    return KindResult(
        url=url,
        items=built.items,
        dropped_window=built.dropped_window,
        dropped_invalid=built.dropped_invalid,
        from_cache=fetched.from_cache,
        http_status=fetched.status,
        redirected_to=_redirected_to(url, fetched.final_url),
        note=note,
    )


async def _snapshot(
    source: CollectorSource, collector: SnapshotCollector, ctx: SourceContext
) -> KindResult:
    """A json-snapshot-diff source: one item per entry added, removed, or changed (design §8.4).

    The new snapshot is compared with the latest one dated before the run date, so running a date
    again gives the same items. With no earlier snapshot there is nothing to compare, so the
    result has no items and the note says a baseline was created.

    The changes are items from the start, so the window does not apply to them. Every entry of the
    response goes through `build_items`, not only the ones that changed, so a source whose entries
    are all malformed fails on its first run and not only on a day that something changes; the
    items of unchanged entries are left out of the result. A removed entry is not in the response,
    so it is built from the earlier snapshot, and one that can no longer be built is not counted.
    The snapshot is written last, after the source has succeeded.
    """
    url, fetched = await _fetch(collector, ctx)
    rows = parse_json_keyed(
        fetched.content,
        collector.items,
        collector.fields,
        collector.key,
        collector.track or [],
    )
    current, unkeyed = snapshot_document(rows)
    previous = ctx.snapshots.previous(source.id, ctx.run_date)
    old_entries: Mapping[str, Mapping[str, Any]] = {} if previous is None else previous["entries"]
    changes: dict[str, ItemChange] = (
        {} if previous is None else dict(diff_snapshot(previous, current))
    )
    entries = {key: stored_entry(record) for key, record in current["entries"].items()}
    removed = {
        key: stored_entry(old_entries[key])
        for key, change in changes.items()
        if change.kind == "removed"
    }
    # build_items asks for an entry's change before it checks the entry, and entries cannot be
    # dict keys (they hold dicts), so the lookup is by the entry object itself.
    change_of = {
        id(entry): changes[key] for key, entry in (entries | removed).items() if key in changes
    }

    def build(subject: Iterable[RawEntry]) -> BuildResult:
        return build_items(
            subject,
            source_id=source.id,
            window=None,
            changelog=bool(source.changelog),
            settings=ctx.settings,
            detected_at=ctx.now,
            change=lambda entry: change_of.get(id(entry)),
        )

    built = build(entries.values())
    reported = [item for item in built.items if item.change is not None]
    seen = {item.id for item in reported}
    reported += [item for item in build(removed.values()).items if item.id not in seen]
    result = _result(
        url,
        fetched,
        BuildResult(
            items=reported, dropped_window=0, dropped_invalid=built.dropped_invalid + unkeyed
        ),
        valid=len(built.items),
        note=BASELINE_NOTE if previous is None else None,
        malformed="no usable key, title, or https URL",
    )
    ctx.snapshots.write(source.id, ctx.run_date, current)
    return result


def _redirected_to(requested: str, final: str) -> str | None:
    """The host (and port, when not the default) the response came from, if not the one asked."""
    asked, ended = urlsplit(requested), urlsplit(final)
    if ended.hostname is None or ended.hostname == asked.hostname:
        return None
    return f"{ended.hostname}:{ended.port}" if ended.port else ended.hostname
