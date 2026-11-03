"""Small, polite HTTP client built on the standard library only.

Why stdlib only: the Skill has to run in places where nothing can be installed
(a claude.ai sandbox, a locked-down laptop). urllib is always there.

Polite means:
- a User-Agent that names the tool and a contact URL (set LEAD_COLLECTOR_CONTACT)
- a minimum gap between two requests to the same host
- a hard timeout and a size cap on every response
- 429 / 503 / 504 answers are retried a few times, honouring Retry-After
"""
from __future__ import annotations

import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

DEFAULT_CONTACT = "https://github.com/ParishSynthMind/claude-skill-local-lead-collector"
RETRY_STATUSES = {429, 502, 503, 504}


def user_agent() -> str:
    contact = os.environ.get("LEAD_COLLECTOR_CONTACT", DEFAULT_CONTACT)
    return f"local-lead-collector/1.0 (+{contact})"


@dataclass
class Response:
    url: str
    status: int
    content_type: str
    body: bytes

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class FetchError(Exception):
    pass


@dataclass
class PoliteClient:
    """HTTP client with a per-host delay. `opener` can be swapped in tests."""

    min_delay: float = 2.0
    timeout: float = 20.0
    max_bytes: int = 2_000_000
    max_retries: int = 3
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    opener: Optional[Callable[..., object]] = None
    _last_hit: Dict[str, float] = field(default_factory=dict)

    def _wait_for_host(self, host: str, min_delay: float) -> None:
        last = self._last_hit.get(host)
        if last is not None:
            gap = self.clock() - last
            if gap < min_delay:
                self.sleep(min_delay - gap)
        self._last_hit[host] = self.clock()

    def request(
        self,
        url: str,
        data: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
        min_delay: Optional[float] = None,
        timeout: Optional[float] = None,
    ) -> Response:
        host = urllib.parse.urlsplit(url).netloc.lower()
        hdrs = {"User-Agent": user_agent(), "Accept-Language": "en"}
        hdrs.update(headers or {})
        open_fn = self.opener or urllib.request.urlopen
        attempt = 0
        while True:
            self._wait_for_host(host, self.min_delay if min_delay is None else min_delay)
            req = urllib.request.Request(url, data=data, headers=hdrs)
            try:
                with open_fn(req, timeout=timeout or self.timeout) as resp:
                    body = resp.read(self.max_bytes + 1)
                    if len(body) > self.max_bytes:
                        raise FetchError(f"response from {host} is larger than {self.max_bytes} bytes")
                    return Response(
                        url=resp.geturl(),
                        status=getattr(resp, "status", 200),
                        content_type=resp.headers.get("Content-Type", "") or "",
                        body=body,
                    )
            except urllib.error.HTTPError as exc:
                if exc.code in RETRY_STATUSES and attempt < self.max_retries:
                    attempt += 1
                    self.sleep(_retry_after(exc, attempt))
                    continue
                raise FetchError(f"HTTP {exc.code} from {host}") from exc
            except urllib.error.URLError as exc:
                if attempt < self.max_retries:
                    attempt += 1
                    self.sleep(5.0 * attempt)
                    continue
                raise FetchError(f"could not reach {host}: {exc.reason}") from exc


def _retry_after(exc: urllib.error.HTTPError, attempt: int) -> float:
    value = exc.headers.get("Retry-After") if exc.headers else None
    if value and value.strip().isdigit():
        return min(float(value.strip()), 120.0)
    return min(10.0 * attempt, 60.0)
