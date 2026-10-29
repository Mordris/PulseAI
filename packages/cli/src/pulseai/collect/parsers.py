"""Turn fetched bytes into raw entries: feeds through feedparser, JSON through JMESPath.

Entries are not checked here. A missing or odd field is None, and `items.build_items` decides
what to do with the entry. A sitemap is read into the URLs it lists, which are not entries yet.
"""

from __future__ import annotations

import gzip
import io
import json
import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from urllib.parse import urlsplit

import feedparser
import jmespath
from defusedxml.ElementTree import ParseError, fromstring
from jmespath.exceptions import JMESPathError, JMESPathTypeError
from jmespath.parser import ParsedResult

from pulseai.collect.fetch import FetchError
from pulseai.collect.normalize import URL_SCHEMES, parse_timestamp
from pulseai.models.sources import FieldMap

# FieldMap keys that map one value to one RawEntry attribute (`extra` maps several).
SCALAR_FIELDS = ("id", "title", "url", "published", "summary", "signal")

# What a feed entry gives when the registry does not map the field. Feeds have no id or signal.
# feedparser's own fields: published_parsed is a struct_time in UTC, parsed from RSS and Atom
# alike; a date it cannot parse is left in the text field.
FEED_DEFAULTS: Mapping[str, str] = {
    "title": "title",
    "url": "link",
    "published": "published_parsed || updated_parsed || published",
    "summary": "summary",
}


# The two bytes every gzip file starts with.
GZIP_MAGIC = b"\x1f\x8b"
# How much of a gzip file is inflated per step, so that the cap is checked long before a bomb has
# filled memory.
GUNZIP_CHUNK_BYTES = 64 * 1024
# The root elements of a sitemap (sitemaps.org): a list of pages, or a list of sitemaps.
SITEMAP_ROOTS = frozenset({"urlset", "sitemapindex"})
# How much of an unexpected root element's name an error message quotes.
ROOT_NAME_CHARS = 40


@dataclass(frozen=True)
class RawEntry:
    """One entry as the source gave it. `published` and `signal` are whatever the source held."""

    id: str | None
    title: str | None
    url: str | None
    published: object
    summary: str | None
    signal: object
    extra: Mapping[str, object]


@dataclass(frozen=True)
class KeyedEntry:
    """One entry of a snapshot source, with what the registry says to compare it by.

    `key` and the `tracked` values (by expression) are whatever the expressions gave, read from
    the same JSON item as `entry`. A key may be missing or not text; the caller decides.
    """

    key: object
    entry: RawEntry
    tracked: Mapping[str, object]


@dataclass(frozen=True)
class _Mapping:
    """A registry field map with its JMESPath expressions compiled once for all entries."""

    scalars: Mapping[str, ParsedResult]
    extra: Mapping[str, ParsedResult]


def _compile(expression: str) -> ParsedResult:
    try:
        return jmespath.compile(expression)
    except JMESPathError as exc:
        msg = f"invalid JMESPath expression {expression!r}: {exc}"
        raise FetchError("parse_error", msg) from None


def _mapping(fields: FieldMap | None, defaults: Mapping[str, str]) -> _Mapping:
    """The expression for each field: the registry's where it sets one, else the default."""
    expressions = dict(defaults)
    extra: dict[str, str] = {}
    if fields is not None:
        for name in SCALAR_FIELDS:
            expression: str | None = getattr(fields, name)
            if expression is not None:
                expressions[name] = expression
        extra = dict(fields.extra or {})
    return _Mapping(
        scalars={name: _compile(expression) for name, expression in expressions.items()},
        extra={key: _compile(expression) for key, expression in extra.items()},
    )


def _search(expression: ParsedResult, data: object) -> object:
    """The expression's value, None where the data has none or has the wrong type for it.

    A wrong type is a fact about one entry (`join` of a number), so that entry's field is empty
    and the other entries are still read. Other JMESPath errors are mistakes in the expression
    and are left to `_entries`.
    """
    try:
        return expression.search(data)
    except JMESPathTypeError:
        return None


def _as_text(value: object) -> str | None:
    """Text as the source wrote it. A number is written out; anything else is not text."""
    if isinstance(value, str):
        return value
    if isinstance(value, int | float) and not isinstance(value, bool):
        return str(value)
    return None


def _entry(data: object, mapping: _Mapping) -> RawEntry:
    values = {name: _search(expression, data) for name, expression in mapping.scalars.items()}
    return RawEntry(
        id=_as_text(values.get("id")),
        title=_as_text(values.get("title")),
        url=_as_text(values.get("url")),
        published=values.get("published"),
        summary=_as_text(values.get("summary")),
        signal=values.get("signal"),
        extra={key: _search(expression, data) for key, expression in mapping.extra.items()},
    )


def _failed(exc: JMESPathError) -> FetchError:
    return FetchError("parse_error", f"a JMESPath expression failed: {exc}")


def _entries(items: list[Any], mapping: _Mapping) -> list[RawEntry]:
    try:
        return [_entry(item, mapping) for item in items]
    except JMESPathError as exc:
        raise _failed(exc) from None


def _keyed(
    items: list[Any],
    mapping: _Mapping,
    key: ParsedResult,
    tracked: Mapping[str, ParsedResult],
) -> list[KeyedEntry]:
    entries = _entries(items, mapping)
    try:
        return [
            KeyedEntry(
                key=_search(key, item),
                entry=entry,
                tracked={name: _search(parsed, item) for name, parsed in tracked.items()},
            )
            for item, entry in zip(items, entries, strict=True)
        ]
    except JMESPathError as exc:
        raise _failed(exc) from None


def parse_feed(content: bytes, fields: FieldMap | None) -> list[RawEntry]:
    """The entries of an RSS or Atom feed.

    Where `fields` sets a JMESPath it is evaluated against the entry as feedparser read it (a
    dict with the keys `title`, `link`, `summary`, `published`, `updated`, `tags`, ...); fields it
    leaves out keep the feed's own values. Raises FetchError("parse_error") when the content is
    not a feed. A feed with no entries is not an error, unless feedparser could not tell what it
    is or had to give up on it.
    """
    mapping = _mapping(fields, FEED_DEFAULTS)
    # A stream: feedparser opens a bytes or str argument as a file name when one exists, and
    # fetches a str that looks like a URL. Fetched content must be neither.
    parsed = feedparser.parse(io.BytesIO(content))
    if not parsed.entries and (parsed.bozo or not parsed.get("version")):
        problem = parsed.get("bozo_exception")
        reason = type(problem).__name__ if problem is not None else "no feed found"
        msg = f"the response is not a readable RSS or Atom feed ({reason})"
        raise FetchError("parse_error", msg)
    return _entries(list(parsed.entries), mapping)


def _select(content: bytes, items: str) -> list[Any]:
    """The JSON items `items` selects. Raises FetchError("parse_error") when it cannot."""
    try:
        document = json.loads(content)
    except (ValueError, RecursionError):  # JSONDecodeError and UnicodeDecodeError are ValueErrors
        raise FetchError("parse_error", "the response is not valid JSON") from None
    select = _compile(items)
    try:
        selected: object = select.search(document)
    except JMESPathError as exc:
        msg = f"JMESPath items expression {items!r} failed: {exc}"
        raise FetchError("parse_error", msg) from None
    if not isinstance(selected, list):
        kind = "nothing" if selected is None else f"a {type(selected).__name__}"
        msg = f"JMESPath items expression {items!r} selected {kind}, not a list"
        raise FetchError("parse_error", msg)
    return cast(list[Any], selected)


def parse_json(content: bytes, items: str, fields: FieldMap) -> list[RawEntry]:
    """The entries `items` selects from a JSON document, mapped with `fields`.

    `items` must select a list. Raises FetchError("parse_error") for content that is not JSON, an
    `items` that selects anything else, and a JMESPath expression that cannot be used.
    """
    selected = _select(content, items)
    return _entries(selected, _mapping(fields, {}))


def parse_json_keyed(
    content: bytes,
    items: str,
    fields: FieldMap,
    key: str,
    track: Sequence[str],
) -> list[KeyedEntry]:
    """Like `parse_json`, with each entry's `key` and `track`ed values read from the same item.

    The entries are the ones `parse_json` gives, in the same order. A `key` or `track` expression
    that has no value for an item, or is the wrong type for it, gives None for that item.
    """
    selected = _select(content, items)
    mapping = _mapping(fields, {})
    return _keyed(selected, mapping, _compile(key), {name: _compile(name) for name in track})


@dataclass(frozen=True)
class SitemapDoc:
    """What one sitemap file lists.

    `urls` holds each page with its `<lastmod>` (None when it has none or cannot be read), in the
    order of the file. `children` holds the sitemaps an index lists. Both hold absolute http(s)
    URLs only.
    """

    urls: dict[str, datetime | None]
    children: list[str]


def _too_large(max_bytes: int) -> FetchError:
    return FetchError("too_large", f"the sitemap is larger than max_response_bytes ({max_bytes})")


def _gunzip(content: bytes, max_bytes: int) -> bytes:
    """The inflated bytes of a gzip file, never more than `max_bytes` of them (a gzip bomb)."""
    inflated = bytearray()
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(content)) as stream:
            # Each read asks for at most one byte past the cap, so the check below needs no more.
            while chunk := stream.read(min(GUNZIP_CHUNK_BYTES, max_bytes + 1 - len(inflated))):
                inflated += chunk
                if len(inflated) > max_bytes:
                    raise _too_large(max_bytes)
    except (OSError, EOFError, zlib.error):  # BadGzipFile is an OSError
        raise FetchError("parse_error", "the sitemap is not a readable gzip file") from None
    return bytes(inflated)


def _local(tag: str) -> str:
    """An element's name without its namespace, which sitemaps write in more than one way."""
    return tag.rsplit("}", 1)[-1]


def _location(text: str | None) -> str | None:
    """The `<loc>` text as an absolute http(s) URL with a host, or None. Nothing else is fetched.

    A URL with a space or a control character in it is not one a sitemap may list (they are
    escaped), and it would reach the logs as written.
    """
    url = (text or "").strip()
    if not url.isprintable() or any(char.isspace() for char in url):
        return None
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:  # a bracket or port that is not valid
        return None
    return url if parts.scheme.lower() in URL_SCHEMES and host else None


def parse_sitemap(content: bytes, max_bytes: int) -> SitemapDoc:
    """The pages and child sitemaps a sitemap or sitemap index lists.

    Gzip is undone when the content starts with the gzip magic (a `.xml.gz` file is gzip whatever
    the server says), and the inflated document may not pass `max_bytes`: FetchError("too_large").
    The XML is untrusted, so it is read with defusedxml, which refuses entity declarations and
    external references. Anything that is not a readable sitemap is FetchError("parse_error"). An
    entry without a usable `<loc>` is left out, and the first entry for a URL is the one kept.
    """
    document = _gunzip(content, max_bytes) if content.startswith(GZIP_MAGIC) else content
    if len(document) > max_bytes:
        raise _too_large(max_bytes)
    try:
        root = fromstring(document)
    except (ParseError, LookupError, ValueError) as exc:
        # defusedxml's EntitiesForbidden, ExternalReferenceForbidden and DTDForbidden are
        # ValueErrors; expat's errors are ParseErrors; an encoding the XML declaration names that
        # Python does not know is a LookupError. The message is the type only: some of these
        # quote what the document declared, which can be as large as the document.
        msg = f"the response is not a readable sitemap ({type(exc).__name__})"
        raise FetchError("parse_error", msg) from None
    kind = _local(root.tag)
    if kind not in SITEMAP_ROOTS:
        msg = f"the response is not a sitemap: its root element is <{kind[:ROOT_NAME_CHARS]}>"
        raise FetchError("parse_error", msg)
    urls: dict[str, datetime | None] = {}
    children: dict[str, None] = {}  # a dict for its order and a fast membership test
    for entry in root:
        name = _local(entry.tag)
        if name not in ("url", "sitemap"):
            continue
        # Only the entry's own children: an image or video extension has its own <loc> inside.
        loc: str | None = None
        lastmod: datetime | None = None
        for field in entry:
            field_name = _local(field.tag)
            if field_name == "loc" and loc is None:
                loc = _location(field.text)
            elif field_name == "lastmod" and lastmod is None:
                lastmod = parse_timestamp((field.text or "").strip())
        if loc is None:
            continue
        if name == "sitemap":
            children[loc] = None
        else:
            urls.setdefault(loc, lastmod)
    return SitemapDoc(urls=urls, children=list(children))
