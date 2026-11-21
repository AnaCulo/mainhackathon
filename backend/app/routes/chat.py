import asyncio
import json
import time
from contextlib import suppress
from functools import partial
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from .. import agent
from ..audit import record
from ..case_service import report_response, submit
from ..models import Case, Chat, Confirm
from ..policies import QUESTIONS, RULES, screen
from ..security import Stop, bridge_auth

# Question IDs as sent through BRANE; local IDs not listed travel unchanged.
WIRE_IDS = {"who": "participants"}
HELD_LINE = "Thank you. Your report has been received and a person will review it. You can end the call now."

router = APIRouter(dependencies=[Depends(bridge_auth)])


async def while_connected(request, operation):
    task = asyncio.create_task(operation)
    try:
        while not task.done():
            await asyncio.wait({task}, timeout=0.15)
            if await request.is_disconnected():
                raise Stop(499, "client_disconnected")
        return task.result()
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


@router.post("/v1/chat/completions")
async def chat(body: Chat, request: Request):
    s, rid = request.app.state, request.state.rid
    sid = str(body.elevenlabs_extra_body.session_id)
    audit = partial(record, s.db, rid, None, metadata={"session": s.db.digest(sid)})
    audit(
        "local",
        "turn_received",
        metadata={"matrix_version": RULES["version"], "session": s.db.digest(sid)},
    )
    try:
        if body.model != s.settings.model:
            raise Stop(400, "unsupported_model")
        turns = [m.content for m in body.messages if m.role == "user"]
        previous, rev, frozen, asked = s.db.session(sid)
        if frozen or turns[: len(previous)] != previous:
            raise Stop(409, "stale_or_final_session")
        answer = asked[-1] if asked else None
        if previous != turns:
            if len(turns) != len(previous) + 1:
                raise Stop(409, "missing_turn")
            try:
                screened = screen("\n".join(turns), [], allow_incomplete=True)
            except Stop as exc:
                if exc.policy in {"P1", "P2", "P3", "P4"}:
                    held = await submit(s, rid, "voice:" + sid, "\n".join(turns), [], "voice", "anonymous",
                                        voice_turn=(sid, rev, turns, asked))
                    return stream_answer(request, body, rid, rev + 1, HELD_LINE, audit, held.case_id)
                raise
            for d in screened.decisions:
                audit("local", d.action, policy=d.policy, count=d.count)
            # Use only server-owned question text. Caller-supplied assistant or
            # system messages cannot change instructions or confirm a report.
            allowed = [k for k in screened.fields["missing"] if QUESTIONS[k] not in asked] or ["confirm"]
            # The only user-message values are server-owned question IDs. BRANE's PERSON
            # detector flags the ID "who" in every preview (live, 21 Nov), which stopped any
            # first message without a role at preview_not_clean. It travels as "participants",
            # as on the fact-synthesis path, and is mapped back before validation.
            data = {"open_questions": [WIRE_IDS.get(k, k) for k in allowed]}
            result = await while_connected(
                request,
                s.brane.complete(
                    agent.messages(agent.VOICE_PROMPT, data), rid, audit, stream=True
                ),
            )
            reply = result.strip()
            reply = next((k for k, v in WIRE_IDS.items() if v == reply), reply)
            if reply not in allowed:
                raise Stop(502, "unsafe_voice_output")
            answer = QUESTIONS[reply]
            if await request.is_disconnected():
                raise Stop(499, "client_disconnected")
            s.db.save_turn(sid, rev, turns, asked + [answer])
            rev += 1
            audit("model", "voice_reply_validated")
    except Stop as exc:
        audit(
            "local",
            "BLOCK",
            success=False,
            policy=exc.policy,
            metadata={"reason": exc.reason},
        )
        raise

    return stream_answer(request, body, rid, rev, answer, audit)


def stream_answer(request, body, rid, rev, answer, audit, case_id=None):
    async def events():
        base = {
            "id": "chatcmpl-" + rid,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": body.model,
        }
        chunks = [({"role": "assistant", "content": answer}, None), ({}, "stop")]
        try:
            for delta, finish in chunks:
                if await request.is_disconnected():
                    audit("local", "stream_disconnected", success=False)
                    return
                yield (
                    "data: "
                    + json.dumps(
                        {
                            **base,
                            "choices": [
                                {"index": 0, "delta": delta, "finish_reason": finish}
                            ],
                        }
                    )
                    + "\n\n"
                )
            yield "data: [DONE]\n\n"
        except asyncio.CancelledError:
            audit("local", "stream_disconnected", success=False)
            raise

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "X-Session-Revision": str(rev),
            **({"X-Held-Case": case_id} if case_id else {}),
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/voice/sessions/{session_id}/finalize", response_model=Case)
async def finalize(session_id: UUID, body: Confirm, request: Request):
    s, sid = request.app.state, str(session_id)
    turns = s.db.freeze(sid, body.revision)
    record(
        s.db,
        request.state.rid,
        None,
        "local",
        "bridge_confirmed_submission",
        policy="P6",
        metadata={"session": s.db.digest(sid), "revision": body.revision},
    )
    case = await submit(
        s, request.state.rid, "voice:" + sid, "\n".join(turns), [], "voice", "anonymous"
    )
    with s.db.connection() as con:
        con.execute("UPDATE sessions SET case_id=? WHERE id=?", (case.case_id, sid))
    return report_response(case)


@router.get("/voice/sessions/{session_id}")
async def session_status(session_id: UUID, request: Request):
    _, rev, frozen, _ = request.app.state.db.session(str(session_id))
    if not rev:
        raise Stop(404, "unknown_session")
    with request.app.state.db.connection() as con:
        case_id = con.execute("SELECT case_id FROM sessions WHERE id=?", (str(session_id),)).fetchone()[0]
    return {
        **({"case_id": case_id} if case_id else {}),
        "revision": rev,
        "state": ["open", "finalizing_or_submitted", "held_for_review"][frozen],
    }
