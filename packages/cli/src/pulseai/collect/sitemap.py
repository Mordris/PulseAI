"""The parts of a sitemap source that read: sitemaps, the URLs they keep, and the pages they name.

`kinds._sitemap` puts them together (design §8.5). Everything here is fetched through the shared
`Fetcher`. A sitemap is untrusted, and so is every URL in it: nothing from it forms a path, and a
source's credentials go only to the origin of its own sitemap, never to a host the sitemap names.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import Message
from fnmatch import fnmatchcase
from typing import Literal
from urllib.parse import urlsplit

import structlog
from structlog.typing import FilteringBoundLogger
from trafilatura import extract_metadata

from pulseai.collect.fetch import Fetcher, FetchError, FetchResult
from pulseai.collect.normalize import format_timestamp, parse_timestamp
from pulseai.collect.parsers import RawEntry, SitemapDoc, parse_sitemap
from pulseai.models.collected import FieldChange, ItemChange
from pulseai.models.sources import HttpOptions

# The field a sitemap source reports a change in: the only value its snapshot tracks.
LASTMOD = "lastmod"
# What a page without a usable charset in its Content-Type is read as.
DEFAULT_CHARSET = "utf-8"
DEFAULT_PORTS = {"http": 80, "https": 443}
# Sorts a candidate without a lastmod after every one that has one.
_OLDEST = datetime.min.replace(tzinfo=UTC)

log: FilteringBoundLogger = structlog.get_logger(__name__)

# trafilatura and htmldate log through the standard library, at error level for a page they cannot
# parse (an empty document) and at warning level for a date they cannot place. Such a page is not
# an error here: it has no title or no date and is counted as such. The run reports through
# structlog, so these records are kept out of its output.
for _library in ("trafilatura", "htmldate"):
    logging.getLogger(_library).setLevel(logging.CRITICAL)


def _origin(url: str) -> tuple[str, str | None, int | None]:
    """The scheme, host and port that decide whether two URLs share credentials."""
    try:
        parts = urlsplit(url)
        scheme = parts.scheme.lower()
        return scheme, parts.hostname, parts.port or DEFAULT_PORTS.get(scheme)
    except ValueError:  # a port out of range
        return "", None, None


def _http_for(http: HttpOptions | None, sitemap: str, url: str) -> HttpOptions | None:
    """The source's http options for a URL its sitemap named.

    Its credentials stay with the sitemap's own origin, as the fetcher does for a redirect. For
    any other origin the options keep their timeout and retries and lose the auth.
    """
    if http is None or http.auth_env is None:
        return http
    asked = _origin(url)
    if asked[1] is not None and asked == _origin(sitemap):
        return http
    return http.model_copy(update={"auth_env": None})


@dataclass(frozen=True)
class SitemapUrls:
    """Every URL the sitemap listed, with how many child sitemaps its index named and read."""

    urls: dict[str, datetime | None]  # the root's URLs first, then each child's, in order
    children: int  # child sitemaps the index listed
    read: int  # of those, the ones read: at most `max_child_sitemaps`

    @property
    def note(self) -> str | None:
        """What to tell the run when the cap left child sitemaps unread."""
        if self.read == self.children:
            return None
        unread = self.children - self.read
        return (
            f"{unread} of {self.children} child sitemaps not read (max_child_sitemaps {self.read})"
        )


def _parse(url: str, content: bytes, max_bytes: int) -> SitemapDoc:
    """The sitemap at `url` as parse_sitemap reads it, with the URL added to a failure."""
    try:
        return parse_sitemap(content, max_bytes)
    except FetchError as exc:
        raise FetchError(exc.reason, f"{url}: {exc.detail}", status=exc.status) from None


async def read_sitemaps(
    fetcher: Fetcher,
    url: str,
    root: FetchResult,
    http: HttpOptions | None,
    *,
    max_children: int,
    max_bytes: int,
) -> SitemapUrls:
    """The URLs of the sitemap at `url` (already fetched as `root`) and of its child sitemaps.

    One level of index is followed: the first `max_children` sitemaps it lists. A child that is
    itself an index gives no URLs, and its children are not read. A child that cannot be fetched
    or read fails the source. Skipping it would drop its URLs from the snapshot, and the next run
    would report every one of them as new.
    """
    document = _parse(url, root.content, max_bytes)
    urls = dict(document.urls)
    followed = document.children[:max_children]
    for child in followed:
        fetched = await fetcher.get(child, _http_for(http, url, child))
        for loc, lastmod in _parse(child, fetched.content, max_bytes).urls.items():
            urls.setdefault(loc, lastmod)
    return SitemapUrls(urls=urls, children=len(document.children), read=len(followed))


def _path(url: str) -> str:
    return urlsplit(url).path or "/"


def matching_urls(
    urls: Mapping[str, datetime | None], include: Sequence[str], exclude: Sequence[str]
) -> dict[str, datetime | None]:
    """The URLs whose path matches an `include` glob and no `exclude` glob.

    Globs are fnmatch patterns matched against the path only (`*` also matches `/`), case
    sensitively. The lastmod of each is cut to whole seconds, which is what a snapshot keeps.
    """
    kept: dict[str, datetime | None] = {}
    for url, lastmod in urls.items():
        path = _path(url)
        if any(fnmatchcase(path, glob) for glob in include) and not any(
            fnmatchcase(path, glob) for glob in exclude
        ):
            kept[url] = None if lastmod is None else lastmod.replace(microsecond=0)
    return kept


@dataclass(frozen=True)
class Candidate:
    """A URL to read: one that is new, or whose lastmod moved forward."""

    url: str
    kind: Literal["added", "updated"]
    before: datetime | None  # the lastmod in the earlier snapshot
    after: datetime | None  # the lastmod now

    @property
    def change(self) -> ItemChange:
        old = None if self.before is None else format_timestamp(self.before)
        new = None if self.after is None else format_timestamp(self.after)
        fields = (
            [] if old is None and new is None else [FieldChange(path=LASTMOD, old=old, new=new)]
        )
        return ItemChange(kind=self.kind, fields=fields)


def candidates(
    current: Mapping[str, datetime | None], previous: Mapping[str, str | None]
) -> list[Candidate]:
    """What to read: URLs missing from `previous`, and URLs whose lastmod is later than before.

    A lastmod that is missing from either snapshot cannot be said to have moved forward, so a
    URL that gained one (or lost one) is not a candidate. The result is newest first by lastmod,
    then by URL, with the URLs that have no lastmod last.
    """
    found: list[Candidate] = []
    for url, after in current.items():
        if url not in previous:
            found.append(Candidate(url, "added", None, after))
            continue
        before = parse_timestamp(previous[url])
        if before is not None and after is not None and after > before:
            found.append(Candidate(url, "updated", before, after))
    found.sort(key=lambda candidate: candidate.url)
    # A stable sort, so URLs with the same lastmod stay in URL order.
    found.sort(key=lambda candidate: candidate.after or _OLDEST, reverse=True)
    return found


def _charset(headers: Mapping[str, str]) -> str:
    """The charset a response names in its Content-Type, or the default."""
    for name, value in headers.items():
        if name.lower() == "content-type":
            message = Message()
            message["Content-Type"] = value
            return message.get_content_charset() or DEFAULT_CHARSET
    return DEFAULT_CHARSET


def _decode(fetched: FetchResult) -> str:
    """The page as text. Bytes the charset cannot read become U+FFFD instead of failing the page."""
    try:
        return fetched.content.decode(_charset(fetched.headers), errors="replace")
    except LookupError:  # a charset Python does not know, or one that is not a text encoding
        return fetched.content.decode(DEFAULT_CHARSET, errors="replace")


async def read_page(
    fetcher: Fetcher, url: str, sitemap: str, http: HttpOptions | None
) -> RawEntry | None:
    """The title, date and description of the page at `url`, or None when it cannot be fetched.

    trafilatura reads the metadata (OpenGraph, `article:published_time`, JSON-LD, `<title>`) and
    htmldate the date. The entry is not checked: a page without a title is left to `build_items`.
    """
    try:
        fetched = await fetcher.get(url, _http_for(http, sitemap, url))
    except FetchError as exc:
        log.info("page_skipped", url=url, reason=exc.reason)
        return None
    metadata = extract_metadata(_decode(fetched), default_url=url)
    return RawEntry(
        id=None,
        title=metadata.title,
        url=url,
        published=metadata.date,
        summary=metadata.description,
        signal=None,
        extra={},
    )
