"""What the tests of the collector kinds share: a fetcher, a source context, and a way to run one.

A test module of its own for each kind imports from here, never from another test module.
"""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
import respx
from pydantic import TypeAdapter

from pulseai.collect.fetch import Fetcher
from pulseai.collect.kinds import KindResult, SourceContext, run_collector
from pulseai.collect.snapshots import SnapshotStore
from pulseai.collect.window import Window
from pulseai.config import load_config
from pulseai.models.collected import CollectedItem
from pulseai.models.config import CollectConfig
from pulseai.models.sources import CollectorSource

NOW = datetime(2026, 10, 29, 6, 0, tzinfo=UTC)
ITEM = TypeAdapter(CollectedItem)

# The feed and json kinds never touch snapshots. A run that tried to write one here would fail,
# because an unprivileged user cannot create this directory.
NO_SNAPSHOTS = SnapshotStore(Path("/nonexistent/instance"), keep=2)

# The cassettes were recorded on this day, and this window runs from a week before it to its end.
# The feeds and lists hold older entries too, which the window drops.
RECORDED_ON = date(2026, 10, 29)
RECORDED_WINDOW = Window(
    since=datetime(2026, 10, 22, tzinfo=UTC), until=datetime(2026, 10, 30, tzinfo=UTC)
)


def source(collector: dict[str, Any], *, changelog: bool | None = None) -> CollectorSource:
    data: dict[str, Any] = {
        "id": "test-source",
        "name": "Test source",
        "tier": "T1",
        "sections": ["research"],
        "trust": 3,
        "enabled": True,
        "via": "collector",
        "collector": collector,
    }
    if changelog is not None:
        data["changelog"] = changelog
    return CollectorSource.model_validate(data)


async def no_sleep(_delay: float) -> None:
    """Retries and rate-limit waits never wait in tests."""


def context(
    fetcher: Fetcher,
    *,
    window: Window = RECORDED_WINDOW,
    run_date: date = RECORDED_ON,
    snapshots: SnapshotStore = NO_SNAPSHOTS,
    settings: CollectConfig | None = None,
) -> SourceContext:
    config = load_config()  # inside a test, where PULSE__ variables are cleared
    return SourceContext(
        fetcher=fetcher,
        window=window,
        run_date=run_date,
        settings=settings or config.collect,
        config=config.model_dump(mode="json"),
        snapshots=snapshots,
        now=NOW,
    )


def make_fetcher(
    transport: httpx.AsyncBaseTransport | None = None,
    *,
    robots: bool = True,
    environ: dict[str, str] | None = None,
    settings: CollectConfig | None = None,
) -> Fetcher:
    """A fetcher with the engine's defaults. `transport=None` is the real transport, which a
    cassette replays; robots.txt is checked, so the cassettes hold those requests too.
    """
    settings = settings or load_config().collect
    return Fetcher(
        settings.model_copy(update={"respect_robots": robots}),
        user_agent=settings.user_agent.format(version="0.0.0"),
        cache_path=None,
        host_rates={},
        environ=environ or {},
        transport=transport,
        sleep=no_sleep,
    )


async def collect(
    collector: dict[str, Any],
    transport: httpx.AsyncBaseTransport | None = None,
    *,
    changelog: bool | None = None,
    window: Window = RECORDED_WINDOW,
    run_date: date = RECORDED_ON,
    snapshots: SnapshotStore = NO_SNAPSHOTS,
    robots: bool = True,
    environ: dict[str, str] | None = None,
    settings: CollectConfig | None = None,
) -> KindResult:
    async with make_fetcher(
        transport, robots=robots, environ=environ, settings=settings
    ) as fetcher:
        return await run_collector(
            source(collector, changelog=changelog),
            context(
                fetcher, window=window, run_date=run_date, snapshots=snapshots, settings=settings
            ),
        )


def serving(url: str, body: object | bytes, **response: Any) -> httpx.MockTransport:
    router = respx.Router()
    content = body if isinstance(body, bytes) else json.dumps(body).encode()
    router.get(url).respond(200, content=content, **response)
    return httpx.MockTransport(router.handler)
