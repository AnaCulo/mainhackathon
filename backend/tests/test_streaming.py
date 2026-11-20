import json
from uuid import uuid4

import pytest

from app.config import MODEL

from .doubles import BACKEND, CONTROL, VOICE


def body(sid, *texts):
    return {
        "model": MODEL,
        "stream": True,
        "elevenlabs_extra_body": {"session_id": str(sid)},
        "messages": [{"role": "user", "content": t} for t in texts],
    }


def test_session(setup):
    client, double, _db = setup
    sid = uuid4()
    endpoint = "/v1/chat/completions"
    first = client.post(endpoint, json=body(sid, CONTROL), headers=VOICE)
    assert first.status_code == 200, first.text
    assert first.headers["content-type"].startswith("text/event-stream")
    parts = first.text.strip().split("\n\n")
    assert parts[-1] == "data: [DONE]"
    chunk = json.loads(parts[0][6:])
    assert chunk["object"] == "chat.completion.chunk"
    assert chunk["choices"][0]["delta"]["content"].endswith("?")
    second = client.post(endpoint, json=body(sid, CONTROL, "Yesterday."), headers=VOICE)
    assert second.headers["X-Session-Revision"] == "2" and not double.deliveries
    assert (
        client.post(endpoint, json=body(sid, "different"), headers=VOICE).status_code
        == 409
    )
    url = f"/voice/sessions/{sid}/finalize"
    assert (
        client.post(
            url, json={"confirmed": False, "revision": 2}, headers=VOICE
        ).status_code
        == 422
    )
    assert (
        client.post(
            url, json={"confirmed": True, "revision": 1}, headers=VOICE
        ).status_code
        == 409
    )
    case = client.post(
        url, json={"confirmed": True, "revision": 2}, headers=VOICE
    ).json()
    assert case["category"] == "safety" and double.deliveries == [case]
    assert (
        client.post(url, json={"confirmed": True, "revision": 2}, headers=VOICE).json()
        == case
    )
    assert len(double.deliveries) == 1


@pytest.mark.parametrize("mode", ["truncated", "restored", "tools", "model", "auth"])
def test_bad_stream(setup, mode):
    client, double, _ = setup
    data = body(uuid4(), CONTROL)
    if mode == "tools":
        data["tools"] = [{"type": "function"}]
    if mode == "model":
        data["model"] = "auto"
    if mode == "restored":
        double.answer = "Anna Virtanen"
    double.fault = mode
    r = client.post(
        "/v1/chat/completions", json=data, headers=BACKEND if mode == "auth" else VOICE
    )
    assert (
        r.status_code >= 400
        and "Anna Virtanen" not in r.text
        and "[DONE]" not in r.text
    )
    if mode in {"tools", "model", "auth"}:
        assert not double.requests


def test_held_turn_disables_finalization(setup):
    client, double, _ = setup
    sid = uuid4()
    url = "/v1/chat/completions"
    assert client.post(url, json=body(sid, CONTROL), headers=VOICE).status_code == 200
    held = client.post(
        url, json=body(sid, CONTROL, "My diagnosis is private."), headers=VOICE
    )
    assert held.status_code == 422
    status = client.get(f"/voice/sessions/{sid}", headers=VOICE).json()
    assert status["state"] == "held_for_review"
    final = client.post(
        f"/voice/sessions/{sid}/finalize",
        json={"confirmed": True, "revision": status["revision"]},
        headers=VOICE,
    )
    assert final.status_code == 409 and double.deliveries == []


@pytest.mark.asyncio
async def test_disconnect_cancels_inflight_gateway_call():
    import asyncio

    from app.routes.chat import while_connected
    from app.security import Stop

    cancelled = asyncio.Event()

    class Gone:
        async def is_disconnected(self):
            return True

    async def waiting():
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with pytest.raises(Stop, match="client_disconnected"):
        await while_connected(Gone(), waiting())
    assert cancelled.is_set()


@pytest.mark.parametrize("fault,status", [("trailing_usage", 200), ("trailing_content", 502)])
def test_trailing_chunk_after_stop(setup, fault, status):
    # Live OpenRouter streams send one empty usage chunk after the stop chunk.
    client, double, _ = setup
    double.fault = fault
    r = client.post("/v1/chat/completions", json=body(str(uuid4()), "A warehouse emergency exit was blocked."), headers=VOICE)
    assert r.status_code == status


def test_elevenlabs_compatibility_fields_accepted(setup):
    # Observed live (20 Nov): ElevenLabs' Custom LLM caller adds these two fields.
    client, double, _ = setup
    data = body(str(uuid4()), "A warehouse emergency exit was blocked.")
    data["max_completion_tokens"] = 5000
    data["stream_options"] = {"include_usage": True}
    r = client.post("/v1/chat/completions", json=data, headers=VOICE)
    assert r.status_code == 200 and "[DONE]" in r.text
    data["surprise"] = 1  # anything else is still rejected
    assert client.post("/v1/chat/completions", json=data, headers=VOICE).status_code == 422


def test_reasoning_fields_in_stream_are_discarded(setup):
    # Observed live (20 Nov): OpenRouter sometimes streams reasoning alongside content.
    client, double, _ = setup
    double.fault = "reasoning"
    r = client.post("/v1/chat/completions", json=body(str(uuid4()), "A warehouse emergency exit was blocked."), headers=VOICE)
    assert r.status_code == 200 and "internal" not in r.text and "[DONE]" in r.text
