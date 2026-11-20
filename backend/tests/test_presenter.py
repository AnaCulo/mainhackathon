"""Exercise the form registered by the launcher's ASGI factory, including the hosted contract."""
import re

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import HOSTED, MODEL
from app.demo import create_demo
from .doubles import Double


@pytest.fixture
def presenter(tmp_path, monkeypatch):
    password = "synthetic-presenter-login"
    monkeypatch.setenv("HANDLER_REF", "handler")
    monkeypatch.setenv("HANDLER_PASSWORD", password)
    upstream = Double(tmp_path)
    app = create_demo(upstream.settings, httpx.MockTransport(upstream))
    with TestClient(app) as client:
        client.auth = ('handler', password)
        yield client, upstream, app.state.db


def post_form(client, text):
    page = client.get("/demo")
    assert page.status_code == 200 and 'action="/demo"' in page.text
    fields = dict(re.findall('name="(key|ticket)" value="([^"]+)"', page.text))
    return client.post("/demo", data={**fields, "text": text})


def test_presenter_requires_a_governed_completion(presenter):
    client, upstream, db = presenter
    text = "Ivo Laan, my team lead, allegedly approved a purchase without the required second sign-off."
    response = post_form(client, text)
    assert response.status_code == 200, response.text
    case, = upstream.deliveries
    assert case["persons"] == ["PERSON_01"] and case["case_id"] in response.text
    assert case["brief"]["facts"] and case["decisions"][-1]["action"] == "HUMAN_ONLY"
    gateway = [(url.removeprefix(HOSTED), body, h) for url, body, h in upstream.requests if url.startswith(HOSTED)]
    assert [path for path, _, _ in gateway] == ["/models", "/policy", "/policy/test", "/policy/test", "/chat/completions"]
    assert all(h["X-Request-ID"] == response.headers["X-Request-ID"] for _, _, h in gateway)
    assert gateway[-1][1]["model"] == MODEL
    assert "Ivo" not in str(gateway) and "#P01" in str(gateway[-1][1]["messages"])
    with db.connection() as con:
        row = con.execute("SELECT original_identity FROM identity_mappings WHERE case_id=?", (case["case_id"],)).fetchone()
        assert db.unseal(row[0]) == "Ivo Laan"

    # A second, freshly issued form cannot replay the first case when the gateway is down.
    before = len(upstream.requests)
    upstream.fault = "timeout"
    failed = post_form(client, "A warehouse emergency exit was blocked with boxes.")
    assert failed.status_code == 503 and "Submission failed" in failed.text
    assert "gateway_timeout" in failed.text and case["case_id"] not in failed.text
    assert [url for url, _, _ in upstream.requests[before:]] == [HOSTED + "/models"]
    assert upstream.deliveries == [case]


def test_presenter_blocks_before_hosted_preview(presenter):
    client, upstream, _ = presenter
    result = post_form(client, "The medical evidence mentions two invoices.")
    assert result.status_code == 422 and "restricted_material" in result.text
    assert not upstream.requests


def test_presenter_does_not_confirm_an_unreceived_case(presenter):
    client, upstream, _ = presenter
    upstream.fault = "webhook"
    result = post_form(client, "A warehouse emergency exit was blocked with boxes.")
    assert result.status_code == 502 and "handoff_unconfirmed" in result.text
    assert "Case ready" not in result.text
