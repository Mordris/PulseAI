"""Dated snapshots of a source's entries, and the diff between two of them (design §8.4).

A snapshot is `{"entries": {key: {"fields": {...}, "tracked": {expression: value}}}}`: for each
entry the registry's `key` picks, the fields it was mapped to and the values the source's `track`
expressions gave. One file holds a run date's snapshot, at
`<instance>/state/snapshots/<source-id>/<YYYY-MM-DD>.json`. The directory is a registry id and the
file name is the run date, so nothing fetched ever forms part of a path.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Any, cast

import structlog
from pydantic import TypeAdapter, ValidationError
from structlog.typing import FilteringBoundLogger

from pulseai.collect.parsers import KeyedEntry, RawEntry
from pulseai.models.collected import FieldChange, ItemChange
from pulseai.models.sources import Id

SNAPSHOT_DIR = Path("state") / "snapshots"
SNAPSHOT_SUFFIX = ".json"
# A snapshot's file name is exactly `<ISO date>.json`; date.fromisoformat alone also reads
# other spellings (20261029, 2026-W44-4).
_DATED_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})" + re.escape(SNAPSHOT_SUFFIX))
_TEMP_PREFIX = "."
_TEMP_SUFFIX = ".tmp"
# The mapped fields a snapshot stores for each entry; these are the attributes of RawEntry.
_FIELDS = ("id", "title", "url", "published", "summary", "signal", "extra")

_SOURCE_ID = TypeAdapter(Id)

log: FilteringBoundLogger = structlog.get_logger(__name__)


def _is_record(record: object) -> bool:
    """Whether the JSON is one entry of a snapshot: all its fields, and its tracked values."""
    if not isinstance(record, dict):
        return False
    parts = cast(dict[str, Any], record)
    fields, tracked = parts.get("fields"), parts.get("tracked")
    return (
        isinstance(fields, dict)
        and set(_FIELDS) <= cast(dict[str, Any], fields).keys()
        and isinstance(tracked, dict)
    )


def _is_snapshot(document: object) -> bool:
    """Whether the JSON has the shape `snapshot_document` writes."""
    if not isinstance(document, dict):
        return False
    entries = cast(dict[str, Any], document).get("entries")
    return isinstance(entries, dict) and all(
        _is_record(record) for record in cast(dict[str, Any], entries).values()
    )


class SnapshotStore:
    """The dated snapshots of every source, kept under an instance directory.

    `keep` is how many snapshots of a source stay after a write; the oldest are removed.
    """

    def __init__(self, instance_dir: Path, keep: int) -> None:
        self._root = instance_dir / SNAPSHOT_DIR
        self._keep = keep

    def _directory(self, source_id: str) -> Path:
        """The source's directory. Only a registry id can name one."""
        try:
            _SOURCE_ID.validate_python(source_id)
        except ValidationError:
            msg = f"invalid source id {source_id!r}: not a registry id"
            raise ValueError(msg) from None
        return self._root / source_id

    @staticmethod
    def _dated(directory: Path) -> list[tuple[date, Path]]:
        """The snapshot files in the directory, oldest first. Anything else in it is ignored."""
        if not directory.is_dir():
            return []
        found: list[tuple[date, Path]] = []
        for path in directory.iterdir():
            named = _DATED_NAME.fullmatch(path.name)
            if named is None or not path.is_file():
                continue
            try:
                found.append((date.fromisoformat(named[1]), path))
            except ValueError:  # 2026-13-40
                continue
        return sorted(found)

    def previous(self, source_id: str, run_date: date) -> dict[str, Any] | None:
        """The latest snapshot dated strictly before `run_date`, or None when there is none.

        A snapshot that cannot be read (not JSON, or not a snapshot) is logged and skipped, so
        the run compares with the next older one instead of failing on a damaged file.
        """
        for day, path in reversed(self._dated(self._directory(source_id))):
            if day >= run_date:
                continue
            try:
                document: object = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:  # JSONDecodeError and UnicodeDecodeError
                reason = type(exc).__name__
            else:
                if _is_snapshot(document):
                    return cast(dict[str, Any], document)
                reason = "not a snapshot"
            log.warning("snapshot_unreadable", source=source_id, file=path.name, reason=reason)
        return None

    def write(self, source_id: str, run_date: date, data: Mapping[str, Any]) -> None:
        """Write the snapshot for `run_date`, replacing that date's file, then prune.

        The file appears whole or not at all: it is written to a temporary file in the same
        directory and renamed over the target. When any step fails the old file stays as it was
        and nothing is pruned. Afterwards only the `keep` newest snapshots stay.
        """
        directory = self._directory(source_id)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{run_date.isoformat()}{SNAPSHOT_SUFFIX}"
        handle, temporary = tempfile.mkstemp(
            dir=directory, prefix=_TEMP_PREFIX, suffix=_TEMP_SUFFIX
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                json.dump(dict(data), out, indent=2, sort_keys=True)
                out.write("\n")
                out.flush()
                os.fsync(out.fileno())  # the data is on disk before the name points at it
            Path(temporary).replace(target)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        for _, old in self._dated(directory)[: -self._keep]:
            old.unlink(missing_ok=True)


def snapshot_document(rows: Iterable[KeyedEntry]) -> tuple[dict[str, Any], int]:
    """The snapshot of a response's entries, and how many had no key to be compared by.

    A key must be text: an entry whose key is missing, null, a number or anything else is left
    out and counted. Of entries with the same key the first stays.
    """
    entries: dict[str, Any] = {}
    unkeyed = 0
    for row in rows:
        if not isinstance(row.key, str):
            unkeyed += 1
        elif row.key not in entries:
            entries[row.key] = {
                "fields": {name: getattr(row.entry, name) for name in _FIELDS},
                "tracked": dict(row.tracked),
            }
    return {"entries": entries}, unkeyed


def stored_entry(record: Mapping[str, Any]) -> RawEntry:
    """The entry a snapshot record was made from."""
    return RawEntry(**{name: record["fields"][name] for name in _FIELDS})


def diff_snapshot(old: Mapping[str, Any], new: Mapping[str, Any]) -> list[tuple[str, ItemChange]]:
    """What changed from `old` to `new`, as (key, change) pairs.

    - An entry only in `new` is added, and one only in `old` is removed. Each lists the tracked
      values it has that are not null, as a change from or to null.
    - An entry in both is changed when a tracked value differs, and lists those values. Only
      expressions both snapshots track are compared, so adding one to a source's `track` does not
      report every entry as changed.
    - Entries that are the same in the tracked values give nothing.

    Added and changed entries come first, in the order of `new`; removed ones follow, by key.
    """
    old_entries: Mapping[str, Mapping[str, Any]] = old["entries"]
    new_entries: Mapping[str, Mapping[str, Any]] = new["entries"]
    changes: list[tuple[str, ItemChange]] = []
    for key, record in new_entries.items():
        tracked: Mapping[str, Any] = record["tracked"]
        if key not in old_entries:
            fields = [
                FieldChange(path=path, old=None, new=value)
                for path, value in tracked.items()
                if value is not None
            ]
            changes.append((key, ItemChange(kind="added", fields=fields)))
            continue
        before: Mapping[str, Any] = old_entries[key]["tracked"]
        fields = [
            FieldChange(path=path, old=before[path], new=value)
            for path, value in tracked.items()
            if path in before and before[path] != value
        ]
        if fields:
            changes.append((key, ItemChange(kind="changed", fields=fields)))
    for key in sorted(old_entries.keys() - new_entries.keys()):
        fields = [
            FieldChange(path=path, old=value, new=None)
            for path, value in old_entries[key]["tracked"].items()
            if value is not None
        ]
        changes.append((key, ItemChange(kind="removed", fields=fields)))
    return changes
