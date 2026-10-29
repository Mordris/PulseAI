"""The one HTTP client every collector request goes through, robots.txt and sitemaps included.

The rules that apply to every request live here, so collectors only call `Fetcher.get`:
HTTP caching, per-host rate limits, retries and rate-limit waits, robots.txt (RFC 9309), size
and redirect caps, and auth headers read from env vars, whose values never reach logs,
exception text, or the cache.
"""

from __future__ import annotations

import time
import zlib
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC
from email.utils import parsedate_to_datetime
from http import HTTPStatus
from http.cookiejar import CookieJar, DefaultCookiePolicy
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
# The content codings the body reader decodes; the request asks for these and nothing else.
DECODED_CODINGS = ("gzip", "x-gzip", "deflate")
ACCEPT_ENCODING = "gzip, deflate"
# 32 added to wbits makes zlib read either a gzip or a zlib header (RFC 9110 §8.4.1.2-3).
GZIP_OR_ZLIB_WBITS = zlib.MAX_WBITS | 32

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


# The network responses sent for the cache request in progress (one task, one request).
_SENT: ContextVar[list[httpx.Response] | None] = ContextVar("pulseai_sent", default=None)


async def _close_all(responses: list[httpx.Response]) -> None:
    with anyio.CancelScope(shield=True):  # runs during a timeout's cancellation too
        for response in responses:
            await response.aclose()


class _NoteSent(httpx.AsyncBaseTransport):
    """Sits under hishel and notes each network response, so `_Cache` can close it."""

    def __init__(self, network: httpx.AsyncBaseTransport) -> None:
        self._network = network

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self._network.handle_async_request(request)
        sent = _SENT.get()
        if sent is not None:
            sent.append(response)
        return response

    async def aclose(self) -> None:
        await self._network.aclose()


class _ClosingStream(httpx.AsyncByteStream):
    """hishel's response body, whose close also closes the network responses behind it."""

    def __init__(self, stream: httpx.AsyncByteStream, sent: list[httpx.Response]) -> None:
        self._stream = stream
        self._sent = sent

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in self._stream:
            yield chunk

    async def aclose(self) -> None:
        try:
            await self._stream.aclose()
        finally:
            await _close_all(self._sent)


class _Cache(httpx.AsyncBaseTransport):
    """hishel's shared cache (RFC 9111), with two fixes around it.

    - Requests that carry credentials go straight to the network. hishel's rule for
      authorized requests (§3.5) covers only the Authorization header, and hishel writes request
      headers into each stored entry. So a response to a credentialed request is never stored or
      reused, whatever the header is called, and the credential stays off disk.
    - Closing a response closes the network response behind it. hishel's response body ignores
      close, and httpx releases a pooled connection only when the body is read to the end, so
      every response left unread (a redirect, a 4xx, a retried 5xx, a body over the cap) would
      otherwise keep its connection until the pool runs dry.
    """

    def __init__(self, network: httpx.AsyncBaseTransport, cache_path: Path) -> None:
        self._network = network
        self._cache = hishel.httpx.AsyncCacheTransport(
            next_transport=_NoteSent(network),
            storage=hishel.AsyncSqliteStorage(database_path=cache_path / CACHE_FILE),
            policy=hishel.SpecificationPolicy(cache_options=hishel.CacheOptions(shared=True)),
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.extensions.get(CREDENTIALED):
            return await self._network.handle_async_request(request)
        sent: list[httpx.Response] = []
        token = _SENT.set(sent)
        try:
            response = await self._cache.handle_async_request(request)
        except BaseException:
            await _close_all(sent)
            raise
        finally:
            _SENT.reset(token)
        stream = response.stream
        if not isinstance(stream, httpx.AsyncByteStream):  # pragma: no cover - hishel's is async
            await _close_all(sent)
            msg = "hishel returned a response without an async body"
            raise TypeError(msg)
        response.stream = _ClosingStream(stream, sent)
        return response

    async def aclose(self) -> None:
        await self._cache.aclose()  # also closes the network transport under it


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


def _is_compressed(headers: httpx.Headers, url: httpx.URL) -> bool:
    """Whether the body has one gzip or deflate coding to undo. Any other coding is refused."""
    listed = (
        raw.strip().lower() for raw in headers.get_list("Content-Encoding", split_commas=True)
    )
    codings = [coding for coding in listed if coding not in ("", "identity")]
    if not codings:
        return False
    if len(codings) > 1:
        msg = f"response from {url} stacks {len(codings)} content codings; only one is decoded"
        raise FetchError("parse_error", msg)
    if codings[0] not in DECODED_CODINGS:
        msg = f"response from {url} uses content coding {codings[0]!r}, which is not decoded"
        raise FetchError("parse_error", msg)
    return True


def _too_large(url: httpx.URL, max_bytes: int) -> FetchError:
    return FetchError(
        "too_large", f"response from {url} is larger than max_response_bytes ({max_bytes})"
    )


async def _read_body(response: httpx.Response, max_bytes: int) -> bytes:
    """The decoded body. Neither the bytes received nor the decoded bytes may pass `max_bytes`.

    The raw body is inflated here, in steps that never produce more than the cap allows. httpx's
    own decoding inflates each network chunk in full before any size check, and undoes stacked
    codings one after another, so a few hundred compressed bytes could take hundreds of MiB.
    """
    url = response.url
    if response.is_stream_consumed:
        # Built in memory from bytes (a mock transport, or a replayed cassette) and already
        # decoded by httpx; nothing came over the network, so only the cap applies.
        if len(response.content) > max_bytes:
            raise _too_large(url, max_bytes)
        return response.content
    compressed = _is_compressed(response.headers, url)
    inflater = zlib.decompressobj(GZIP_OR_ZLIB_WBITS) if compressed else None
    body = bytearray()
    received = 0
    try:
        async for chunk in response.aiter_raw():
            received += len(chunk)
            if received > max_bytes:
                raise _too_large(url, max_bytes)
            if inflater is None:
                body += chunk
            else:
                # Each step may add at most one byte past the cap (max_length 0 would mean no
                # limit, which the loop condition rules out). Data after the end of the
                # compressed stream is still received, so the response and hishel's copy of it
                # complete, but ignored, as httpx does.
                data = chunk
                while data and not inflater.eof and len(body) <= max_bytes:
                    body += inflater.decompress(data, max_bytes + 1 - len(body))
                    data = inflater.unconsumed_tail
            if len(body) > max_bytes:
                raise _too_large(url, max_bytes)
    except zlib.error:
        raise FetchError("parse_error", f"response body from {url} could not be decoded") from None
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
        # Redirects are followed by hand (see _attempt) so each hop gets the robots check and
        # the host's rate limit, and credentials never follow a redirect to another origin.
        # Cookies are refused: one jar for the run would carry a session cookie set for one
        # source's credentials to every other source on that host, and into the cache.
        self._client = httpx.AsyncClient(
            transport=network if cache_path is None else _Cache(network, cache_path),
            headers={"User-Agent": user_agent, "Accept-Encoding": ACCEPT_ENCODING},
            cookies=CookieJar(policy=DefaultCookiePolicy(allowed_domains=[])),
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
        content = await _read_body(response, self._settings.max_response_bytes)
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
