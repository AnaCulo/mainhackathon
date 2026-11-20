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
from ..case_service import submit
from ..models import Case, Chat, Confirm
from ..policies import QUESTIONS, RULES, screen
from ..security import Stop, bridge_auth

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
                screened = screen("\n".join(turns), [], voice=True)
            except Stop as exc:
                if exc.policy in {"P1", "P2", "P3", "P4"}:
                    s.db.save_turn(sid, rev, turns, asked, frozen=2)
                raise
            for d in screened.decisions:
                audit("local", d.action, policy=d.policy, count=d.count)
            # Use only server-owned question text. Caller-supplied assistant or
            # system messages cannot change instructions or confirm a report.
            candidates = [
                QUESTIONS[k]
                for k in screened.fields["missing"]
                if QUESTIONS[k] not in asked
            ]
            allowed = candidates or [QUESTIONS["confirm"]]
            data = {"screened_history": screened.fields, "allowed_questions": allowed}
            result = await while_connected(
                request,
                s.brane.complete(
                    agent.messages(agent.VOICE_PROMPT, data), rid, audit, stream=True
                ),
            )
            if result.strip() not in allowed:
                raise Stop(502, "unsafe_voice_output")
            answer = result.strip()
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
    return case


@router.get("/voice/sessions/{session_id}")
async def session_status(session_id: UUID, request: Request):
    _, rev, frozen, _ = request.app.state.db.session(str(session_id))
    if not rev:
        raise Stop(404, "unknown_session")
    return {
        "revision": rev,
        "state": ["open", "finalizing_or_submitted", "held_for_review"][frozen],
    }
