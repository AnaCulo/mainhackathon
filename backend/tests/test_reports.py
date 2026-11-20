import json
from uuid import uuid4

from .doubles import BACKEND, CONTROL


def test_control(setup, submit):
    client, double, db = setup
    r = submit(CONTROL)
    assert r.status_code == 200, r.text
    case = r.json()
    assert set(case) == {
        "case_id",
        "reporter",
        "category",
        "summary",
        "persons",
        "received_at",
        "decisions",
        "brane_status",
        "brief",
    }
    assert case["category"] == "safety" and case["persons"] == []
    assert (
        case["summary"] == "The reporter describes an emergency exit blocked by boxes."
    )
    assert case["decisions"] == [
        {"policy": "P5", "action": "ALLOW", "count": None},
        {"policy": "P6", "action": "HUMAN_ONLY", "count": None},
    ]
    assert double.deliveries == [case]
    with db.connection() as con:
        row = con.execute("SELECT * FROM cases").fetchone()
        assert row["status"] == "awaiting_human_review"
        detail = db.unseal(row["extraction"])
        assert (
            detail["approximate_time"] == "unknown"
            and detail["location"] == "warehouse"
        )
        assert (
            con.execute(
                "SELECT count(*) FROM audit_events WHERE request_id=? AND source='gateway'",
                (r.headers["x-request-id"],),
            ).fetchone()[0]
            >= 2
        )
    assert client.get("/health").json()["ready"]


def test_replay(setup):
    client, double, _ = setup
    headers = {**BACKEND, "Idempotency-Key": str(uuid4())}
    first = client.post("/reports", json={"text": CONTROL}, headers=headers)
    again = client.post("/reports", json={"text": CONTROL}, headers=headers)
    assert first.json() == again.json() and len(double.deliveries) == 1
    assert (
        client.post("/reports", json={"text": "different"}, headers=headers).status_code
        == 409
    )


def test_grounded_summary(setup, submit):
    _, double, db = setup
    from app.policies import screen

    data = screen(CONTROL, []).fields
    double.answer = json.dumps({**data, "summary": "Only the night manager knows."})
    assert submit(CONTROL).status_code == 502
    assert not double.deliveries
    with db.connection() as con:
        assert (
            con.execute("SELECT status FROM cases").fetchone()[0] == "held_for_review"
        )


def test_in_flight_reservation(setup):
    import pytest

    from app.security import Stop

    _, _, db = setup
    key = str(uuid4())
    cid, received, _ = db.reserve(key, {"text": CONTROL}, "first")
    with pytest.raises(Stop, match="request_in_progress"):
        db.reserve(key, {"text": CONTROL}, "second")
    db.hold(cid, "first", "gateway_unverifiable")
    assert db.reserve(key, {"text": CONTROL}, "second") == (cid, received, None)


def test_model_can_prioritize_multiple_grounded_observations(setup, submit):
    from app.policies import screen

    text = "A safety concern was raised alongside harassment."
    screened = screen(text, [])
    selected = list(reversed(screened.observations))
    setup[1].answer = json.dumps(
        {
            **screened.fields,
            "summary": " ".join(s for _, s in selected),
            "category": selected[0][0],
        }
    )
    assert submit(text).json()["category"] == "harassment"


def test_unknown_narrative_held_before_egress(setup, submit):
    r = submit("The person from the tiny satellite office knows more.")
    assert r.status_code == 422 and r.json()["error"] == "local_review_required"
    assert not setup[1].requests


def test_invoice_discrepancy_brief_has_fact_timeline_evidence(submit):
    # Manual-benchmark fixture: the handler brief must carry all four fields.
    r = submit(
        "Two invoice totals differ. The discrepancy appeared on Monday. The ledger has both entries."
    )
    assert r.status_code == 200
    case = r.json()
    assert case["brief"] == {
        "facts": ["The report describes a discrepancy between invoice totals."],
        "timeline": ["Reported time: Monday."],
        "evidence": ["Ledger entries (original held locally)."],
    }
    assert " ".join(case["brief"]["facts"]) == case["summary"]
