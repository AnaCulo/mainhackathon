import httpx
import pytest

from app.agent import REPORT_PROMPT, messages
from app.brane_client import BraneClient
from app.security import Stop

from .doubles import CONTROL, Double


@pytest.mark.parametrize(
    "fault,status,attempt",
    [
        ("timeout", 503, False),
        ("drift", 503, False),
        ("model_missing", 503, False),
        ("refusal", 202, False),
        ("preview", 503, False),
        ("headers", 503, True),
    ],
)
def test_fail_closed(setup, submit, fault, status, attempt):
    _, double, db = setup
    double.fault = fault
    r = submit(CONTROL)
    assert r.status_code == status and CONTROL not in r.text
    assert (
        bool([u for u, _, _ in double.requests if u.endswith("chat/completions")])
        == attempt
    )
    assert double.single_held_delivery
    with db.connection() as con:
        assert con.execute(
            "SELECT count(*) FROM audit_events WHERE policy_id='P5' AND success=0"
        ).fetchone()[0]


@pytest.mark.asyncio
async def test_connection_failure(tmp_path):
    def offline(req):
        raise httpx.ConnectError("untrusted synthetic error detail")

    async with httpx.AsyncClient(transport=httpx.MockTransport(offline)) as http:
        brane = BraneClient(Double(tmp_path).settings, http)
        with pytest.raises(Stop, match="gateway_unverifiable"):
            await brane.complete(
                messages(REPORT_PROMPT, {}), "test", lambda *a, **k: None
            )


@pytest.mark.asyncio
async def test_unconfigured_gateway_never_connects(tmp_path):
    from dataclasses import replace

    double = Double(tmp_path)
    async with httpx.AsyncClient(transport=httpx.MockTransport(double)) as http:
        for config in [
            replace(double.settings, api_key=""),
            replace(double.settings, policy_digest=""),
            replace(double.settings, base="https://example.invalid"),
            replace(double.settings, model="auto"),
        ]:
            with pytest.raises(Stop, match="gateway_not_configured"):
                await BraneClient(config, http).complete(
                    [], "test", lambda *a, **k: None
                )
    assert double.requests == []


@pytest.mark.parametrize("fault", ["combined", "combined_payload"])
def test_combined_preview_stops_before_completion(setup, submit, fault):
    # Each message previews clean alone, the joined conversation does not (live P3a, 20 Nov).
    _, double, _ = setup
    double.fault = fault
    r = submit("A warehouse emergency exit was blocked with boxes.")
    assert r.status_code == 503 and r.json()["hold_reason"] == "preview_not_clean"
    assert not [u for u, _, _ in double.requests if u.endswith("/chat/completions")]
    assert double.single_held_delivery
