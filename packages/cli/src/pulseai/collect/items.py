"""Turn raw entries into collected items: normalized, checked, and filtered by the window."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError

from pulseai.collect.normalize import (
    canonical_url,
    clean_text,
    format_timestamp,
    item_id,
    parse_timestamp,
)
from pulseai.collect.parsers import RawEntry
from pulseai.collect.window import Window
from pulseai.models.collected import (
    CollectedItem,
    DatedItem,
    Extra,
    ItemChange,
    UndatedItem,
)
from pulseai.models.config import CollectConfig

# The stored canonical URL must be https (design §13); the item's own url may be http.
HTTPS_PREFIX = "https://"


@dataclass(frozen=True)
class BuildResult:
    items: list[CollectedItem]
    dropped_window: int  # outside the window, or undated where undated items are not kept
    dropped_invalid: int  # no usable title or https URL, or not a valid item


def _encodable(text: str) -> str:
    """The text with each lone surrogate (which JSON allows) replaced, so it can be written."""
    return text.encode("utf-8", errors="replace").decode("utf-8")


def _number(value: object) -> float | None:
    """A finite number: a number, or ASCII text that reads as one. A bool is not a number."""
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    if isinstance(value, str) and not value.isascii():  # float() also reads other scripts' digits
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):  # text that is not a number; an int beyond float
        return None
    return number if math.isfinite(number) else None


def _extra(values: Mapping[str, object]) -> Extra:
    """The scalar values, which is all the collected file holds. Anything else is left out."""
    kept: Extra = {}
    for key, value in values.items():
        if value is None or isinstance(value, bool):
            kept[key] = value
        elif isinstance(value, str):
            kept[key] = _encodable(value)
        elif isinstance(value, int | float):
            number = _number(value)
            if number is not None:
                kept[key] = number
    return kept


def _item(
    entry: RawEntry,
    *,
    source_id: str,
    settings: CollectConfig,
    published: datetime | None,
    detected_at: str | None,
    change: Callable[[RawEntry], ItemChange | None] | None,
) -> CollectedItem | None:
    """The item for an entry, or None when it has no usable title or https URL."""
    title = clean_text(entry.title, settings.title_max_chars)
    url = None if entry.url is None else _encodable(entry.url).strip()
    canonical = canonical_url(url) if url else None
    if title is None or url is None or canonical is None or not canonical.startswith(HTTPS_PREFIX):
        return None
    fields: dict[str, object] = {
        "id": item_id(source_id, mapped_id=entry.id, canonical=canonical),
        "source_id": source_id,
        "title": title,
        "url": url,
        "canonical_url": canonical,
        "summary": clean_text(entry.summary, settings.summary_max_chars),
        "signal": _number(entry.signal),
        "extra": _extra(entry.extra),
    }
    # Left out unless there is a value: the schema does not allow null for either, and the repo
    # dumps models with exclude_unset, so an explicit None would be written as null.
    if detected_at is not None:
        fields["detected_at"] = detected_at
    changed = None if change is None else change(entry)
    if changed is not None:
        fields["change"] = changed
    try:
        if published is None:
            return UndatedItem.model_validate(fields | {"published": None, "undated": True})
        return DatedItem.model_validate(
            fields | {"published": format_timestamp(published), "undated": False}
        )
    except ValidationError:  # e.g. a url with a space in it
        return None


def _outside(window: Window | None, published: datetime | None, *, changelog: bool) -> bool:
    """Whether the window drops an entry: it is dated outside it, or undated and not a changelog."""
    if window is None:
        return False
    if published is None:
        return not changelog
    return not window.contains(published)


def build_items(
    entries: Iterable[RawEntry],
    *,
    source_id: str,
    window: Window | None,
    changelog: bool,
    settings: CollectConfig,
    detected_at: datetime | None = None,
    change: Callable[[RawEntry], ItemChange | None] | None = None,
) -> BuildResult:
    """Validated items for the entries that are usable, in the order given.

    - An entry without a usable title or https URL is dropped and counted as invalid.
    - With a `window`, a dated entry outside `[since, until)` is dropped, and so is an undated
      one (no date, or one that cannot be read) unless `changelog` is set; an undated entry that
      is kept has `undated` true and no `published`. Both count as dropped by the window.
    - Without a `window` (snapshot and sitemap sources) no entry is dropped for its date.
    - Of items with the same id the first stays. A repeat is dropped without being counted.

    `detected_at` and `change(entry)` fill the fields of the same names, for sources that report
    changes. The text of each item is plain text: titles and summaries have their markup removed
    and are cut to the lengths in `settings`.
    """
    items: list[CollectedItem] = []
    seen: set[str] = set()
    dropped_window = 0
    dropped_invalid = 0
    detected = None if detected_at is None else format_timestamp(detected_at)
    for entry in entries:
        published = parse_timestamp(entry.published)
        item = _item(
            entry,
            source_id=source_id,
            settings=settings,
            published=published,
            detected_at=detected,
            change=change,
        )
        if item is None:
            dropped_invalid += 1
            continue
        if _outside(window, published, changelog=changelog):
            dropped_window += 1
            continue
        if item.id not in seen:
            seen.add(item.id)
            items.append(item)
    return BuildResult(items=items, dropped_window=dropped_window, dropped_invalid=dropped_invalid)
