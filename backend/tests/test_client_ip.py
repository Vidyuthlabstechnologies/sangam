"""Rate limits key on an address the client cannot forge."""
from starlette.requests import Request

from app.config import settings
from app.core.middleware import client_ip


def _request(xff: str | None, peer: str = "10.0.0.9") -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


def test_default_uses_the_socket_peer(monkeypatch):
    monkeypatch.setattr(settings, "client_ip_forwarded_hop", 0)
    assert client_ip(_request("1.1.1.1, 2.2.2.2")) == "10.0.0.9"


def test_hop_ignores_addresses_the_client_prepended(monkeypatch):
    monkeypatch.setattr(settings, "client_ip_forwarded_hop", 1)
    assert client_ip(_request("6.6.6.6, 203.0.113.7")) == "203.0.113.7"
    assert client_ip(_request("203.0.113.7")) == "203.0.113.7"


def test_hop_falls_back_when_the_header_is_short(monkeypatch):
    monkeypatch.setattr(settings, "client_ip_forwarded_hop", 2)
    assert client_ip(_request("203.0.113.7")) == "10.0.0.9"
    assert client_ip(_request(None)) == "10.0.0.9"
