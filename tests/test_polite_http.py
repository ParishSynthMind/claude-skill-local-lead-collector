import pytest

from conftest import FakeWeb
from polite_http import FetchError, PoliteClient, user_agent


class Clock:
    def __init__(self):
        self.t, self.slept = 100.0, []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(round(s, 2))
        self.t += s


def client_with(routes, **kw):
    clock = Clock()
    web = FakeWeb(routes)
    return PoliteClient(sleep=clock.sleep, clock=clock.now, opener=web, **kw), clock, web


def test_waits_between_requests_to_same_host_only():
    c, clock, _ = client_with({"https://a.example": "x", "https://b.example": "y"}, min_delay=2.0)
    c.request("https://a.example/1")
    c.request("https://b.example/1")
    c.request("https://a.example/2")
    assert clock.slept == [2.0]


def test_retry_after_honoured():
    answers = [(429, b"", {"Retry-After": "7"}), "ok"]
    c, clock, web = client_with({"https://a.example": lambda req: answers.pop(0)}, min_delay=0)
    assert c.request("https://a.example/").text() == "ok"
    assert 7.0 in clock.slept and len(web.calls) == 2


def test_size_cap_and_user_agent(monkeypatch):
    c, _, _ = client_with({"https://a.example": b"x" * 50}, min_delay=0, max_bytes=10)
    with pytest.raises(FetchError, match="larger"):
        c.request("https://a.example/")
    monkeypatch.setenv("LEAD_COLLECTOR_CONTACT", "ops@example.org")
    assert user_agent() == "local-lead-collector/1.0 (+ops@example.org)"


def test_404_is_not_retried():
    c, _, web = client_with({}, min_delay=0)
    with pytest.raises(FetchError, match="404"):
        c.request("https://a.example/")
    assert len(web.calls) == 1
