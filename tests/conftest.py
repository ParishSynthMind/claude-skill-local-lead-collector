import email.message
import io
import json
import os
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "local-lead-collector"
FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(SKILL / "scripts"))


class FakeResponse:
    def __init__(self, url, body, content_type="text/html; charset=utf-8", status=200):
        self._url, self._body, self.status = url, body, status
        self.headers = email.message.Message()
        self.headers["Content-Type"] = content_type

    def read(self, n=-1):
        return self._body if n < 0 else self._body[:n]

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeWeb:
    """Maps URL prefixes to responses. A value can be bytes/str, (status, body), or a callable."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, req, timeout=None):
        url = req.full_url
        self.calls.append(url)
        for prefix, value in self.routes.items():
            if url.startswith(prefix):
                if callable(value):
                    value = value(req)
                if isinstance(value, tuple) and isinstance(value[0], int):
                    status, body = value[0], value[1]
                    headers = email.message.Message()
                    for k, v in (value[2] if len(value) > 2 else {}).items():
                        headers[k] = v
                    if status >= 400:
                        raise urllib.error.HTTPError(url, status, "err", headers, io.BytesIO(b""))
                    value = body
                if isinstance(value, Exception):
                    raise value
                body = value.encode() if isinstance(value, str) else value
                ctype = "application/json" if body[:1] in (b"{", b"[") else "text/html; charset=utf-8"
                if url.endswith("robots.txt"):
                    ctype = "text/plain"
                return FakeResponse(url, body, ctype)
        raise urllib.error.HTTPError(url, 404, "not found", email.message.Message(), io.BytesIO(b""))


def make_client(routes, **kw):
    from polite_http import PoliteClient

    web = FakeWeb(routes)
    client = PoliteClient(min_delay=0, sleep=lambda s: None, opener=web, **kw)
    return client, web


@pytest.fixture
def fixture_json():
    def load(name):
        return json.loads((FIXTURES / name).read_text())
    return load


@pytest.fixture
def fixture_text():
    return lambda name: (FIXTURES / name).read_text()
