import json
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.demo import create_demo
from .doubles import BACKEND, Double
from .test_ui import local


@pytest.mark.parametrize("key,status,policy", [
    ("T1",200,None), ("T2",202,"P3"), ("T3",200,None), ("T4",202,"P4"), ("T5",202,"P3"),
    ("E1",202,"P1"), ("E6",202,"P3"), ("OUTAGE",503,"P5"),
])
def test_fixture_through_reports(local, key, status, policy):
    client, double = local
    fixtures = client.get("/ui/redteam/cases").json()["cases"]
    assert [x["id"] for x in fixtures] == ["T1","T2","T3","T4","T5","E1","E6","OUTAGE"]
    r = client.post("/ui/redteam/run", json={"id":key}).json()
    assert r["status"] == status and r["delivery"] == "delivered"
    assert r["request_id"] and r["handler_url"].endswith(r["case"]["case_id"])
    if policy:
        assert r["case"]["policy"] == policy and not double.gateway_requests
        assert r["completion_attempts"] == 0 and not r["outbound_messages"] and not r["completion_headers"]
        assert double.single_held_delivery
    else:
        assert r["completion_attempts"] == 1 and r["completion_headers"]["X-Brane-Routed-To"] == "cloud"
        sent, = [b for u,b,_ in double.gateway_requests if u.endswith("/chat/completions")]
        assert r["outbound_messages"] == [sent["messages"][1]["content"]]
    if key == "T3":
        assert {"policy":"P2","action":"PROTECT","count":5} in r["case"]["decisions"]
        assert "#P01" in r["outbound_messages"][0] and "Oosterhout" not in json.dumps(r["outbound_messages"])
    if key == "OUTAGE":
        assert r["case"]["hold_reason"] == "gateway_unverifiable"
        assert not client.app.state.gateway_kill
        assert client.post("/ui/redteam/run", json={"id":"T1"}).json()["status"] == 200


def test_run_accepts_only_fixture_ids(local):
    client, double = local
    for body in [{"id":"missing"},{"id":"T1","text":"replacement"}]:
        assert client.post("/ui/redteam/run", json=body).status_code == 422
    assert client.post("/ui/redteam/run", json={"id":"OUTAGE"}, headers={"forwarded":"for=proxy"}).status_code == 404
    assert not double.requests


def test_local_original_requires_presenter_and_direct_loopback(tmp_path, monkeypatch):
    double = Double(tmp_path)
    monkeypatch.setenv("HANDLER_REF", "handler")
    monkeypatch.setenv("HANDLER_PASSWORD", "synthetic-test-login")
    app = create_demo(replace(double.settings, environment="development"), httpx.MockTransport(double))
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1",50000)) as client:
        receipt = client.post("/reports", headers=BACKEND, json={"text":"My medical records contain <example>."}).json()
        path = "/demo/held/" + receipt["case_id"]
        assert client.get(path).status_code == 401
        client.auth = ("handler","synthetic-test-login")
        assert client.get(path,headers={"x-forwarded-host":"example.invalid"}).status_code == 404
        original = client.get(path)
        assert original.status_code == 200 and "&lt;example&gt;" in original.text
        assert "restricted_material (P3)" in original.text
