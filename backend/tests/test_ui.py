"""Local demo website: only on loopback, and it reuses the protected routes."""
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app

from .doubles import Double


@pytest.fixture
def local(tmp_path):
    double = Double(tmp_path)
    app = create_app(replace(double.settings, environment="development"), httpx.MockTransport(double))
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000)) as client:
        yield client, double


def test_page_and_api_hidden_off_loopback(tmp_path):
    double = Double(tmp_path)
    app = create_app(replace(double.settings, environment="development"), httpx.MockTransport(double))
    with TestClient(app) as remote:  # client "testclient", Host "testserver"
        assert remote.get("/").status_code == 404
        assert remote.get("/ui/new-session").status_code == 404


def test_page_hidden_through_tunnel_or_proxy(local):
    client, _ = local
    assert client.get("/", headers={"host": "abc.trycloudflare.com"}).status_code == 404
    assert client.get("/", headers={"cf-ray": "x"}).status_code == 404
    assert client.get("/", headers={"x-forwarded-for": "203.0.113.9"}).status_code == 404


def test_page_hidden_outside_development(tmp_path):
    double = Double(tmp_path)  # environment "test"
    app = create_app(double.settings, httpx.MockTransport(double))
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000)) as client:
        assert client.get("/").status_code == 404


def test_typed_conversation_then_submit(local):
    client, double = local
    assert "Anonymous Whistleblower Intake Hotline" in client.get("/").text
    sid = client.get("/ui/new-session").json()["session_id"]
    r = client.post("/ui/turn", json={"session_id": sid, "history": ["A warehouse emergency exit was blocked."]})
    body = r.json()
    assert r.status_code == 200 and body["status"] == 200 and body["question"]
    actions = [e["action"] for e in body["trace"]]
    assert "preview_clean" in actions and "outbound_messages" in actions and "ALLOW" in actions
    outbound = next(e for e in body["trace"] if e["action"] == "outbound_messages")["meta"]["messages"]
    assert outbound and all("warehouse emergency exit was blocked" not in m for m in outbound)
    s = client.post("/ui/submit", json={"session_id": sid}).json()
    assert s["status"] == 200 and s["case"]["case_id"].startswith("WB-")
    assert s["delivery"] == "delivered" and double.deliveries


def test_held_turn_shows_reason_and_sends_nothing(local):
    client, double = local
    sid = str(uuid4())
    r = client.post("/ui/turn", json={"session_id": sid, "history": ["My medication was discussed at a safety inspection."]}).json()
    assert r["status"] == 200 and r["held_case_id"] == double.deliveries[0]["case_id"]
    assert not [u for u, _, _ in double.requests if u.endswith("/chat/completions")]


def test_voice_clips_only_for_fixed_lines(local):
    client, _ = local
    assert client.get("/ui/voice/what").status_code == 200
    assert client.get("/ui/voice/disclosure").status_code == 200
    assert client.get("/ui/voice/..%2F..%2F.env").status_code == 404
    assert client.get("/ui/voice/anything").status_code == 404
