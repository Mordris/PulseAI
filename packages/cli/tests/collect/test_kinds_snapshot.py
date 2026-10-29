import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
import vcr
from test_kinds_feed_json import ITEM, NOW, RECORDED_WINDOW, collect, serving

from pulseai.collect.fetch import FetchError
from pulseai.collect.kinds import KindResult
from pulseai.collect.normalize import format_timestamp, parse_timestamp
from pulseai.collect.snapshots import SnapshotStore
from pulseai.config import load_config
from pulseai.models.collected import CollectedItem, FieldChange

pytestmark = pytest.mark.anyio

CASSETTE_DIR = Path(__file__).parent / "cassettes"
SOURCE = "test-source"  # the id test_kinds_feed_json.source() gives its source

DAY_1 = date(2026, 10, 28)
DAY_2 = date(2026, 10, 29)
DAY_3 = date(2026, 10, 30)

# The same collector as the default registry's OpenRouter entry, written out so that registry
# changes cannot break these tests.
OPENROUTER: dict[str, Any] = {
    "kind": "json-snapshot-diff",
    "url": "https://openrouter.ai/api/v1/models",
    "items": "data[*]",
    "key": "id",
    "track": ["pricing", "context_length"],
    "fields": {
        "id": "id",
        "title": "name",
        "url": "join('', ['https://openrouter.ai/', id])",
        "published": "created",
        "summary": "description",
    },
}

URL = "https://api.example.com/v1/models"
COLLECTOR: dict[str, Any] = {
    "kind": "json-snapshot-diff",
    "url": URL,
    "items": "data[*]",
    "key": "id",
    "track": ["pricing.prompt", "context_length"],
    "fields": {
        "id": "id",
        "title": "name",
        "url": "join('', ['https://example.com/models/', id])",
        "published": "created",
        "summary": "description",
    },
}
LONG_AGO = 1_600_000_000  # 2020-09-13T12:26:40Z, years before the window


@pytest.fixture
def store(tmp_path: Path) -> SnapshotStore:
    return SnapshotStore(tmp_path, keep=load_config().collect.snapshot_keep)


@pytest.fixture
def cassette(vcr_config: dict[str, Any]) -> Callable[[str], AbstractContextManager[Any]]:
    """Replay one cassette for the length of a `with`, so a test can run several days."""

    def replay(name: str) -> AbstractContextManager[Any]:
        return vcr.use_cassette(str(CASSETTE_DIR / name), **vcr_config)

    return replay


def snapshot_files(store_root: Path) -> list[str]:
    directory = store_root / "state" / "snapshots" / SOURCE
    return sorted(path.name for path in directory.iterdir()) if directory.exists() else []


def model(
    slug: str,
    *,
    prompt: str = "0.001",
    context: int = 8000,
    created: int | None = LONG_AGO,
) -> dict[str, Any]:
    return {
        "id": slug,
        "name": f"Model {slug}",
        "created": created,
        "description": f"About {slug}.",
        "pricing": {"prompt": prompt},
        "context_length": context,
    }


async def run_day(
    store: SnapshotStore,
    run_date: date,
    *models: dict[str, Any],
    collector: dict[str, Any] = COLLECTOR,
) -> KindResult:
    transport = serving(URL, {"data": list(models)})
    return await collect(collector, transport, robots=False, run_date=run_date, snapshots=store)


def dumped(result: KindResult) -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in result.items]


def validated(items: list[CollectedItem]) -> None:
    for item in items:
        assert ITEM.validate_python(item.model_dump(mode="json")) == item
        assert item.source_id == SOURCE
        assert item.canonical_url.startswith("https://")
        assert item.detected_at == format_timestamp(NOW)
        assert item.change is not None


# --- the first run -----------------------------------------------------------------------------


async def test_first_run_writes_baseline_and_emits_nothing(
    tmp_path: Path, store: SnapshotStore
) -> None:
    result = await run_day(store, DAY_1, model("a"), model("b", prompt="0.002"))

    assert result.items == []
    assert result.note == "baseline created"
    assert (result.dropped_window, result.dropped_invalid, result.unread) == (0, 0, 0)
    assert (result.url, result.http_status, result.from_cache) == (URL, 200, False)
    assert snapshot_files(tmp_path) == ["2026-10-28.json"]
    written = json.loads(
        (tmp_path / "state/snapshots/test-source/2026-10-28.json").read_text(encoding="utf-8")
    )
    assert list(written["entries"]) == ["a", "b"]
    assert written["entries"]["b"]["tracked"] == {"pricing.prompt": "0.002", "context_length": 8000}
    assert written["entries"]["b"]["fields"]["title"] == "Model b"


async def test_a_source_that_returns_no_entries_gets_an_empty_baseline(
    tmp_path: Path, store: SnapshotStore
) -> None:
    result = await run_day(store, DAY_1)

    assert (result.items, result.note) == ([], "baseline created")
    assert snapshot_files(tmp_path) == ["2026-10-28.json"]


# --- later runs --------------------------------------------------------------------------------


async def test_next_day_reports_added_removed_and_changed_entries(store: SnapshotStore) -> None:
    await run_day(store, DAY_1, model("a", prompt="0.1"), model("b"), model("c"))

    result = await run_day(store, DAY_2, model("a", prompt="0.2"), model("b"), model("d"))

    assert result.note is None
    assert (result.dropped_window, result.dropped_invalid) == (0, 0)
    assert [(item.title, item.change.kind) for item in result.items if item.change] == [
        ("Model a", "changed"),
        ("Model d", "added"),
        ("Model c", "removed"),
    ]
    changed, added, removed = result.items
    assert changed.change is not None
    assert changed.change.fields == [FieldChange(path="pricing.prompt", old="0.1", new="0.2")]
    # A removed entry keeps the title, link, and date it last had.
    assert (removed.title, removed.url) == ("Model c", "https://example.com/models/c")
    assert added.url == "https://example.com/models/d"
    for item in result.items:
        assert (item.undated, item.published) == (False, "2020-09-13T12:26:40Z")
    validated(result.items)
    assert len({item.id for item in result.items}) == 3


async def test_change_items_ignore_the_window(store: SnapshotStore) -> None:
    await run_day(store, DAY_1, model("a"))

    result = await run_day(store, DAY_2, model("a"), model("b"))

    [item] = result.items
    published = parse_timestamp(item.published)
    assert published is not None
    assert not RECORDED_WINDOW.contains(published)  # created years before the window
    assert item.change is not None
    assert item.change.kind == "added"
    assert result.dropped_window == 0


async def test_an_entry_without_a_date_is_reported_undated(store: SnapshotStore) -> None:
    await run_day(store, DAY_1, model("a"))

    result = await run_day(store, DAY_2, model("a"), model("b", created=None))

    [item] = result.items
    assert (item.undated, item.published) == (True, None)
    validated(result.items)


async def test_unchanged_entries_emit_nothing(store: SnapshotStore) -> None:
    await run_day(store, DAY_1, model("a"), model("b"))

    result = await run_day(store, DAY_2, model("b"), model("a"))

    assert (result.items, result.note) == ([], None)


async def test_same_date_rerun_gives_same_diff(tmp_path: Path, store: SnapshotStore) -> None:
    await run_day(store, DAY_1, model("a", prompt="0.1"), model("b"))
    today = (model("a", prompt="0.2"), model("c"))
    snapshot = tmp_path / "state/snapshots/test-source/2026-10-29.json"

    first = await run_day(store, DAY_2, *today)
    first_file = snapshot.read_bytes()
    second = await run_day(store, DAY_2, *today)

    assert len(first.items) == 3
    assert dumped(second) == dumped(first)
    assert snapshot.read_bytes() == first_file
    assert snapshot_files(tmp_path) == ["2026-10-28.json", "2026-10-29.json"]


async def test_a_run_compares_with_the_latest_snapshot_before_its_date(
    store: SnapshotStore,
) -> None:
    await run_day(store, DAY_1, model("a", prompt="0.1"))
    await run_day(store, DAY_2, model("a", prompt="0.2"))

    result = await run_day(store, DAY_3, model("a", prompt="0.3"))

    [item] = result.items
    assert item.change is not None
    assert item.change.fields == [FieldChange(path="pricing.prompt", old="0.2", new="0.3")]


async def test_without_track_only_added_and_removed_entries_are_reported(
    store: SnapshotStore,
) -> None:
    collector = {key: value for key, value in COLLECTOR.items() if key != "track"}
    await run_day(store, DAY_1, model("a", prompt="0.1"), model("b"), collector=collector)

    result = await run_day(store, DAY_2, model("a", prompt="0.2"), model("c"), collector=collector)

    assert [(item.title, item.change.kind) for item in result.items if item.change] == [
        ("Model c", "added"),
        ("Model b", "removed"),
    ]


async def test_tracking_a_new_expression_does_not_report_every_entry(store: SnapshotStore) -> None:
    only_price = COLLECTOR | {"track": ["pricing.prompt"]}
    await run_day(store, DAY_1, model("a"), model("b"), collector=only_price)

    # The registry now tracks the context length too; the earlier snapshot did not.
    first = await run_day(store, DAY_2, model("a", context=1), model("b"))
    second = await run_day(store, DAY_3, model("a", context=2), model("b"))

    assert first.items == []
    [item] = second.items
    assert item.change is not None
    assert item.change.fields == [FieldChange(path="context_length", old=1, new=2)]


# --- entries that cannot be used ---------------------------------------------------------------


async def test_entries_without_a_string_key_are_invalid(
    tmp_path: Path, store: SnapshotStore
) -> None:
    keyless = {"name": "No key", "pricing": {}}
    numeric = model("x") | {"id": 7}

    result = await run_day(store, DAY_1, model("a"), keyless, numeric)

    assert (result.items, result.note) == ([], "baseline created")
    assert result.dropped_invalid == 2
    written = json.loads(
        (tmp_path / "state/snapshots/test-source/2026-10-28.json").read_text(encoding="utf-8")
    )
    assert list(written["entries"]) == ["a"]


async def test_a_malformed_entry_next_to_good_ones_is_dropped_and_counted(
    store: SnapshotStore,
) -> None:
    """Design §12: the source fails only when every entry is malformed, changed or not."""
    await run_day(store, DAY_1, model("a"), model("b"))
    keyless = {"name": "No key"}
    nameless = model("c") | {"name": None}

    result = await run_day(store, DAY_2, model("a"), model("b"), keyless, nameless)

    assert result.items == []
    assert result.dropped_invalid == 2


async def test_a_response_of_only_malformed_entries_fails_even_when_entries_were_there_before(
    tmp_path: Path, store: SnapshotStore
) -> None:
    """The earlier entries would all read as removed; that is not a usable response."""
    await run_day(store, DAY_1, model("a"), model("b"))
    numeric = [model("a") | {"id": 1}, model("b") | {"id": 2}]

    with pytest.raises(FetchError) as caught:
        await run_day(store, DAY_2, *numeric)

    assert caught.value.reason == "invalid_items"
    assert caught.value.detail.startswith("all 2 entries had no usable key")
    assert snapshot_files(tmp_path) == ["2026-10-28.json"]


EMPTY_NOTE = "empty response; previous snapshot kept"


async def test_an_empty_response_keeps_the_previous_snapshot(
    tmp_path: Path, store: SnapshotStore
) -> None:
    """A transient empty 200 must not report every entry removed, and every one added after."""
    await run_day(store, DAY_1, model("a"), model("b"))

    result = await run_day(store, DAY_2)

    assert result.items == []
    assert result.note == EMPTY_NOTE
    assert (result.dropped_window, result.dropped_invalid) == (0, 0)
    assert (result.url, result.http_status) == (URL, 200)
    assert snapshot_files(tmp_path) == ["2026-10-28.json"]  # nothing written for the run date
    for later in (DAY_2, DAY_3):
        earlier = store.previous(SOURCE, later)
        assert earlier is not None
        assert list(earlier["entries"]) == ["a", "b"]


async def test_the_day_after_an_empty_response_reports_no_changes(store: SnapshotStore) -> None:
    await run_day(store, DAY_1, model("a"), model("b"))
    await run_day(store, DAY_2)

    result = await run_day(store, DAY_3, model("a"), model("b"))

    assert (result.items, result.note) == ([], None)


async def test_an_empty_response_leaves_the_snapshot_the_date_already_has(
    tmp_path: Path, store: SnapshotStore
) -> None:
    await run_day(store, DAY_1, model("a"))
    await run_day(store, DAY_2, model("a"), model("b"))
    snapshot = tmp_path / "state/snapshots/test-source/2026-10-29.json"
    written = snapshot.read_bytes()

    result = await run_day(store, DAY_2)

    assert (result.items, result.note) == ([], EMPTY_NOTE)
    assert snapshot.read_bytes() == written


async def test_an_empty_response_after_an_empty_snapshot_is_written(
    tmp_path: Path, store: SnapshotStore
) -> None:
    """Only a previous snapshot with entries is worth keeping."""
    await run_day(store, DAY_1)

    result = await run_day(store, DAY_2)

    assert (result.items, result.note) == ([], None)
    assert snapshot_files(tmp_path) == ["2026-10-28.json", "2026-10-29.json"]


async def test_an_added_and_a_removed_entry_with_the_same_item_id_give_one_item(
    store: SnapshotStore,
) -> None:
    """A source whose key changed but whose link did not: the id comes from the mapped id."""
    same_id = {"id": "old-key", "name": "Model", "created": LONG_AGO}
    collector = COLLECTOR | {"fields": COLLECTOR["fields"] | {"id": "slug"}}
    await run_day(store, DAY_1, same_id | {"slug": "the-model"}, collector=collector)

    result = await run_day(
        store, DAY_2, same_id | {"id": "new-key", "slug": "the-model"}, collector=collector
    )

    assert [item.change.kind for item in result.items if item.change] == ["added"]


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (b"not json", "parse_error"),
        (json.dumps({"data": {"a": 1}}).encode(), "parse_error"),
        (json.dumps({"data": [{"name": "No key"}, {"id": 5}]}).encode(), "invalid_items"),
        # Keys are fine but no entry has a name for a title, so the mapping is wrong.
        (json.dumps({"data": [{"id": "a"}, {"id": "b"}]}).encode(), "invalid_items"),
    ],
    ids=["not-json", "items-not-a-list", "no-keys", "no-titles"],
)
async def test_failed_source_does_not_write_snapshot(
    tmp_path: Path, store: SnapshotStore, body: bytes, reason: str
) -> None:
    with pytest.raises(FetchError) as caught:
        await collect(COLLECTOR, serving(URL, body), robots=False, run_date=DAY_1, snapshots=store)

    assert caught.value.reason == reason
    assert not (tmp_path / "state").exists()


async def test_a_source_that_fails_leaves_the_snapshots_it_has(
    tmp_path: Path, store: SnapshotStore
) -> None:
    await run_day(store, DAY_1, model("a"))
    router = respx.Router()
    router.get(URL).respond(500)

    with pytest.raises(FetchError) as caught:
        await collect(
            COLLECTOR,
            httpx.MockTransport(router.handler),
            robots=False,
            run_date=DAY_2,
            snapshots=store,
        )

    assert caught.value.reason == "http_error"
    assert snapshot_files(tmp_path) == ["2026-10-28.json"]


async def test_the_failed_day_is_compared_with_the_last_good_one(store: SnapshotStore) -> None:
    await run_day(store, DAY_1, model("a", prompt="0.1"))
    with pytest.raises(FetchError):
        await collect(
            COLLECTOR, serving(URL, b"not json"), robots=False, run_date=DAY_2, snapshots=store
        )

    result = await run_day(store, DAY_3, model("a", prompt="0.2"))

    [item] = result.items
    assert item.change is not None
    assert item.change.fields == [FieldChange(path="pricing.prompt", old="0.1", new="0.2")]


# --- recorded responses ------------------------------------------------------------------------

# snapshot-openrouter.yaml was recorded from https://openrouter.ai/api/v1/models (robots.txt
# included) and cut down from 456 models to these five. snapshot-openrouter-next-day.yaml is a
# copy edited by hand to stand for the next day: GPT-6.1 Terra's prompt price is lower, GPT-4 is
# gone, and Aurora 1 (written by hand) is new.
RECORDED_MODELS = [
    "particle-ai/particle-1",
    "openai/gpt-6.1-terra",
    "recursive/flint-v1.0:free",
    "openai/gpt-4",
    "moonshotai/kimi-k3.1-pro",
]


@pytest.mark.vcr
@pytest.mark.default_cassette("snapshot-openrouter.yaml")
async def test_first_run_from_cassette(tmp_path: Path, store: SnapshotStore) -> None:
    result = await collect(OPENROUTER, run_date=DAY_1, snapshots=store)

    assert result.url == "https://openrouter.ai/api/v1/models"
    assert (result.items, result.note, result.http_status) == ([], "baseline created", 200)
    assert (result.dropped_window, result.dropped_invalid) == (0, 0)
    written = json.loads(
        (tmp_path / "state/snapshots/test-source/2026-10-28.json").read_text(encoding="utf-8")
    )
    assert list(written["entries"]) == sorted(RECORDED_MODELS)
    terra = written["entries"]["openai/gpt-6.1-terra"]
    assert terra["fields"]["title"] == "OpenAI: GPT-6.1 Terra"
    assert terra["fields"]["url"] == "https://openrouter.ai/openai/gpt-6.1-terra"
    assert terra["tracked"]["context_length"] == 1_050_000
    assert terra["tracked"]["pricing"]["prompt"] == "0.000001"


async def next_day(
    store: SnapshotStore, cassette: Callable[[str], AbstractContextManager[Any]]
) -> KindResult:
    """Run the recorded day, then the edited copy as the day after."""
    with cassette("snapshot-openrouter.yaml"):
        await collect(OPENROUTER, run_date=DAY_1, snapshots=store)
    with cassette("snapshot-openrouter-next-day.yaml"):
        return await collect(OPENROUTER, run_date=DAY_2, snapshots=store)


async def test_next_day_emits_price_change(
    store: SnapshotStore, cassette: Callable[[str], AbstractContextManager[Any]]
) -> None:
    result = await next_day(store, cassette)

    assert result.note is None
    assert (result.dropped_window, result.dropped_invalid) == (0, 0)
    assert [(item.title, item.change.kind) for item in result.items if item.change] == [
        ("Example Labs: Aurora 1", "added"),
        ("OpenAI: GPT-6.1 Terra", "changed"),
        ("OpenAI: GPT-4", "removed"),
    ]
    added, changed, removed = result.items
    validated(result.items)

    # The registry tracks the whole pricing object, so the change holds the old and new objects.
    assert changed.change is not None
    [price] = changed.change.fields
    assert price.path == "pricing"
    assert (price.old["prompt"], price.new["prompt"]) == ("0.000001", "0.0000008")
    assert price.old | {"prompt": None} == price.new | {"prompt": None}  # nothing else differs
    assert changed.url == "https://openrouter.ai/openai/gpt-6.1-terra"
    assert changed.published == "2026-10-26T18:13:29Z"

    assert added.change is not None
    assert added.url == "https://openrouter.ai/example-labs/aurora-1"
    assert added.published == "2026-10-29T05:00:00Z"
    assert {field.path for field in added.change.fields} == {"pricing", "context_length"}

    # GPT-4 is long gone from the response; it keeps the title, link, and date it had.
    assert removed.change is not None
    assert removed.url == "https://openrouter.ai/openai/gpt-4"
    assert removed.published == "2023-05-28T00:00:00Z"
    assert FieldChange(path="context_length", old=8191, new=None) in removed.change.fields


async def test_same_date_rerun_gives_the_same_diff_from_cassettes(
    tmp_path: Path, store: SnapshotStore, cassette: Callable[[str], AbstractContextManager[Any]]
) -> None:
    first = await next_day(store, cassette)
    snapshot = tmp_path / "state/snapshots/test-source/2026-10-29.json"
    first_file = snapshot.read_bytes()

    with cassette("snapshot-openrouter-next-day.yaml"):
        second = await collect(OPENROUTER, run_date=DAY_2, snapshots=store)

    assert len(first.items) == 3
    assert dumped(second) == dumped(first)
    assert snapshot.read_bytes() == first_file
    assert snapshot_files(tmp_path) == ["2026-10-28.json", "2026-10-29.json"]
