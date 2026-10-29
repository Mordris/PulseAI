import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from structlog.testing import capture_logs

from pulseai.collect.parsers import KeyedEntry, RawEntry
from pulseai.collect.snapshots import SnapshotStore, diff_snapshot, snapshot_document, stored_entry
from pulseai.models.collected import FieldChange, ItemChange

SOURCE = "openrouter-models"
DAY = date(2026, 10, 29)


def day(number: int) -> date:
    return date(2026, 10, number)


def record(title: str, tracked: dict[str, Any] | None = None) -> dict[str, Any]:
    """One entry of a snapshot, as `snapshot_document` writes it."""
    fields = {
        "id": None,
        "title": title,
        "url": f"https://example.com/{title.lower()}",
        "published": None,
        "summary": None,
        "signal": None,
        "extra": {},
    }
    return {"fields": fields, "tracked": tracked or {}}


def document(**records: dict[str, Any]) -> dict[str, Any]:
    return {"entries": records}


def snapshot_dir(root: Path, source_id: str = SOURCE) -> Path:
    return root / "state" / "snapshots" / source_id


def files(root: Path, source_id: str = SOURCE) -> list[str]:
    return sorted(path.name for path in snapshot_dir(root, source_id).iterdir())


# --- the store ---------------------------------------------------------------------------------


def test_write_puts_the_snapshot_under_the_source_id_and_the_run_date(tmp_path: Path) -> None:
    data = document(a=record("A", {"pricing.prompt": "0.1"}))

    SnapshotStore(tmp_path, keep=3).write(SOURCE, DAY, data)

    written = snapshot_dir(tmp_path) / "2026-10-29.json"
    assert json.loads(written.read_text(encoding="utf-8")) == data
    assert files(tmp_path) == ["2026-10-29.json"]


def test_previous_is_latest_strictly_before_run_date(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path, keep=14)
    for number in (27, 28, 29):
        store.write(SOURCE, day(number), document(a=record(f"Day {number}")))

    assert store.previous(SOURCE, day(29)) == document(a=record("Day 28"))
    assert store.previous(SOURCE, day(30)) == document(a=record("Day 29"))
    assert store.previous(SOURCE, day(28)) == document(a=record("Day 27"))
    assert store.previous(SOURCE, day(27)) is None


def test_previous_is_none_for_a_source_without_snapshots(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path, keep=14)
    store.write("other-source", day(20), document(a=record("A")))

    assert store.previous(SOURCE, DAY) is None


def test_previous_ignores_files_that_are_not_dated_snapshots(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path, keep=14)
    store.write(SOURCE, day(26), document(a=record("Day 26")))
    directory = snapshot_dir(tmp_path)
    for name in ("latest.json", "20261028.json", "2026-13-40.json", "2026-10-28.json.tmp", "x"):
        (directory / name).write_text(json.dumps(document(a=record("Junk"))), encoding="utf-8")
    (directory / "2026-10-27.json").mkdir()

    assert store.previous(SOURCE, DAY) == document(a=record("Day 26"))


def test_previous_skips_a_snapshot_that_cannot_be_read(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path, keep=14)
    store.write(SOURCE, day(26), document(a=record("Day 26")))
    directory = snapshot_dir(tmp_path)
    (directory / "2026-10-27.json").write_text('{"entries": ', encoding="utf-8")
    (directory / "2026-10-28.json").write_text(json.dumps([1, 2]), encoding="utf-8")

    with capture_logs() as logs:
        found = store.previous(SOURCE, DAY)

    assert found == document(a=record("Day 26"))
    assert [(entry["event"], entry["log_level"], entry["file"]) for entry in logs] == [
        ("snapshot_unreadable", "warning", "2026-10-28.json"),
        ("snapshot_unreadable", "warning", "2026-10-27.json"),
    ]


def test_previous_is_none_when_no_snapshot_can_be_read(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path, keep=14)
    directory = snapshot_dir(tmp_path)
    directory.mkdir(parents=True)
    (directory / "2026-10-28.json").write_bytes(b"\xff\xfe")

    with capture_logs():
        assert store.previous(SOURCE, DAY) is None


def test_write_replaces_the_snapshot_of_the_same_date(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path, keep=3)
    store.write(SOURCE, DAY, document(a=record("First")))

    store.write(SOURCE, DAY, document(a=record("Second")))

    assert files(tmp_path) == ["2026-10-29.json"]
    assert store.previous(SOURCE, day(30)) == document(a=record("Second"))


def test_write_prunes_to_keep(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path, keep=2)
    (snapshot_dir(tmp_path)).mkdir(parents=True)
    (snapshot_dir(tmp_path) / "notes.txt").write_text("not a snapshot", encoding="utf-8")

    for number in (26, 27, 28, 29):
        store.write(SOURCE, day(number), document(a=record(f"Day {number}")))

    # The oldest are gone; a file that is not a dated snapshot is left alone.
    assert files(tmp_path) == ["2026-10-28.json", "2026-10-29.json", "notes.txt"]


def test_write_keeps_other_sources_snapshots(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path, keep=2)
    for number in (26, 27, 28):
        store.write("other-source", day(number), document(a=record("Other")))

    for number in (27, 28, 29):
        store.write(SOURCE, day(number), document(a=record("Mine")))

    assert files(tmp_path, "other-source") == ["2026-10-27.json", "2026-10-28.json"]
    assert files(tmp_path) == ["2026-10-28.json", "2026-10-29.json"]


def test_write_is_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    roomy = SnapshotStore(tmp_path, keep=14)
    for number in (27, 28):
        roomy.write(SOURCE, day(number), document(a=record(f"Day {number}")))
    roomy.write(SOURCE, DAY, document(a=record("Old")))
    store = SnapshotStore(tmp_path, keep=2)

    def fail(_source: object, _target: object) -> None:
        raise OSError("disk full")

    # The rename is os.replace (Path.replace calls it too); failing it is a crash at the last step.
    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError, match="disk full"):
        store.write(SOURCE, DAY, document(a=record("New")))
    monkeypatch.undo()

    # The old file is intact, no half-written or temporary file is left, and nothing was pruned.
    assert files(tmp_path) == ["2026-10-27.json", "2026-10-28.json", "2026-10-29.json"]
    assert store.previous(SOURCE, day(30)) == document(a=record("Old"))


def test_a_failed_write_of_a_new_date_leaves_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SnapshotStore(tmp_path, keep=2)

    def fail(_source: object, _target: object) -> None:
        raise OSError("read-only file system")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError, match="read-only"):
        store.write(SOURCE, DAY, document(a=record("New")))
    monkeypatch.undo()

    assert files(tmp_path) == []
    assert store.previous(SOURCE, day(30)) is None


@pytest.mark.parametrize("source_id", ["../escape", "a/b", "", ".", "..", "Upper", "x.json"])
def test_only_registry_ids_name_a_directory(tmp_path: Path, source_id: str) -> None:
    store = SnapshotStore(tmp_path / "instance", keep=2)

    with pytest.raises(ValueError, match="source id"):
        store.write(source_id, DAY, document(a=record("A")))
    with pytest.raises(ValueError, match="source id"):
        store.previous(source_id, DAY)

    assert list(tmp_path.iterdir()) == []


# --- the document ------------------------------------------------------------------------------


def row(key: object, title: str, tracked: dict[str, object] | None = None) -> KeyedEntry:
    entry = RawEntry(
        id=None,
        title=title,
        url=f"https://example.com/{title.lower()}",
        published=1_700_000_000,
        summary="About it.",
        signal=3,
        extra={"tag": "t"},
    )
    return KeyedEntry(key=key, entry=entry, tracked=tracked or {})


def test_snapshot_document_holds_the_fields_and_tracked_values_by_key() -> None:
    rows = [row("a/x", "X", {"pricing.prompt": "0.1"}), row("b/y", "Y")]

    built, unkeyed = snapshot_document(rows)

    assert unkeyed == 0
    assert list(built["entries"]) == ["a/x", "b/y"]
    assert built["entries"]["a/x"] == {
        "fields": {
            "id": None,
            "title": "X",
            "url": "https://example.com/x",
            "published": 1_700_000_000,
            "summary": "About it.",
            "signal": 3,
            "extra": {"tag": "t"},
        },
        "tracked": {"pricing.prompt": "0.1"},
    }
    assert built["entries"]["b/y"]["tracked"] == {}
    assert json.loads(json.dumps(built)) == built


def test_snapshot_document_counts_entries_without_a_string_key() -> None:
    rows = [row("a", "A"), row(None, "None"), row(7, "Seven"), row(True, "Bool"), row("b", "B")]

    built, unkeyed = snapshot_document(rows)

    assert list(built["entries"]) == ["a", "b"]
    assert unkeyed == 3


def test_snapshot_document_keeps_the_first_entry_of_a_repeated_key() -> None:
    built, unkeyed = snapshot_document([row("a", "First"), row("a", "Second")])

    assert [value["fields"]["title"] for value in built["entries"].values()] == ["First"]
    assert unkeyed == 0


def test_a_stored_entry_is_the_entry_it_was_stored_from() -> None:
    original = row("a", "A", {"x": 1})

    built, _ = snapshot_document([original])
    restored = stored_entry(json.loads(json.dumps(built))["entries"]["a"])

    assert restored == original.entry


# --- the diff ----------------------------------------------------------------------------------


def test_diff_added_removed_changed() -> None:
    old = document(
        kept=record("Kept", {"pricing.prompt": "0.1", "context_length": 8000}),
        gone=record("Gone", {"pricing.prompt": "0.2", "context_length": 4000}),
        same=record("Same", {"pricing.prompt": "0.5", "context_length": 1000}),
    )
    new = document(
        kept=record("Kept", {"pricing.prompt": "0.3", "context_length": 8000}),
        same=record("Same", {"pricing.prompt": "0.5", "context_length": 1000}),
        fresh=record("Fresh", {"pricing.prompt": "0.4", "context_length": 2000}),
    )

    assert diff_snapshot(old, new) == [
        (
            "kept",
            ItemChange(
                kind="changed",
                fields=[FieldChange(path="pricing.prompt", old="0.1", new="0.3")],
            ),
        ),
        (
            "fresh",
            ItemChange(
                kind="added",
                fields=[
                    FieldChange(path="pricing.prompt", old=None, new="0.4"),
                    FieldChange(path="context_length", old=None, new=2000),
                ],
            ),
        ),
        (
            "gone",
            ItemChange(
                kind="removed",
                fields=[
                    FieldChange(path="pricing.prompt", old="0.2", new=None),
                    FieldChange(path="context_length", old=4000, new=None),
                ],
            ),
        ),
    ]


def test_a_change_lists_every_tracked_path_that_changed() -> None:
    old = document(a=record("A", {"pricing": {"prompt": "1", "image": "2"}, "context_length": 1}))
    new = document(a=record("A", {"pricing": {"prompt": "1", "image": "3"}, "context_length": 2}))

    [(key, change)] = diff_snapshot(old, new)

    assert (key, change.kind) == ("a", "changed")
    assert change.fields == [
        FieldChange(
            path="pricing", old={"prompt": "1", "image": "2"}, new={"prompt": "1", "image": "3"}
        ),
        FieldChange(path="context_length", old=1, new=2),
    ]


def test_unchanged_tracked_values_emit_nothing() -> None:
    tracked = {"pricing": {"prompt": "0.1", "completion": "0.2"}, "context_length": 8000}
    old = document(a=record("A", tracked), b=record("B", None))
    # A different title is not a change: only the tracked values are compared.
    new = document(a=record("Renamed", {**tracked}), b=record("B", None))

    assert diff_snapshot(old, new) == []


def test_a_tracked_value_that_goes_missing_or_appears_is_a_change() -> None:
    old = document(a=record("A", {"x": 1}), b=record("B", {"x": None}))
    new = document(a=record("A", {"x": None}), b=record("B", {"x": 2}))

    assert diff_snapshot(old, new) == [
        ("a", ItemChange(kind="changed", fields=[FieldChange(path="x", old=1, new=None)])),
        ("b", ItemChange(kind="changed", fields=[FieldChange(path="x", old=None, new=2)])),
    ]


def test_an_expression_only_one_snapshot_tracks_is_not_a_change() -> None:
    """Adding to a source's `track` must not report every entry as changed."""
    old = document(a=record("A", {"pricing": "p"}), b=record("B", {"pricing": "p", "limit": 1}))
    new = document(a=record("A", {"pricing": "p", "limit": 5}), b=record("B", {"pricing": "p"}))

    assert diff_snapshot(old, new) == []


def test_added_and_removed_entries_list_only_the_tracked_values_they_have() -> None:
    old = document(gone=record("Gone", {"x": None}))
    new = document(fresh=record("Fresh", {"x": None, "y": 1}))

    assert diff_snapshot(old, new) == [
        ("fresh", ItemChange(kind="added", fields=[FieldChange(path="y", old=None, new=1)])),
        ("gone", ItemChange(kind="removed", fields=[])),
    ]


def test_diff_of_two_empty_snapshots_is_empty() -> None:
    assert diff_snapshot(document(), document()) == []


def test_removed_entries_come_after_the_others_in_key_order() -> None:
    old = document(c=record("C"), a=record("A"), b=record("B"))
    new = document(d=record("D"), b=record("B"))

    assert [(key, change.kind) for key, change in diff_snapshot(old, new)] == [
        ("d", "added"),
        ("a", "removed"),
        ("c", "removed"),
    ]
