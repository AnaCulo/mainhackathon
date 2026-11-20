import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from .doubles import BACKEND, CONTROL

FIXTURES = json.loads((Path(__file__).resolve().parents[2] / "data/synthetic_reports.json").read_text())["cases"]


@pytest.mark.parametrize("fixture", ["T2", "T5"])
def test_policy_receipt_and_replay(setup, fixture):
    client, double, db = setup
    example = next(x for x in FIXTURES if x["id"] == fixture)
    text = " ".join(filter(None, (example["report"], example["evidence"])))
    headers = {**BACKEND, "Idempotency-Key": str(uuid4())}
    first = client.post("/reports", headers=headers, json={"text": text})
    again = client.post("/reports", headers=headers, json={"text": text})
    assert first.status_code == again.status_code == 202
    assert first.json() == again.json() and first.headers["X-Request-ID"]
    assert not double.gateway_requests and double.single_held_delivery
    receipt, = double.deliveries
    assert first.json() == {**receipt, "message": "Received. A person will review your report."}
    assert UUID(receipt["case_id"][3:]).version == 4
    assert receipt["reporter"] == "REPORTER_01" and receipt["status"] == "held_for_review"
    assert receipt["policy"] in {"P3", "P5"}
    assert receipt["hold_reason"] in {"restricted_material", "local_review_required"}
    assert receipt["decisions"] == [
        {"policy":receipt["policy"], "action":"LOCAL_ONLY" if receipt["policy"] == "P3" else "BLOCK", "count":None},
        {"policy":"P6", "action":"HUMAN_ONLY", "count":None}]
    assert all(s.casefold() not in json.dumps(receipt).casefold() for s in example["must_not_egress"])
    with db.connection() as con:
        row = con.execute("SELECT evidence, received_at FROM cases WHERE case_id=?", (receipt["case_id"],)).fetchone()
        assert receipt["received_at"] == row["received_at"]
        assert db.unseal(row["evidence"])["text"] == text and text.encode() not in db.path.read_bytes()
        assert con.execute("SELECT count(*) FROM audit_events WHERE action='held_registered'").fetchone()[0] == 1


def test_timeout_receipt_is_durable(setup, submit):
    _, double, _ = setup
    double.fault = "timeout"
    response = submit(CONTROL)
    case = response.json()
    assert response.status_code == 503 and case["status"] == "held_unverified"
    assert case["hold_reason"] == "gateway_timeout" and case["case_id"] == double.deliveries[0]["case_id"]
    assert not any(url.endswith("/chat/completions") for url, _, _ in double.gateway_requests)
