"""Local demo website: Anonymous Whistleblower Intake Hotline (synthetic).

Two ways to report, both only to this machine:
  * Send messages: typed text -> backend screening -> BRANE -> model -> fixed question.
  * Talk: push-to-talk audio -> local Whisper on this Mac -> text -> same path. Audio is
    deleted after transcription and never leaves the machine.
The agent's spoken questions are pre-generated clips of fixed server-owned text, so no
reporter data reaches any text-to-speech service.

Every UI call goes through the backend's existing protected routes (the same code ElevenLabs
uses), internally and with server-held credentials, then returns that request's audit trail
for the "behind the scenes" panel. The UI only answers on loopback with a local Host header
and never through a tunnel or proxy.
"""
import json
import os
import time
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from ..brane_client import outage_request
from ..config import MODEL
from ..policies import QUESTIONS

STATIC = Path(__file__).resolve().parent.parent / "static"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}
PROXY_HEADERS = ("cf-ray", "cf-connecting-ip", "x-forwarded-for", "x-forwarded-host", "forwarded")
CLIPS = {**{k: v for k, v in QUESTIONS.items()}, "disclosure": None}


def local_only(request: Request):
    host = (request.headers.get("host") or "").rsplit(":", 1)[0].lower()
    client = request.client.host if request.client else ""
    if (
        request.app.state.settings.environment != "development"
        or client not in {"127.0.0.1", "::1"}
        or host not in LOCAL_HOSTS
        or any(h in request.headers for h in PROXY_HEADERS)
    ):
        raise HTTPException(404)


router = APIRouter(dependencies=[Depends(local_only)])


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    history: list[str] = Field(min_length=1, max_length=32)


class Submit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID


def trace(db, request_id):
    with db.connection() as con:
        rows = con.execute(
            "SELECT timestamp, source, policy_id, action, count, model_route, success, metadata "
            "FROM audit_events WHERE request_id=? ORDER BY event_id", (request_id,)).fetchall()
    out = []
    for r in rows:
        meta = json.loads(r["metadata"] or "{}")
        meta.pop("session", None)  # content-free digest, not useful in the panel
        out.append({"t": r["timestamp"], "source": r["source"], "policy": r["policy_id"],
                    "action": r["action"], "count": r["count"], "route": r["model_route"],
                    "ok": bool(r["success"]), "meta": meta})
    return out


def internal(request):
    s = request.app.state.settings
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=request.app),
                             base_url="http://backend.internal",
                             headers={"Authorization": "Bearer " + s.bridge_key}, timeout=90)


@router.get("/", response_class=HTMLResponse)
async def page():
    from ..stt import warm_up  # preload the local speech model in the background

    warm_up()
    return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8"),
                        headers={"Cache-Control": "no-store"})


@router.get("/ui/new-session")
async def new_session():
    return {"session_id": str(uuid4())}


@router.post("/ui/turn")
async def turn(body: Turn, request: Request):
    started = time.perf_counter()
    async with internal(request) as client:
        r = await client.post("/v1/chat/completions", json={
            "model": MODEL, "stream": True,
            "messages": [{"role": "user", "content": t} for t in body.history],
            "elevenlabs_extra_body": {"session_id": str(body.session_id)}})
    rid = r.headers.get("x-request-id")
    question, error = None, None
    if r.status_code == 200:
        for line in r.text.splitlines():
            if line.startswith("data: ") and line[6:] != "[DONE]":
                question = (question or "") + (json.loads(line[6:])["choices"][0]["delta"].get("content") or "")
    else:
        try:
            error = r.json().get("error") or "request_rejected"
        except ValueError:
            error = "request_rejected"
    clip = next((k for k, v in QUESTIONS.items() if v == question), None)
    return {"held_case_id": r.headers.get("x-held-case"), "status": r.status_code, "question": question, "clip": clip, "error": error,
            "request_id": rid, "ms": round((time.perf_counter() - started) * 1000),
            "trace": trace(request.app.state.db, rid) if rid else []}


@router.post("/ui/submit")
async def submit(body: Submit, request: Request):
    sid = str(body.session_id)
    _, revision, frozen, _ = request.app.state.db.session(sid)
    if not revision:
        raise HTTPException(404, "unknown_session")
    started = time.perf_counter()
    async with internal(request) as client:
        r = await client.post(f"/voice/sessions/{sid}/finalize", json={"confirmed": True, "revision": revision})
    rid = r.headers.get("x-request-id")
    case = r.json() if "case_id" in r.json() else None
    delivery = None
    if case:
        with request.app.state.db.connection() as con:
            row = con.execute("SELECT state FROM outbox WHERE case_id=?", (case["case_id"],)).fetchone()
        delivery = row["state"] if row else None
    return {"status": r.status_code, "case": case, "delivery": delivery,
            "error": None if case else (r.json().get("error") if r.headers.get("content-type", "").startswith("application/json") else "rejected"),
            "handler_url": f"http://127.0.0.1:8788/review/{case['case_id']}" if case else None,
            "ms": round((time.perf_counter() - started) * 1000),
            "trace": trace(request.app.state.db, rid) if rid else []}


@router.post("/ui/stt")
async def speech_to_text(request: Request):
    """Push-to-talk audio -> text, on this machine only. The audio is never stored."""
    audio = await request.body()
    if not audio or len(audio) > 10 * 1024 * 1024:
        raise HTTPException(413 if audio else 400, "audio_missing_or_too_large")
    from ..stt import transcribe  # lazy: the text-only demo does not need the model
    return transcribe(audio)


@router.get("/ui/voice/{name}")
async def voice_clip(name: str):
    """Pre-generated agent speech for fixed, server-owned lines only (no reporter data)."""
    if name not in CLIPS:
        raise HTTPException(404)
    for ext, media in (("mp3", "audio/mpeg"), ("m4a", "audio/mp4"), ("wav", "audio/wav")):
        path = STATIC / "voice" / f"{name}.{ext}"
        if path.exists():
            return FileResponse(path, media_type=media)
    raise HTTPException(404)

REDTEAM_IDS = ("T1", "T3", "T4", "T5", "E1", "E6", "OUTAGE")
FIXTURES = Path(__file__).resolve().parents[3] / "data" / "synthetic_reports.json"


def redteam_cases():
    cases = {c["id"]: c for c in json.loads(FIXTURES.read_text(encoding="utf-8"))["cases"]}
    result = []
    for key in REDTEAM_IDS:
        example = cases["T1" if key == "OUTAGE" else key]
        text = example.get("panel_report") or "\n\n".join(filter(None, (example["report"], example["evidence"])))
        result.append({"id": key, "text": text,
                       "highlights": [s for s in example["must_not_egress"] if s in text]})
    return result


class RedteamRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(max_length=8)


@router.get("/ui/redteam/cases")
async def list_redteam():
    return {"cases": redteam_cases()}


@router.post("/ui/redteam/run")
async def run_redteam(body: RedteamRun, request: Request):
    sample = next((c for c in redteam_cases() if c["id"] == body.id), None)
    if sample is None:
        raise HTTPException(422, "unknown_fixture")
    started = time.perf_counter()
    state = request.app.state
    headers = {"Authorization": "Bearer " + state.settings.backend_key, "Idempotency-Key": str(uuid4())}
    async with internal(request) as client:
        async def report():
            return await client.post("/reports", json={"text": sample["text"]}, headers=headers)
        if body.id == "OUTAGE":
            async with state.outage_lock:
                token = outage_request.set(True)
                state.gateway_kill = True
                try:
                    response = await report()
                finally:
                    state.gateway_kill = False
                    outage_request.reset(token)
        else:
            response = await report()
    rid = response.headers["x-request-id"]
    events = trace(state.db, rid)
    case = response.json()
    cid = case.get("case_id")
    with state.db.connection() as con:
        delivery = con.execute("SELECT state FROM outbox WHERE case_id=?", (cid,)).fetchone()
    return {"id": body.id, "status": response.status_code, "case": case, "request_id": rid, "trace": events,
            "outbound_messages": [msg for e in events if e["action"] == "outbound_messages"
                                  for msg in e["meta"]["messages"]],
            "completion_headers": next((e["meta"] for e in events if e["source"] == "gateway"
                                        and e["action"] in {"ALLOW", "headers_rejected"}), {}),
            "completion_attempts": sum(e["action"] == "completion_attempted" for e in events),
            "delivery": delivery[0] if delivery else None,
            "handler_url": f"http://127.0.0.1:{int(os.getenv('DEMO_REGISTER_PORT', '8788'))}/review/{cid}" if cid else None,
            "ms": round((time.perf_counter() - started) * 1000)}
