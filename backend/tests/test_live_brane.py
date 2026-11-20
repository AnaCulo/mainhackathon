"""Opt in only after reviewing the tenant. No webhook calls or production data."""

import os
from uuid import uuid4

import httpx
import pytest

from app.agent import parse_case, report_messages
from app.brane_client import BraneClient
from app.config import Settings
from app.policies import screen

from .doubles import CONTROL


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_BRANE") != "1", reason="requires approved live tenant"
)
@pytest.mark.asyncio
async def test_live_governed_control():
    settings = Settings.load()
    rid = str(uuid4())
    events = []

    def audit(source, action, **kwargs):
        events.append((source, action, kwargs))

    async with httpx.AsyncClient(trust_env=False) as http:
        adapter = BraneClient(settings, http)
        assert adapter.configured, (
            "Configure approved tenant and pin its reviewed policy"
        )
        safe = screen(CONTROL, [])
        result = await adapter.complete(report_messages(safe), rid, audit)
        assert parse_case(result, safe).category == "safety"
    assert any(
        source == "gateway" and action == "ALLOW" for source, action, _ in events
    )
    print("Governed synthetic control request ID", rid)


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_BRANE") != "1", reason="requires approved live tenant"
)
@pytest.mark.asyncio
async def test_live_nonexecuting_repeated_contact_preview():
    """Separate tenant calibration with a fixed synthetic sentinel. No completion."""
    from app.brane_client import policy_digest
    from app.security import Stop

    settings = Settings.load()
    rid = str(uuid4())
    headers = {
        "Authorization": "Bearer " + settings.api_key,
        "X-Request-ID": rid,
        "User-Agent": "hotline-intake-live-test/1.0",
    }
    contact = "synthetic-hotline@example.invalid"
    prompt = f"The demo mailbox is {contact}. The same demo address is {contact}."
    async with httpx.AsyncClient(trust_env=False) as http:
        adapter = BraneClient(settings, http)
        assert adapter.configured
        policy = await adapter._json("GET", "/policy", headers)
        assert policy_digest(policy) == settings.policy_digest
        try:
            preview = await adapter._json(
                "POST",
                "/policy/test",
                headers,
                {"prompt": prompt, "executeCompletion": False},
            )
        except Stop as exc:
            assert exc.reason == "gateway_refused"
            return
        route = preview["decision"]["route"]
        outgoing = preview["outgoingCloudPayloadPreview"]
        if route == "cloud":
            assert (
                isinstance(outgoing, str)
                and outgoing.strip()
                and contact not in outgoing.casefold()
            )
            assert any(
                hit.get("label") == "EMAIL" and hit.get("action") == "placeholder"
                for hit in preview["detectedCategories"]
            )
        else:
            assert route in {"local", "refuse"} and not outgoing
    print("Non-executing synthetic contact preview ID", rid)
