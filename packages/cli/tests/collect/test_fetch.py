import email.utils
import gzip
import time
import tracemalloc
import zlib
from collections.abc import AsyncIterator, Callable, Mapping
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from structlog.testing import capture_logs

from pulseai.collect.fetch import Fetcher, FetchError
from pulseai.config import load_config
from pulseai.models.config import CollectConfig
from pulseai.models.sources import HttpOptions

pytestmark = pytest.mark.anyio

USER_AGENT = "PulseAI/1.2.3 (+https://example.org/bot)"
CREDENTIAL = "s3cret-token-value"
FEED = "https://example.com/feed.xml"
ROBOTS = "https://example.com/robots.txt"
API = "https://api.example.com/v1/items"
CDN = "https://cdn.example.net/feed.xml"
AUTH_ENV = "PULSE_TEST_TOKEN"
BEARER = HttpOptions(auth_env=AUTH_ENV, auth_prefix="Bearer ")
API_KEY = HttpOptions(auth_header="X-Api-Key", auth_env=AUTH_ENV)


class Sleeps:
    """An injected sleep that records each delay instead of waiting."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


class Body(httpx.AsyncByteStream):
    """A body sent over the "network" in chunks, as a real transport does; notes its close."""

    def __init__(
        self, data: bytes, *, chunk: int = 64 * 1024, fail: Exception | None = None
    ) -> None:
        self.data = data
        self.chunk = chunk
        self.fail = fail
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for start in range(0, len(self.data), self.chunk):
            yield self.data[start : start + self.chunk]
        if self.fail is not None:
            raise self.fail

    async def aclose(self) -> None:
        self.closed = True


@cache
def gzip_bomb(decoded_mib: int) -> bytes:
    """Gzip of `decoded_mib` MiB of zeros (about a thousandth of that on the wire)."""
    compressor = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)
    block = bytes(1 << 20)
    return b"".join(compressor.compress(block) for _ in range(decoded_mib)) + compressor.flush()


async def peak_allocation(fetcher: Fetcher, url: str) -> tuple[FetchError, int]:
    """The error a fetch fails with, and the most memory allocated while it ran."""
    async with fetcher:
        tracemalloc.start()
        try:
            with pytest.raises(FetchError) as caught:
                await fetcher.get(url)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
    return caught.value, peak


def settings(**overrides: Any) -> CollectConfig:
    """Engine defaults with small caps, robots off, and the given overrides."""
    small = {
        "respect_robots": False,
        "retries": 2,
        "max_wait_seconds": 120,
        "max_redirects": 2,
        "max_response_bytes": 1024,
    }
    return load_config().collect.model_copy(update={**small, **overrides})


def make(
    handler: Callable[[httpx.Request], Any],
    *,
    sleep: Sleeps | None = None,
    environ: Mapping[str, str] | None = None,
    cache_path: Path | None = None,
    host_rates: Mapping[str, int] | None = None,
    user_agent: str = USER_AGENT,
    **overrides: Any,
) -> Fetcher:
    return Fetcher(
        settings(**overrides),
        user_agent=user_agent,
        cache_path=cache_path,
        host_rates=host_rates or {},
        environ=environ or {},
        transport=httpx.MockTransport(handler),
        sleep=sleep or Sleeps(),
    )


async def failure(fetcher: Fetcher, url: str, http: HttpOptions | None = None) -> FetchError:
    async with fetcher:
        with pytest.raises(FetchError) as caught:
            await fetcher.get(url, http)
    return caught.value


# --- user agent, redirects, size ---------------------------------------------------------------


async def test_sends_user_agent_and_follows_redirect_cap() -> None:
    router = respx.Router()
    router.get("https://example.com/a").respond(301, headers={"Location": "/b"})
    router.get("https://example.com/b").respond(302, headers={"Location": "/c"})
    router.get("https://example.com/c").respond(200, text="ok")
    router.get("https://example.com/x").respond(301, headers={"Location": "/y"})
    router.get("https://example.com/y").respond(301, headers={"Location": "/z"})
    router.get("https://example.com/z").respond(301, headers={"Location": "/w"})
    beyond = router.get("https://example.com/w").respond(200)

    async with make(router.handler, max_redirects=2) as fetcher:
        result = await fetcher.get("https://example.com/a")
        with pytest.raises(FetchError) as caught:
            await fetcher.get("https://example.com/x")

    assert (result.status, result.content) == (200, b"ok")
    assert result.url == "https://example.com/a"
    assert result.final_url == "https://example.com/c"
    assert all(call.request.headers["User-Agent"] == USER_AGENT for call in router.calls)
    assert caught.value.reason == "http_error"
    assert not beyond.called


async def test_records_cross_host_redirect() -> None:
    router = respx.Router()
    router.get(FEED).respond(301, headers={"Location": CDN})
    router.get(CDN).respond(200, text="<rss/>")

    async with make(router.handler) as fetcher:
        result = await fetcher.get(FEED)

    assert result.url == FEED
    assert result.final_url == CDN
    assert httpx.URL(result.final_url).host == "cdn.example.net"


async def test_body_over_cap_fails_too_large() -> None:
    chunks_read = 0

    async def endless_body() -> AsyncIterator[bytes]:
        nonlocal chunks_read
        for _ in range(100):
            chunks_read += 1
            yield b"x" * 512

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=endless_body())

    error = await failure(make(handler, max_response_bytes=1024), FEED)

    assert error.reason == "too_large"
    assert chunks_read < 100


async def test_body_at_cap_is_read() -> None:
    router = respx.Router()
    router.get(FEED).respond(200, content=b"x" * 1024)

    async with make(router.handler, max_response_bytes=1024) as fetcher:
        result = await fetcher.get(FEED)

    assert len(result.content) == 1024


MAX_BYTES = 64 * 1024
PEAK_BOUND = 4 * 2**20  # the bombs below decode to 32 MiB; reading under the cap stays far below


async def test_gzip_bomb_fails_too_large_without_inflating_it() -> None:
    bomb = gzip_bomb(32)
    assert len(bomb) < MAX_BYTES  # small on the wire: only the decoded size is over the cap

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Encoding": "gzip"}, stream=Body(bomb))

    error, peak = await peak_allocation(make(handler, max_response_bytes=MAX_BYTES), FEED)

    assert error.reason == "too_large"
    assert peak < PEAK_BOUND


async def test_stacked_content_codings_are_refused_without_decoding() -> None:
    stacked = gzip.compress(gzip_bomb(32))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Encoding": "gzip, gzip"}, stream=Body(stacked))

    error, peak = await peak_allocation(make(handler, max_response_bytes=MAX_BYTES), FEED)

    assert error.reason == "parse_error"
    assert peak < PEAK_BOUND


@pytest.mark.parametrize(
    ("coding", "encode"),
    [
        ("gzip", gzip.compress),
        ("x-gzip", gzip.compress),
        ("GZIP", gzip.compress),
        ("deflate", zlib.compress),
        ("identity", bytes),
    ],
)
async def test_one_gzip_or_deflate_coding_is_decoded(
    coding: str, encode: Callable[[bytes], bytes]
) -> None:
    text = b"<rss>" + b"item " * 2000 + b"</rss>"
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200, headers={"Content-Encoding": coding}, stream=Body(encode(text), chunk=7)
        )

    async with make(handler, max_response_bytes=len(text)) as fetcher:
        result = await fetcher.get(FEED)

    assert result.content == text
    assert requests[0].headers["Accept-Encoding"] == "gzip, deflate"


@pytest.mark.parametrize(
    ("coding", "body"),
    [("br", b"\x1b\x00\x00"), ("gzip", b"\x1f\x8b not really gzip"), ("deflate", b"raw?")],
    ids=["unsupported", "corrupt-gzip", "corrupt-deflate"],
)
async def test_undecodable_body_fails_parse_error(coding: str, body: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Encoding": coding}, stream=Body(body))

    error = await failure(make(handler), FEED)

    assert error.reason == "parse_error"


# --- retries and rate limits -------------------------------------------------------------------


async def test_timeout_fails_timeout() -> None:
    router = respx.Router()
    route = router.get(FEED).mock(side_effect=httpx.ReadTimeout)
    sleeps = Sleeps()

    error = await failure(make(router.handler, sleep=sleeps, retries=2), FEED)

    assert error.reason == "timeout"
    assert route.call_count == 3
    assert len(sleeps.delays) == 2


async def test_connect_error_fails_network_error() -> None:
    router = respx.Router()
    route = router.get(FEED).mock(side_effect=httpx.ConnectError)

    error = await failure(make(router.handler, retries=1), FEED)

    assert error.reason == "network_error"
    assert route.call_count == 2


async def test_5xx_then_200_succeeds() -> None:
    router = respx.Router()
    route = router.get(FEED).mock(side_effect=[httpx.Response(503), httpx.Response(200)])
    sleeps = Sleeps()

    async with make(router.handler, sleep=sleeps) as fetcher:
        result = await fetcher.get(FEED)

    assert result.status == 200
    assert route.call_count == 2
    assert len(sleeps.delays) == 1
    assert 0 <= sleeps.delays[0] <= 120


async def test_persistent_5xx_fails_http_error_with_status() -> None:
    router = respx.Router()
    route = router.get(FEED).respond(502)
    sleeps = Sleeps()

    error = await failure(make(router.handler, sleep=sleeps, retries=2), FEED)

    assert (error.reason, error.status) == ("http_error", 502)
    assert route.call_count == 3
    assert len(sleeps.delays) == 2


async def test_429_retry_after_within_budget_waits_then_succeeds() -> None:
    router = respx.Router()
    router.get(FEED).mock(
        side_effect=[httpx.Response(429, headers={"Retry-After": "30"}), httpx.Response(200)]
    )
    sleeps = Sleeps()

    async with make(router.handler, sleep=sleeps, max_wait_seconds=120) as fetcher:
        result = await fetcher.get(FEED)

    assert result.status == 200
    assert sleeps.delays == [30]


async def test_429_beyond_budget_fails_rate_limited_without_sleeping() -> None:
    router = respx.Router()
    route = router.get(FEED).respond(429, headers={"Retry-After": "3600"})
    sleeps = Sleeps()

    error = await failure(make(router.handler, sleep=sleeps, max_wait_seconds=120), FEED)

    assert (error.reason, error.status) == ("rate_limited", 429)
    assert sleeps.delays == []
    assert route.call_count == 1


async def test_retry_after_http_date_is_a_wait_until_then() -> None:
    later = email.utils.format_datetime(datetime.now(UTC) + timedelta(seconds=60), usegmt=True)
    router = respx.Router()
    router.get(FEED).mock(
        side_effect=[httpx.Response(429, headers={"Retry-After": later}), httpx.Response(200)]
    )
    sleeps = Sleeps()

    async with make(router.handler, sleep=sleeps) as fetcher:
        await fetcher.get(FEED)

    assert len(sleeps.delays) == 1
    assert 50 <= sleeps.delays[0] <= 60


async def test_rate_limit_waits_count_as_retries() -> None:
    router = respx.Router()
    route = router.get(FEED).respond(429, headers={"Retry-After": "1"})
    sleeps = Sleeps()

    error = await failure(make(router.handler, sleep=sleeps, retries=2), FEED)

    assert (error.reason, error.status) == ("rate_limited", 429)
    assert sleeps.delays == [1, 1]
    assert route.call_count == 3


async def test_github_403_ratelimit_is_a_rate_limit() -> None:
    def exhausted(reset_in: int) -> httpx.Response:
        reset = str(int(time.time()) + reset_in)
        return httpx.Response(
            403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": reset}
        )

    router = respx.Router()
    router.get(FEED).mock(side_effect=[exhausted(30), httpx.Response(200)])
    router.get(API).mock(side_effect=[exhausted(3600)])
    sleeps = Sleeps()

    async with make(router.handler, sleep=sleeps, max_wait_seconds=120) as fetcher:
        result = await fetcher.get(FEED)
        with pytest.raises(FetchError) as caught:
            await fetcher.get(API)

    assert result.status == 200
    assert len(sleeps.delays) == 1
    assert 0 < sleeps.delays[0] <= 30
    assert (caught.value.reason, caught.value.status) == ("rate_limited", 403)


@pytest.mark.parametrize("headers", [{}, {"X-RateLimit-Remaining": "12"}])
async def test_plain_403_is_http_error(headers: dict[str, str]) -> None:
    router = respx.Router()
    route = router.get(FEED).respond(403, headers=headers)
    sleeps = Sleeps()

    error = await failure(make(router.handler, sleep=sleeps), FEED)

    assert (error.reason, error.status) == ("http_error", 403)
    assert route.call_count == 1
    assert sleeps.delays == []


async def test_source_http_options_override_timeout_and_retries() -> None:
    router = respx.Router()
    route = router.get(FEED).respond(503)

    error = await failure(
        make(router.handler, timeout_seconds=20, retries=3),
        FEED,
        HttpOptions(timeout_seconds=4.5, retries=0),
    )

    assert error.reason == "http_error"
    assert route.call_count == 1
    assert route.calls[0].request.extensions["timeout"]["read"] == 4.5


async def test_per_host_rate_limit_spaces_requests() -> None:
    router = respx.Router()
    router.get(FEED).respond(200)
    router.get("https://example.com/other.xml").respond(200)

    async with make(
        router.handler, per_host_per_minute=30, host_rates={"example.com": 2}
    ) as fetcher:
        await fetcher.get(FEED)
        await fetcher.get("https://example.com/other.xml")
        limiter = fetcher.limiter("example.com")
        unknown = fetcher.limiter("other.org")

        assert (limiter.max_rate, limiter.time_period) == (2, 60)
        # Both requests drew from this host's bucket, so a third would wait.
        assert not limiter.has_capacity()
        assert fetcher.limiter("example.com") is limiter
        assert (unknown.max_rate, unknown.time_period) == (30, 60)
        assert unknown.has_capacity()


# --- robots.txt --------------------------------------------------------------------------------


async def test_robots_disallow_fails_robots_disallowed() -> None:
    router = respx.Router()
    router.get(ROBOTS).respond(200, text="User-agent: *\nDisallow: /*.atom$\n")
    atom = router.get("https://example.com/releases.atom").respond(200)
    router.get("https://example.com/releases").respond(200, text="ok")

    async with make(router.handler, respect_robots=True) as fetcher:
        with capture_logs() as logs, pytest.raises(FetchError) as caught:
            await fetcher.get("https://example.com/releases.atom")
        allowed = await fetcher.get("https://example.com/releases")

    assert caught.value.reason == "robots_disallowed"
    assert not atom.called
    assert allowed.status == 200
    assert any(entry["event"] == "robots_disallowed" for entry in logs)


@pytest.mark.parametrize(
    ("user_agent", "allowed"),
    [(USER_AGENT, False), ("OtherBot/2.0 (+https://example.org/other)", True)],
)
async def test_robots_group_is_chosen_by_the_user_agent_product_token(
    user_agent: str, allowed: bool
) -> None:
    router = respx.Router()
    router.get(ROBOTS).respond(
        200, text="User-agent: PulseAI\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
    )
    feed = router.get(FEED).respond(200)

    async with make(router.handler, respect_robots=True, user_agent=user_agent) as fetcher:
        try:
            await fetcher.get(FEED)
        except FetchError as exc:
            assert exc.reason == "robots_disallowed"

    assert feed.called is allowed


@pytest.mark.parametrize("status", [401, 403, 404, 410])
async def test_robots_404_allows_everything(status: int) -> None:
    router = respx.Router()
    router.get(ROBOTS).respond(status)
    router.get(FEED).respond(200)

    async with make(router.handler, respect_robots=True) as fetcher:
        result = await fetcher.get(FEED)

    assert result.status == 200


@pytest.mark.parametrize(
    "fail_robots",
    [lambda route: route.respond(503), lambda route: route.mock(side_effect=httpx.ConnectError)],
    ids=["5xx", "unreachable"],
)
async def test_robots_5xx_disallows(fail_robots: Callable[[respx.Route], object]) -> None:
    router = respx.Router()
    fail_robots(router.get(ROBOTS))
    feed = router.get(FEED).respond(200)

    error = await failure(make(router.handler, respect_robots=True), FEED)

    assert error.reason == "robots_disallowed"
    assert not feed.called


async def test_robots_fetched_once_per_host() -> None:
    router = respx.Router()
    robots = router.get(ROBOTS).respond(200, text="User-agent: *\nAllow: /\n")
    other_robots = router.get("https://other.org/robots.txt").respond(404)
    router.get(FEED).respond(200)
    router.get("https://example.com/other.xml").respond(200)
    router.get("https://other.org/feed").respond(200)

    async with make(router.handler, respect_robots=True) as fetcher:
        await fetcher.get(FEED)
        await fetcher.get("https://example.com/other.xml")
        await fetcher.get("https://other.org/feed")

    assert robots.call_count == 1
    assert other_robots.call_count == 1
    assert robots.calls[0].request.headers["User-Agent"] == USER_AGENT


async def test_redirect_target_robots_are_checked() -> None:
    router = respx.Router()
    router.get(ROBOTS).respond(200, text="User-agent: *\nAllow: /\n")
    router.get("https://cdn.example.net/robots.txt").respond(
        200, text="User-agent: *\nDisallow: /\n"
    )
    router.get(FEED).respond(301, headers={"Location": CDN})
    target = router.get(CDN).respond(200)

    error = await failure(make(router.handler, respect_robots=True), FEED)

    assert error.reason == "robots_disallowed"
    assert not target.called


async def test_robots_rate_limit_fails_the_source_as_rate_limited() -> None:
    router = respx.Router()
    router.get(ROBOTS).respond(429, headers={"Retry-After": "3600"})
    feed = router.get(FEED).respond(200)

    error = await failure(make(router.handler, respect_robots=True), FEED)

    assert error.reason == "rate_limited"
    assert not feed.called


# --- auth --------------------------------------------------------------------------------------


async def test_auth_header_only_on_its_source() -> None:
    router = respx.Router()
    bearer = router.get(API).respond(200)
    keyed = router.get("https://api.example.com/v1/keyed").respond(200)
    public = router.get(FEED).respond(200)

    async with make(router.handler, environ={AUTH_ENV: CREDENTIAL}) as fetcher:
        await fetcher.get(API, BEARER)
        await fetcher.get("https://api.example.com/v1/keyed", API_KEY)
        await fetcher.get(FEED)
        await fetcher.get(FEED, HttpOptions(timeout_seconds=5))

    assert bearer.calls[0].request.headers["Authorization"] == f"Bearer {CREDENTIAL}"
    assert keyed.calls[0].request.headers["X-Api-Key"] == CREDENTIAL
    assert "Authorization" not in keyed.calls[0].request.headers
    for call in public.calls:
        assert "Authorization" not in call.request.headers
        assert CREDENTIAL not in str(call.request.headers)


@pytest.mark.parametrize("environ", [{}, {AUTH_ENV: ""}])
async def test_missing_required_auth_env_fails(environ: dict[str, str]) -> None:
    router = respx.Router()
    router.get("https://api.example.com/robots.txt").respond(404)
    router.get(API).respond(200)

    error = await failure(make(router.handler, environ=environ, respect_robots=True), API, BEARER)

    assert error.reason == "missing_auth_env"
    assert AUTH_ENV in error.detail
    assert router.calls.call_count == 0


@pytest.mark.parametrize("environ", [{}, {AUTH_ENV: ""}])
async def test_optional_auth_env_unset_sends_unauthenticated(environ: dict[str, str]) -> None:
    router = respx.Router()
    route = router.get(API).respond(200)
    optional = HttpOptions(auth_env=AUTH_ENV, auth_prefix="Bearer ", auth_optional=True)

    async with make(router.handler, environ=environ) as fetcher:
        result = await fetcher.get(API, optional)

    assert result.status == 200
    assert "Authorization" not in route.calls[0].request.headers


async def test_auth_value_that_is_not_a_header_value_fails_without_leaking() -> None:
    router = respx.Router()
    router.get(API).respond(200)
    broken = f"{CREDENTIAL}\r\nX-Injected: 1"

    error = await failure(make(router.handler, environ={AUTH_ENV: broken}), API, BEARER)

    assert error.reason == "missing_auth_env"
    assert CREDENTIAL not in str(error)
    assert router.calls.call_count == 0


@pytest.mark.parametrize("http", [BEARER, API_KEY], ids=["authorization", "custom-header"])
async def test_cross_origin_redirect_drops_the_auth_header(http: HttpOptions) -> None:
    header = http.auth_header or "Authorization"
    router = respx.Router()
    router.get(API).respond(302, headers={"Location": "/v2/items"})
    same_origin = router.get("https://api.example.com/v2/items").respond(
        302, headers={"Location": CDN}
    )
    other_origin = router.get(CDN).respond(200)

    async with make(router.handler, environ={AUTH_ENV: CREDENTIAL}) as fetcher:
        result = await fetcher.get(API, http)

    assert result.final_url == CDN
    assert CREDENTIAL in same_origin.calls[0].request.headers[header]
    assert header not in other_origin.calls[0].request.headers


async def test_errors_and_logs_never_carry_the_secret() -> None:
    router = respx.Router()
    router.get(API).mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(429, headers={"Retry-After": "1"}),
            httpx.Response(200),
        ]
    )
    leaky = router.get("https://api.example.com/v1/leaky").mock(
        side_effect=httpx.LocalProtocolError(f"Illegal header value b'Bearer {CREDENTIAL}'")
    )

    with capture_logs() as logs:
        async with make(router.handler, environ={AUTH_ENV: CREDENTIAL}) as fetcher:
            result = await fetcher.get(API, BEARER)
            with pytest.raises(FetchError) as caught:
                await fetcher.get("https://api.example.com/v1/leaky", BEARER)

    assert result.status == 200
    assert leaky.called
    assert caught.value.reason == "network_error"
    assert CREDENTIAL not in str(caught.value)
    assert caught.value.__cause__ is None
    events = {entry["event"] for entry in logs}
    assert {"fetch", "retry", "rate_limit_wait"} <= events
    assert CREDENTIAL not in repr(logs)
    fetched = next(entry for entry in logs if entry["event"] == "fetch")
    assert (fetched["url"], fetched["status"]) == (API, 200)


# --- caching -----------------------------------------------------------------------------------


@pytest.mark.parametrize("http", [BEARER, API_KEY], ids=["authorization", "custom-header"])
async def test_authorized_response_not_reused_from_cache(tmp_path: Path, http: HttpOptions) -> None:
    router = respx.Router()
    route = router.get(API).respond(200, headers={"Cache-Control": "max-age=600"}, text="mine")

    async with make(router.handler, environ={AUTH_ENV: CREDENTIAL}, cache_path=tmp_path) as fetcher:
        first = await fetcher.get(API, http)
        second = await fetcher.get(API, http)
        anonymous = await fetcher.get(API)

    assert route.call_count == 3
    assert not (first.from_cache or second.from_cache or anonymous.from_cache)


async def test_authorized_public_response_keeps_the_token_out_of_the_cache(tmp_path: Path) -> None:
    router = respx.Router()
    route = router.get(API).respond(200, headers={"Cache-Control": "public, max-age=600"})

    async with make(router.handler, environ={AUTH_ENV: CREDENTIAL}, cache_path=tmp_path) as fetcher:
        await fetcher.get(API, BEARER)
        await fetcher.get(API, BEARER)

    assert route.call_count == 2
    stored = b"".join(path.read_bytes() for path in tmp_path.rglob("*") if path.is_file())
    assert CREDENTIAL.encode() not in stored


async def test_fresh_response_served_from_cache(tmp_path: Path) -> None:
    router = respx.Router()
    route = router.get(FEED).respond(200, headers={"Cache-Control": "max-age=600"}, text="feed")

    async with make(router.handler, cache_path=tmp_path) as fetcher:
        first = await fetcher.get(FEED)
        second = await fetcher.get(FEED)

    assert route.call_count == 1
    assert (first.from_cache, second.from_cache) == (False, True)
    assert second.content == b"feed"


async def test_conditional_request_served_from_cache(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("If-None-Match") == '"v1"':
            return httpx.Response(304, headers={"ETag": '"v1"'})
        return httpx.Response(
            200, headers={"ETag": '"v1"', "Cache-Control": "no-cache"}, content=b"body"
        )

    router = respx.Router()
    route = router.get(FEED).mock(side_effect=handler)

    async with make(router.handler, cache_path=tmp_path) as fetcher:
        first = await fetcher.get(FEED)
        second = await fetcher.get(FEED)

    assert route.call_count == 2
    assert route.calls[1].request.headers["If-None-Match"] == '"v1"'
    assert (first.from_cache, second.from_cache) == (False, True)
    assert (second.status, second.content) == (200, b"body")


async def test_compressed_response_is_cached_and_replayed_decoded(tmp_path: Path) -> None:
    text = b"<feed>" + b"entry " * 500 + b"</feed>"
    sent: list[Body] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(Body(gzip.compress(text), chunk=100))
        headers = {"Content-Encoding": "gzip", "Cache-Control": "max-age=600"}
        return httpx.Response(200, headers=headers, stream=sent[-1])

    async with make(handler, cache_path=tmp_path, max_response_bytes=len(text)) as fetcher:
        first = await fetcher.get(FEED)
        second = await fetcher.get(FEED)

    assert len(sent) == 1
    assert (first.from_cache, second.from_cache) == (False, True)
    assert first.content == second.content == text


async def test_cache_releases_every_network_response(tmp_path: Path) -> None:
    sent: list[Body] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        status, headers, body = 200, {"Cache-Control": "max-age=600"}, Body(b"ok")
        if path == "/missing":
            status, body = 404, Body(b"not found")
        elif path == "/moved":
            status, headers = 301, {"Location": "/ok"}
        elif path == "/big":
            body = Body(b"x" * 4096, chunk=512)
        elif path == "/flaky":
            status = 503
        elif path == "/slow":
            body = Body(b"partial", fail=httpx.ReadTimeout("stalled"))
        sent.append(body)
        return httpx.Response(status, headers=headers, stream=body)

    async with make(handler, cache_path=tmp_path, max_response_bytes=1024, retries=1) as fetcher:
        for path, reason in [
            ("/missing", "http_error"),
            ("/big", "too_large"),
            ("/flaky", "http_error"),
            ("/slow", "timeout"),
        ]:
            with pytest.raises(FetchError) as caught:
                await fetcher.get(f"https://example.com{path}")
            assert caught.value.reason == reason
        moved = await fetcher.get("https://example.com/moved")
        still_open = [body for body in sent if not body.closed]

    assert moved.content == b"ok"
    assert len(sent) == 8  # 404, too large, 503 twice, stalled twice, the redirect, its target
    assert still_open == []


async def test_cookies_are_never_kept_or_sent(tmp_path: Path) -> None:
    cookie = "session=from-an-authorized-response"
    router = respx.Router()
    router.get(API).respond(200, headers={"Set-Cookie": f"{cookie}; Path=/"})
    public = router.get("https://api.example.com/v1/public").respond(
        200, headers={"Cache-Control": "public, max-age=60"}
    )
    router.get("https://api.example.com/login").respond(
        302, headers={"Set-Cookie": f"{cookie}; Path=/", "Location": "/v1/landing"}
    )
    landing = router.get("https://api.example.com/v1/landing").respond(200)

    environ = {AUTH_ENV: CREDENTIAL}
    async with make(router.handler, environ=environ, cache_path=tmp_path) as fetcher:
        await fetcher.get(API, BEARER)  # sets the cookie on an authorized response
        await fetcher.get("https://api.example.com/v1/public")  # anonymous, and stored
        await fetcher.get("https://api.example.com/login")  # sets it again, then redirects

    sent = [*public.calls, *landing.calls]
    assert len(sent) == 2
    assert all("Cookie" not in call.request.headers for call in sent)
    stored = b"".join(path.read_bytes() for path in tmp_path.rglob("*") if path.is_file())
    assert cookie.encode() not in stored
