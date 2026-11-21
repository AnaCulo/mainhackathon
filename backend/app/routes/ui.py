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

Robustness: /ui/turn and /ui/submit always answer with a JSON envelope
{status, error, ...} (HTTP 200) whatever happens internally (timeouts, gateway faults,
unexpected exceptions), so the page never has to parse a raw 500. Only content-free reason
codes are returned; the trace is built from an allowlist of audit metadata keys.
"""
import asyncio
import json
import logging
import os
import time
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from ..brane_client import outage_request
from ..config import MODEL
from .. import narrative
from ..fact_extraction import extract_local_facts
from ..locality import is_local, same_origin
from ..models import Text
from ..policies import QUESTIONS, RULES, screen
from ..security import Stop

STATIC = Path(__file__).resolve().parent.parent / "static"
CLIPS = {**{k: v for k, v in QUESTIONS.items()}, "disclosure": None}
MAX_TURNS = 32          # turns per conversation the page may send
MAX_CHARS = 16000       # total characters across the conversation (same as the Chat model)
MAX_AUDIO = 2560 * 1024      # ~80 s of 16 kHz mono WAV; the page stops at 60 s
AUDIO_TYPES = {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"}
STT_SLOTS = 1                 # one transcription at a time: bounded CPU use
STT_WAIT = 20                 # seconds a second request waits for the slot
INTERNAL_TIMEOUT = 85   # seconds; the page aborts at 95 s
SESSION_STATES = ("open", "submitted", "held")
# Audit metadata the panel may show. Everything here is a code, a count, a digest, a header
# value or the already-protected outbound text; anything else is dropped.
TRACE_META = {"matrix_version", "reason", "policy_sha256", "messages_checked",
              "combined_checked", "messages", "operation", "revision", "upstream_request_id",
              "chars", "new_aliases", "state", "distinct_tokens", "instruction_like"}
log = logging.getLogger("uvicorn.error")


def local_only(request: Request):
    # Second layer behind the LocalGuard middleware, with the same predicate.
    if not is_local(request.scope):
        raise HTTPException(404)
    if request.method not in {"GET", "HEAD"} and not same_origin(request.scope):
        raise HTTPException(403, "cross_origin")


router = APIRouter(dependencies=[Depends(local_only)])


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    history: list[Text] = Field(min_length=1, max_length=MAX_TURNS)

    @model_validator(mode="after")
    def bounded(self):
        if sum(len(t) for t in self.history) > MAX_CHARS:
            raise ValueError("Conversation too long")
        return self


class Submit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: UUID
    # The reporter chose to send a report the local grammar cannot draft: finalize then registers
    # it as held for a person (a receipt, nothing sent to a model).
    anyway: StrictBool = False  # a behaviour flag: no "yes" -> True coercion


def handler_url(cid):
    return f"http://127.0.0.1:{int(os.getenv('DEMO_REGISTER_PORT', '8788'))}/review/{cid}"


def session_case_id(db, sid):
    try:
        with db.connection() as con:
            row = con.execute("SELECT case_id FROM sessions WHERE id=?", (sid,)).fetchone()
        return row[0] if row else None
    except Exception:
        log.exception("ui_session_case_failed")
        return None


def trace(db, request_id):
    try:
        with db.connection() as con:
            rows = con.execute(
                "SELECT timestamp, source, policy_id, action, count, model_route, success, metadata "
                "FROM audit_events WHERE request_id=? ORDER BY event_id", (request_id,)).fetchall()
    except Exception:  # the panel is best effort; never fail the request over it
        log.exception("ui_trace_failed")
        return []
    out = []
    for r in rows:
        try:
            meta = json.loads(r["metadata"] or "{}")
        except ValueError:
            meta = {}
        meta = {k: v for k, v in meta.items() if k in TRACE_META or k.startswith("X-Brane-")}
        out.append({"t": r["timestamp"], "source": r["source"], "policy": r["policy_id"],
                    "action": r["action"], "count": r["count"], "route": r["model_route"],
                    "ok": bool(r["success"]), "meta": meta})
    return out


def session_state(db, sid):
    try:
        _, revision, frozen, _ = db.session(sid)
    except Exception:
        log.exception("ui_session_read_failed")
        return None, 0
    return SESSION_STATES[frozen] if frozen in (0, 1, 2) else None, revision


def readiness(turns, summaries=True):
    """Dry run of the local part of finalize (screening + local fact extraction), with no
    BRANE call, no audit and no state change. Returns None when a case can be drafted, else the
    content-free reason the finalize path would refuse with. Callers act only on NEEDS_DETAIL:
    every other refusal is left to finalize, which holds the case properly for a human."""
    text = "\n".join(turns)
    try:
        screened = screen(text, [], allow_incomplete=True)
        try:
            review = extract_local_facts(text, screened)
        except Stop as exc:
            # Mirrors case_service.submit: an unparsed report can still be
            # summarised from a protected copy when it has enough substance.
            if exc.reason != "local_review_required" or not summaries or not narrative.eligible(text):
                raise
            try:
                narrative.protect(screened.protected or text, screened.mentions)
            except Stop:
                # Identifier shapes the redactions cannot settle (an IBAN, a full address):
                # finalize holds it for a person with a receipt. More detail would not help.
                return "held_for_person"
            return None
        if any(RULES[p] == "BLOCK" for p in review.withheld_policies):
            return "restricted_material"
    except Stop as exc:
        return exc.reason
    except Exception:
        log.exception("ui_readiness_failed")
        return "readiness_unknown"
    return None


NEEDS_DETAIL = {"local_review_required", "ambiguous_report"}


def internal(request):
    s = request.app.state.settings
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=request.app),
                             base_url="http://backend.internal",
                             headers={"Authorization": "Bearer " + s.bridge_key},
                             timeout=INTERNAL_TIMEOUT)


def error_code(r):
    try:
        data = r.json()
    except ValueError:
        return "request_rejected"
    return (data.get("error") if isinstance(data, dict) else None) or "request_rejected"


def stream_text(body):
    """Concatenate the content deltas of our own SSE answer; None if it is not well formed."""
    text = None
    for line in body.splitlines():
        if line.startswith("data: ") and line[6:] != "[DONE]":
            try:
                delta = json.loads(line[6:])["choices"][0]["delta"].get("content")
            except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                return None
            text = (text or "") + (delta if isinstance(delta, str) else "")
    return text


@router.get("/", response_class=HTMLResponse)
async def page():
    try:
        from ..stt import warm_up  # preload the local speech model in the background

        warm_up()
    except Exception:
        log.exception("stt_warm_up_failed")
    return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8"),
                        headers={"Cache-Control": "no-store"})


@router.get("/ui/new-session")
async def new_session():
    return {"session_id": str(uuid4())}


@router.post("/ui/turn")
async def turn(body: Turn, request: Request):
    started = time.perf_counter()
    sid = str(body.session_id)
    db = request.app.state.db
    rid, question, error, status, held_case = None, None, None, 500, None
    try:
        async with internal(request) as client:
            r = await client.post("/v1/chat/completions", json={
                "model": MODEL, "stream": True,
                "messages": [{"role": "user", "content": t} for t in body.history],
                "elevenlabs_extra_body": {"session_id": sid}})
        rid, status = r.headers.get("x-request-id"), r.status_code
        held_case = r.headers.get("x-held-case")  # held content is registered, with a receipt
        if status == 200:
            question = stream_text(r.text)
            if not question:
                status, error = 502, "invalid_reply"
        else:
            error = error_code(r)
    except (httpx.TimeoutException, asyncio.TimeoutError):
        status, error = 504, "backend_timeout"
    except Exception:
        log.exception("ui_turn_failed")
        status, error = 500, "internal_error"
    state, _ = session_state(db, sid)
    clip = next((k for k, v in QUESTIONS.items() if v == question), None)
    ready = None
    if status == 200 and state == "open":
        try:
            turns, _, _, _ = db.session(sid)
            ready = readiness(turns, request.app.state.settings.narrative) if turns else "unknown_session"
        except Exception:
            log.exception("ui_readiness_failed")
            ready = "readiness_unknown"
    return {"held_case_id": held_case, "status": status, "question": question if status == 200 else None, "clip": clip,
            "error": error, "held": state == "held", "session_state": state,
            # Only the "needs more detail" refusal is anticipated here; any other local hold is
            # left to finalize, which stores the case for a human handler.
            "submittable": status == 200 and state == "open" and ready not in NEEDS_DETAIL,
            "needs": "more_detail" if ready in NEEDS_DETAIL else None,
            "request_id": rid, "ms": round((time.perf_counter() - started) * 1000),
            "trace": trace(db, rid) if rid else []}


@router.post("/ui/submit")
async def submit(body: Submit, request: Request):
    started = time.perf_counter()
    sid = str(body.session_id)
    db = request.app.state.db
    state, revision = session_state(db, sid)
    envelope = {"status": 404, "case": None, "delivery": None, "error": "unknown_session",
                "handler_url": None, "session_state": state, "request_id": None, "ms": 0,
                "trace": [], "held_case_id": None}
    if not revision:
        return envelope
    if state == "held":
        return {**envelope, "status": 409, "error": "held_for_review",
                "held_case_id": session_case_id(db, sid)}
    if state == "open" and not body.anyway:
        # Finalize freezes the session before drafting. Refuse locally first when the report
        # would be refused anyway, so the reporter can still add detail (nothing is frozen).
        try:
            turns, _, _, _ = db.session(sid)
            ready = readiness(turns, request.app.state.settings.narrative)
        except Exception:
            log.exception("ui_readiness_failed")
            ready = None  # let finalize decide
        if ready in NEEDS_DETAIL:
            return {**envelope, "status": 422, "error": "needs_more_detail",
                    "ms": round((time.perf_counter() - started) * 1000)}
    try:
        async with internal(request) as client:
            r = await client.post(f"/voice/sessions/{sid}/finalize",
                                  json={"confirmed": True, "revision": revision})
        rid = r.headers.get("x-request-id")
        envelope.update(status=r.status_code, request_id=rid, error=None)
        try:
            data = r.json()
        except ValueError:
            data = None
        if isinstance(data, dict) and isinstance(data.get("case_id"), str):
            # A drafted case (200) or a held receipt (202, or 5xx when the gateway was unverifiable).
            with db.connection() as con:
                row = con.execute("SELECT state FROM outbox WHERE case_id=?",
                                  (data["case_id"],)).fetchone()
            envelope.update(case=data, delivery=row["state"] if row else None,
                            handler_url=handler_url(data["case_id"]))
        else:
            envelope["error"] = error_code(r)
        envelope["trace"] = trace(db, rid) if rid else []
    except (httpx.TimeoutException, asyncio.TimeoutError):
        envelope.update(status=504, error="backend_timeout", case=None)
    except Exception:
        log.exception("ui_submit_failed")
        envelope.update(status=500, error="internal_error", case=None)
    envelope["session_state"], _ = session_state(db, sid)
    envelope["ms"] = round((time.perf_counter() - started) * 1000)
    return envelope


def _stt_error(status, code):
    return JSONResponse({"error": code}, status_code=status)


@router.post("/ui/stt")
async def speech_to_text(request: Request):
    """Push-to-talk audio -> text, on this machine only. The audio is never stored."""
    ctype = (request.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    if ctype not in AUDIO_TYPES:  # not CORS-safelisted: a cross-site page needs a preflight
        return _stt_error(415, "unsupported_media_type")
    audio = await request.body()
    if not audio:
        return _stt_error(400, "audio_missing")
    if len(audio) > MAX_AUDIO:
        return _stt_error(413, "audio_too_long")
    if len(audio) < 44 or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        return _stt_error(415, "unsupported_audio")
    try:
        from ..stt import _load, transcribe  # lazy: the text-only demo does not need the model

        await run_in_threadpool(_load)  # missing package or model download failure
    except Exception as exc:
        log.warning("stt_unavailable %s", type(exc).__name__)
        return _stt_error(503, "stt_unavailable")
    slots = getattr(request.app.state, "stt_slots", None)
    if slots is None:
        slots = request.app.state.stt_slots = asyncio.Semaphore(STT_SLOTS)
    try:
        await asyncio.wait_for(slots.acquire(), STT_WAIT)
    except asyncio.TimeoutError:
        return _stt_error(503, "stt_busy")
    try:
        # Decoding takes about a second; keep the event loop free for other requests.
        return await run_in_threadpool(transcribe, audio)
    except Exception as exc:  # never log audio or text, only the exception type
        log.warning("stt_failed %s", type(exc).__name__)
        return _stt_error(422, "audio_unreadable")
    finally:
        slots.release()


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


# ----- Red team panel (synthetic fixtures only) ------------------------------------------------
REDTEAM_IDS = ("T1", "T2", "T3", "T4", "T5", "E1", "E6", "OUTAGE")
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
    try:
        return {"cases": redteam_cases()}
    except Exception:
        log.exception("ui_redteam_fixtures_failed")
        return JSONResponse({"cases": [], "error": "fixtures_unavailable"}, status_code=503)


@router.post("/ui/redteam/run")
async def run_redteam(body: RedteamRun, request: Request):
    try:
        sample = next((c for c in redteam_cases() if c["id"] == body.id), None)
    except Exception:
        log.exception("ui_redteam_fixtures_failed")
        return JSONResponse({"error": "fixtures_unavailable"}, status_code=503)
    if sample is None:
        return JSONResponse({"error": "unknown_fixture"}, status_code=422)
    started = time.perf_counter()
    state = request.app.state
    headers = {"Authorization": "Bearer " + state.settings.backend_key, "Idempotency-Key": str(uuid4())}
    try:
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
    except (httpx.TimeoutException, asyncio.TimeoutError):
        return JSONResponse({"id": body.id, "error": "backend_timeout"}, status_code=504)
    except Exception:
        log.exception("ui_redteam_failed")
        return JSONResponse({"id": body.id, "error": "internal_error"}, status_code=500)
    rid = response.headers.get("x-request-id")
    events = trace(state.db, rid) if rid else []
    try:
        case = response.json()
    except ValueError:
        case = {}
    cid = case.get("case_id") if isinstance(case, dict) else None
    delivery = None
    if cid:
        with state.db.connection() as con:
            delivery = con.execute("SELECT state FROM outbox WHERE case_id=?", (cid,)).fetchone()
    return {"id": body.id, "status": response.status_code, "case": case, "request_id": rid, "trace": events,
            "outbound_messages": [msg for e in events if e["action"] == "outbound_messages"
                                  for msg in e["meta"].get("messages", [])],
            "completion_headers": next((e["meta"] for e in events if e["source"] == "gateway"
                                        and e["action"] in {"ALLOW", "headers_rejected"}), {}),
            "completion_attempts": sum(e["action"] == "completion_attempted" for e in events),
            "delivery": delivery[0] if delivery else None,
            "handler_url": handler_url(cid) if cid else None,
            "ms": round((time.perf_counter() - started) * 1000)}
