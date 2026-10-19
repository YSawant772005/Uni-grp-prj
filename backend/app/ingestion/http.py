"""Polite HTTP client for permitted sources.

Provides request timeouts, bounded concurrency, per-host rate limiting,
exponential retry/backoff with ``Retry-After`` support, and conditional
(ETag / Last-Modified) requests used for change detection. A failure on one
document never stops the other independent documents from being processed.
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger("uni.ingestion")

RETRY_STATUSES = {408, 425, 429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    def __init__(self, url: str, reason: str, status: int | None = None, permanent: bool = False):
        super().__init__(f"{url}: {reason}")
        self.url, self.reason, self.status, self.permanent = url, reason, status, permanent


@dataclass
class HttpResult:
    url: str
    status: int
    content: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)
    not_modified: bool = False
    attempts: int = 1

    def text(self, encoding: str | None = None) -> str:
        return self.content.decode(encoding or "utf-8", errors="replace")

    @property
    def etag(self) -> str | None:
        return self.headers.get("etag")

    @property
    def last_modified(self) -> str | None:
        return self.headers.get("last-modified")


class RateLimiter:
    """Thread-safe minimum spacing between requests (requests per second)."""

    def __init__(self, rps: float):
        self._interval = 1.0 / rps if rps > 0 else 0.0
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def acquire(self) -> None:
        if not self._interval:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._next_slot - now
            self._next_slot = max(now, self._next_slot) + self._interval
        if wait > 0:
            time.sleep(wait)


class Fetcher:
    def __init__(self, *, user_agent: str, timeout: float = 60.0, max_retries: int = 3,
                 backoff: float = 1.5, rps: float = 5.0, max_workers: int = 4,
                 verify_tls: bool = True):
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.max_workers = max(1, max_workers)
        self.limiter = RateLimiter(rps)
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout), follow_redirects=True,
            limits=httpx.Limits(max_connections=max(8, self.max_workers * 2),
                                max_keepalive_connections=self.max_workers),
            headers={"User-Agent": user_agent}, verify=verify_tls,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Fetcher":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def get(self, url: str, *, headers: dict[str, str] | None = None,
            etag: str | None = None, last_modified: str | None = None) -> HttpResult:
        """GET with retries. Conditional headers turn an unchanged page into 304."""
        conditional = dict(headers or {})
        if etag:
            conditional["If-None-Match"] = etag
        if last_modified:
            conditional["If-Modified-Since"] = last_modified
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            self.limiter.acquire()
            try:
                response = self._client.get(url, headers=conditional)
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning("fetch error url=%s attempt=%s error=%s", url, attempt, exc)
                self._sleep(attempt, None)
                continue
            if response.status_code == 304:
                return HttpResult(url, 304, b"", dict(response.headers), True, attempt)
            if response.status_code in RETRY_STATUSES:
                last_error = FetchError(url, f"HTTP {response.status_code}",
                                        response.status_code, permanent=False)
                logger.warning("retryable status url=%s status=%s attempt=%s",
                               url, response.status_code, attempt)
                self._sleep(attempt, response.headers.get("retry-after"))
                continue
            if response.status_code >= 400:
                raise FetchError(url, f"HTTP {response.status_code}", response.status_code,
                                 permanent=True)
            return HttpResult(url, response.status_code, response.content,
                              dict(response.headers), False, attempt)
        raise FetchError(url, f"exhausted {self.max_retries} attempts: {last_error}",
                         getattr(last_error, "status", None), permanent=True)

    def _sleep(self, attempt: int, retry_after: str | None) -> None:
        delay = retry_after and retry_after.isdigit() and float(retry_after) or \
            self.backoff * (2 ** (attempt - 1))
        time.sleep(min(delay, 60.0))

    def parallel_map(self, func, items):
        """Bounded-concurrency mapping. Returns ``(item, result, error)`` triples."""
        items = list(items)
        if not items:
            return []
        if self.max_workers == 1:
            return [(i, *self._safe(func, i)) for i in items]

        def run(item):
            result, error = self._safe(func, item)
            return item, result, error

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            return list(pool.map(run, items))

    @staticmethod
    def _safe(func, item):
        try:
            return func(item), None
        except Exception as exc:  # isolated: one bad source document cannot stop the run
            logger.warning("fetch failed item=%s error=%s", item, exc)
            return None, exc