"""Turn what sources give us into the forms the collected files use: times, URLs, ids, and text."""

from __future__ import annotations

import calendar
import hashlib
import html
import time
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import courlan
import nh3
from slugify import slugify

from pulseai.schemas import load_schema

# The schema that fixes what an item id may look like.
COLLECTED_SCHEMA = "collected.schema.json"
URL_SCHEMES = frozenset({"http", "https"})
ID_SEPARATOR = ":"
ID_HASH_CHARS = 16
ELLIPSIS = "…"

_EPOCH = datetime.fromtimestamp(0, UTC)


def to_utc(at: datetime) -> datetime:
    """The same instant in UTC. A datetime without a time zone is already UTC."""
    if at.utcoffset() is None:
        return at.replace(tzinfo=UTC)
    return at.astimezone(UTC)


def _parse_text(text: str) -> datetime:
    """Read ISO 8601 or RFC 822 text. Raises ValueError for anything else."""
    stripped = text.strip()
    try:
        return datetime.fromisoformat(stripped)
    except ValueError:
        return parsedate_to_datetime(stripped)


def parse_timestamp(value: object) -> datetime | None:
    """A datetime, a feedparser struct_time, Unix epoch seconds, or ISO 8601 or RFC 822 text.

    The result is a UTC datetime. A value without a time zone is UTC and a date alone is that day
    at 00:00. Anything else, including a bool, NaN, or a value out of range (such as epoch
    milliseconds), gives None.
    """
    try:
        if isinstance(value, datetime):
            return to_utc(value)
        if isinstance(value, bool):
            return None
        if isinstance(value, int | float):
            return _EPOCH + timedelta(seconds=value)
        if isinstance(value, time.struct_time):
            # timegm rolls a leap second (:60) over into the next minute.
            return _EPOCH + timedelta(seconds=calendar.timegm(value))
        if isinstance(value, str):
            return to_utc(_parse_text(value))
    except (ValueError, OverflowError):
        return None
    return None


def format_timestamp(at: datetime) -> str:
    """RFC 3339 UTC with an uppercase Z and no fraction, as the collected files write times."""
    return to_utc(at).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_url(url: str) -> str | None:
    """The URL without tracking parameters or other spellings of the same address.

    Other query parameters and the fragment stay: they can tell pages and entries apart (`?v=`,
    `/changelog#v1.2.0`). None when it is not an http(s) URL with a host, or cannot be parsed.
    """
    candidate = url.strip()
    try:
        parts = urlsplit(candidate)
        if parts.scheme.lower() not in URL_SCHEMES or not parts.hostname:
            return None
        _ = parts.port  # a port that is not a number in range raises ValueError
        return courlan.normalize_url(candidate, strict=False)
    except ValueError:
        return None


def item_id(source_id: str, *, mapped_id: str | None, canonical: str) -> str:
    """`<source-id>:<slug>`, from the source's own id when it gives a usable one.

    Otherwise the slug is a hash of the canonical URL. Either way the same item gets the same id on
    every run, and the id fits the collected-file schema.
    """
    max_length: int = load_schema(COLLECTED_SCHEMA)["$defs"]["itemId"]["maxLength"]
    prefix = f"{source_id}{ID_SEPARATOR}"
    slug = slugify(mapped_id) if mapped_id else ""
    if slug and len(prefix) + len(slug) <= max_length:
        return prefix + slug
    return prefix + hashlib.sha256(canonical.encode()).hexdigest()[:ID_HASH_CHARS]


def clean_text(value: str | None, max_chars: int) -> str | None:
    """Plain text from markup: tags and their scripts removed, entities decoded, spaces collapsed.

    Text longer than `max_chars` is cut at a word boundary and ends with an ellipsis. None when
    nothing readable is left. The result is text, not HTML: a renderer must still escape it.
    """
    if value is None:
        return None
    # JSON allows a lone surrogate, which nh3 cannot take. Replace it rather than lose the item.
    encodable = value.encode("utf-8", errors="replace").decode("utf-8")
    # nh3 drops a tag without leaving a gap, so mark each tag with a space or "</p><p>" glues words.
    stripped = nh3.clean(encodable.replace("<", " <"), tags=set())
    text = " ".join(html.unescape(stripped).split())
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    cut = text.rfind(" ", 0, max_chars)
    return (text[:cut] if cut > 0 else text[: max_chars - 1]) + ELLIPSIS
