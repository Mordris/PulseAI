"""The one HTTP client every collector request goes through, robots.txt and sitemaps included.

The rules that apply to every request live here, so collectors only call `Fetcher.get`:
HTTP caching, per-host rate limits, retries and rate-limit waits, robots.txt (RFC 9309), size
and redirect caps, and auth headers read from env vars, whose values never reach logs,
exception text, or the cache.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC
from email.utils import parsedate_to_datetime
from http import HTTPStatus
from pathlib import Path
from typing import Self

import anyio
import hishel
import hishel.httpx
import httpx
import structlog
from aiolimiter import AsyncLimiter
from protego import Protego
from structlog.typing import FilteringBoundLogger
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from pulseai.models.collect_run import Reason as FailureReason
from pulseai.models.config import CollectConfig
from pulseai.models.sources import HttpOptions

DEFAULT_AUTH_HEADER = "Authorization"
CACHE_FILE = "http.sqlite"
ROBOTS_PATH = "/robots.txt"
SECONDS_PER_MINUTE = 60
# RFC 9309 §2.3.1.4: when robots.txt can't be reached, assume everything is disallowed.
DISALLOW_ALL = "User-agent: *\nDisallow: /\n"
# Request extension marking a request that carries credentials; such requests skip the cache.
CREDENTIALED = "pulseai_credentialed"

__all__ = ["FailureReason", "FetchError", "FetchResult", "Fetcher"]

log: FilteringBoundLogger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class FetchResult:
    """A successful (2xx) response, read in full."""

    url: str  # the URL asked for
    final_url: str  # where redirects ended; its host differs from url's after a cross-host one
    status: int
    headers: Mapping[str, str]
    content: bytes
    from_cache: bool
    elapsed_ms: int


class FetchError(Exception):
    """A failed request, with the run summary's reason. Its text never holds a secret."""

    def __init__(self, reason: FailureReason, detail: str, *, status: int | None = None) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason: FailureReason = reason
        self.detail = detail
        self.status = status


class _RetryableError(Exception):
    """An attempt worth repeating: a 5xx, or a rate limit whose wait is acceptable or unknown."""

    def __init__(self, status: int, *, rate_limited: bool, wait: float | None = None) -> None:
        super().__init__(f"HTTP {status}")
        self.status = status
        self.rate_limited = rate_limited
        self.wait = wait


_RETRYABLE = (
    _RetryableError,
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
    TimeoutError,
)


class _CacheUnlessCredentialed(httpx.AsyncBaseTransport):
    """Sends requests that carry credentials past the cache, straight to the network.

    hishel's shared-cache rule (RFC 9111 §3.5) covers only the Authorization header, and hishel
    writes request headers into each stored entry. Skipping the cache for every credentialed
    request keeps a response to one from being stored or reused, whatever the header is
    called, and keeps the credential off disk.
    """

    def __init__(self, cache: httpx.AsyncBaseTransport, network: httpx.AsyncBaseTransport) -> None:
        self._cache = cache
        self._network = network

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        transport = self._network if request.extensions.get(CREDENTIALED) else self._cache
        return await transport.handle_async_request(request)

    async def aclose(self) -> None:
        await self._cache.aclose()  # also closes the network transport it wraps


def _is_digits(text: str) -> bool:
    return text.isascii() and text.isdigit()


def _is_rate_limited(response: httpx.Response) -> bool:
    """429, or GitHub's form of a rate limit: 403 with X-RateLimit-Remaining: 0."""
    status = response.status_code
    remaining = response.headers.get("X-RateLimit-Remaining", "").strip()
    return status == HTTPStatus.TOO_MANY_REQUESTS or (
        status == HTTPStatus.FORBIDDEN and remaining == "0"
    )


def _rate_limit_wait(headers: httpx.Headers, now: float) -> float | None:
    """Seconds the server asks to wait, from Retry-After or X-RateLimit-Reset; None if unsaid."""
    retry_after = headers.get("Retry-After", "").strip()
    if _is_digits(retry_after):
        return float(retry_after)
    if retry_after:
        try:
            when = parsedate_to_datetime(retry_after)
        except (TypeError, ValueError):
            pass
        else:
            if when.tzinfo is None:
                when = when.replace(tzinfo=UTC)
            return max(0.0, when.timestamp() - now)
    reset = headers.get("X-RateLimit-Reset", "").strip()
    if _is_digits(reset):
        return max(0.0, float(reset) - now)
    return None


def _same_origin(a: httpx.URL, b: httpx.URL) -> bool:
    return (a.scheme, a.host, a.port) == (b.scheme, b.host, b.port)


def _is_header_value(value: str) -> bool:
    """Printable ASCII only, so no CR, LF or other control character can reach the request."""
    return value.isascii() and value.isprintable()


def _describe(error: BaseException, *, credentialed: bool) -> str:
    """The error's type, and its message unless the request carried credentials.

    Library messages can quote request headers, so a credentialed request reports the type only.
    """
    message = "" if credentialed else str(error)
    return f"{type(error).__name__}: {message}" if message else type(error).__name__


async def _read_capped(response: httpx.Response, max_bytes: int) -> bytes:
    """The decoded body, read in chunks; stops and fails as soon as it passes `max_bytes`."""
    body = bytearray()
    async for chunk in response.aiter_bytes():
        body += chunk
        if len(body) > max_bytes:
            msg = f"response from {response.url} is larger than max_response_bytes ({max_bytes})"
            raise FetchError("too_large", msg)
    return bytes(body)


class Fetcher:
    """The shared async HTTP client for one collection run. Use it as an async context manager."""

    def __init__(
        self,
        settings: CollectConfig,
        *,
        user_agent: str,
        cache_path: Path | None,
        host_rates: Mapping[str, int],
        environ: Mapping[str, str],
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = anyio.sleep,
    ) -> None:
        """`cache_path=None` disables HTTP caching. `host_rates` maps hosts to requests per minute;
        other hosts get `settings.per_host_per_minute`. `sleep` is injectable so tests never wait.
        """
        self._settings = settings
        self._environ = environ
        self._sleep = sleep
        self._host_rates = {host.lower(): rate for host, rate in host_rates.items()}
        self._limiters: dict[str, AsyncLimiter] = {}
        # robots.txt groups are matched by the product token: "PulseAI" in "PulseAI/1.0 (+url)".
        self._product_token = user_agent.split("/", 1)[0].strip()
        self._robots: dict[str, Protego] = {}
        self._robots_locks: dict[str, anyio.Lock] = {}
        self._backoff = wait_exponential_jitter(max=settings.max_wait_seconds)

        network = transport or httpx.AsyncHTTPTransport()
        client_transport: httpx.AsyncBaseTransport = network
        if cache_path is not None:
            cache = hishel.httpx.AsyncCacheTransport(
                next_transport=network,
                storage=hishel.AsyncSqliteStorage(database_path=cache_path / CACHE_FILE),
                policy=hishel.SpecificationPolicy(cache_options=hishel.CacheOptions(shared=True)),
            )
            client_transport = _CacheUnlessCredentialed(cache, network)
        # Redirects are followed by hand (see _attempt) so each hop gets the robots check and
        # the host's rate limit, and credentials never follow a redirect to another origin.
        self._client = httpx.AsyncClient(
            transport=client_transport,
            headers={"User-Agent": user_agent},
            timeout=settings.timeout_seconds,
            follow_redirects=False,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._client.aclose()

    def limiter(self, host: str) -> AsyncLimiter:
        """The request budget for one host: its rate in `host_rates`, else `per_host_per_minute`."""
        limiter = self._limiters.get(host)
        if limiter is None:
            rate = self._host_rates.get(host, self._settings.per_host_per_minute)
            limiter = self._limiters[host] = AsyncLimiter(rate, SECONDS_PER_MINUTE)
        return limiter

    async def get(self, url: str, http: HttpOptions | None = None) -> FetchResult:
        """GET `url` under every shared rule. Raises FetchError with the failure reason.

        A source's `http` options override the timeout, retries and auth defaults.
        """
        options = http or HttpOptions()
        auth = self._auth(options)
        return await self._fetch(
            url,
            auth=auth,
            timeout=(
                self._settings.timeout_seconds
                if options.timeout_seconds is None
                else options.timeout_seconds
            ),
            retries=self._settings.retries if options.retries is None else options.retries,
            check_robots=self._settings.respect_robots,
        )

    def _auth(self, options: HttpOptions) -> tuple[str, str] | None:
        """The auth header as (name, value), or None. An empty env var counts as unset."""
        if options.auth_env is None:
            return None
        token = self._environ.get(options.auth_env, "")
        if not token:
            if options.auth_optional:
                return None
            msg = f"environment variable {options.auth_env} (http.auth_env) is not set"
            raise FetchError("missing_auth_env", msg)
        value = (options.auth_prefix or "") + token
        if not _is_header_value(value):
            msg = f"environment variable {options.auth_env} (http.auth_env) is not a header value"
            raise FetchError("missing_auth_env", msg)
        return (options.auth_header or DEFAULT_AUTH_HEADER, value)

    async def _fetch(
        self,
        url: str,
        *,
        auth: tuple[str, str] | None,
        timeout: float,
        retries: int,
        check_robots: bool,
    ) -> FetchResult:
        started = time.perf_counter()
        credentialed = auth is not None
        retrying = AsyncRetrying(
            stop=stop_after_attempt(retries + 1),
            wait=self._wait,
            retry=retry_if_exception_type(_RETRYABLE),
            sleep=self._sleep,
            before_sleep=lambda state: self._log_wait(state, url, credentialed=credentialed),
            reraise=True,
        )
        try:
            result: FetchResult = await retrying(
                self._attempt,
                url,
                auth=auth,
                timeout=timeout,
                check_robots=check_robots,
                started=started,
            )
        except _RetryableError as exc:
            if exc.rate_limited:
                msg = f"HTTP {exc.status} from {url}: still rate limited after {retries} retries"
                raise FetchError("rate_limited", msg, status=exc.status) from None
            msg = f"HTTP {exc.status} from {url} after {retries} retries"
            raise FetchError("http_error", msg, status=exc.status) from None
        except (httpx.TimeoutException, TimeoutError) as exc:
            msg = f"{_describe(exc, credentialed=credentialed)} for {url}"
            raise FetchError("timeout", msg) from None
        except (httpx.RequestError, httpx.InvalidURL) as exc:
            msg = f"{_describe(exc, credentialed=credentialed)} for {url}"
            raise FetchError("network_error", msg) from None
        log.debug(
            "fetch",
            url=url,
            status=result.status,
            from_cache=result.from_cache,
            elapsed_ms=result.elapsed_ms,
        )
        return result

    def _wait(self, state: RetryCallState) -> float:
        """The server's wait for a rate limit when it gave one, else exponential backoff."""
        error = state.outcome.exception() if state.outcome is not None else None
        if isinstance(error, _RetryableError) and error.wait is not None:
            return error.wait
        return self._backoff(state)

    def _log_wait(self, state: RetryCallState, url: str, *, credentialed: bool) -> None:
        error = state.outcome.exception() if state.outcome is not None else None
        wait = state.next_action.sleep if state.next_action is not None else 0.0
        if isinstance(error, _RetryableError) and error.rate_limited:
            log.warning("rate_limit_wait", url=url, status=error.status, wait_seconds=wait)
        elif isinstance(error, _RetryableError):
            log.info(
                "retry",
                url=url,
                status=error.status,
                attempt=state.attempt_number,
                wait_seconds=wait,
            )
        else:
            log.info(
                "retry",
                url=url,
                error=None if error is None else _describe(error, credentialed=credentialed),
                attempt=state.attempt_number,
                wait_seconds=wait,
            )

    async def _attempt(
        self,
        url: str,
        *,
        auth: tuple[str, str] | None,
        timeout: float,
        check_robots: bool,
        started: float,
    ) -> FetchResult:
        """One try: send and follow redirects up to the cap, then read the body."""
        request = self._client.build_request(
            "GET",
            url,
            headers=dict([auth]) if auth is not None else None,
            timeout=timeout,
            extensions={CREDENTIALED: True} if auth is not None else None,
        )
        origin = request.url
        for _ in range(self._settings.max_redirects + 1):
            if check_robots:
                await self._check_robots(request.url)
            await self.limiter(request.url.host).acquire()
            # A deadline per hop as well as httpx's per-operation timeouts: hishel drops the
            # request's timeout on its way to the network, and a body that trickles in slowly
            # would otherwise never time out.
            with anyio.fail_after(timeout):
                response = await self._client.send(request, stream=True)
                try:
                    if response.next_request is None:
                        return await self._read(url, request.url, response, started)
                    redirect = response.next_request
                finally:
                    await response.aclose()
            if auth is not None and not _same_origin(origin, redirect.url):
                redirect.headers.pop(auth[0], None)
            request = redirect
        msg = f"more than {self._settings.max_redirects} redirects (max_redirects) from {url}"
        raise FetchError("http_error", msg)

    async def _read(
        self, url: str, final_url: httpx.URL, response: httpx.Response, started: float
    ) -> FetchResult:
        status = response.status_code
        if _is_rate_limited(response):
            wait = _rate_limit_wait(response.headers, time.time())
            if wait is not None and wait > self._settings.max_wait_seconds:
                msg = (
                    f"HTTP {status} from {final_url}: the server asks for a {wait:.0f} s wait, "
                    f"longer than max_wait_seconds ({self._settings.max_wait_seconds})"
                )
                raise FetchError("rate_limited", msg, status=status)
            raise _RetryableError(status, rate_limited=True, wait=wait)
        if httpx.codes.is_server_error(status):
            raise _RetryableError(status, rate_limited=False)
        if not response.is_success:
            raise FetchError("http_error", f"HTTP {status} from {final_url}", status=status)
        content = await _read_capped(response, self._settings.max_response_bytes)
        return FetchResult(
            url=url,
            final_url=str(final_url),
            status=status,
            headers=httpx.Headers(response.headers),
            content=content,
            from_cache=bool(response.extensions.get("hishel_from_cache", False)),
            elapsed_ms=round((time.perf_counter() - started) * 1000),
        )

    async def _check_robots(self, url: httpx.URL) -> None:
        robots_url = str(url.copy_with(path=ROBOTS_PATH, query=None, fragment=None))
        async with self._robots_locks.setdefault(robots_url, anyio.Lock()):
            rules = self._robots.get(robots_url)
            if rules is None:
                rules = self._robots[robots_url] = await self._fetch_robots(robots_url)
        if not rules.can_fetch(str(url), self._product_token):
            log.info("robots_disallowed", url=str(url))
            msg = f"robots.txt disallows {url} for {self._product_token}"
            raise FetchError("robots_disallowed", msg)

    async def _fetch_robots(self, robots_url: str) -> Protego:
        """The host's rules (RFC 9309 §2.3.1): a 4xx means none; a 5xx or no answer, disallow all.

        A rate limit is not an answer about the rules, so it fails the source as rate_limited.
        """
        try:
            result = await self._fetch(
                robots_url,
                auth=None,
                timeout=self._settings.timeout_seconds,
                retries=self._settings.retries,
                check_robots=False,
            )
        except FetchError as exc:
            if exc.reason == "rate_limited":
                raise
            if exc.status is not None and httpx.codes.is_client_error(exc.status):
                return Protego.parse("")
            return Protego.parse(DISALLOW_ALL)
        return Protego.parse(result.content.decode("utf-8", errors="replace"))
