import time
from uuid import uuid4

import httpx

from .audit import now
from .models import Case


async def deliver(db, http, settings, cid):
    """Lease a durable outbox entry. The receiver deduplicates by case_id."""
    if not settings.webhook:
        return "pending"
    owner = uuid4().hex
    with db.connection() as con:
        leased = con.execute(
            """UPDATE outbox SET state='sending',owner=?,lease=?,attempts=attempts+1,
            updated_at=? WHERE case_id=? AND (state='pending' OR (state='sending' AND lease<?))""",
            (owner, time.time() + 120, now(), cid, time.time()),
        ).rowcount
        if not leased:
            row = con.execute(
                "SELECT state FROM outbox WHERE case_id=?", (cid,)
            ).fetchone()
            return row["state"] if row else "unknown"
        data = con.execute(
            "SELECT payload FROM cases WHERE case_id=?", (cid,)
        ).fetchone()[0]
    payload = Case.model_validate_json(data)
    state = "pending"
    try:
        async with http.stream(
            "POST",
            settings.webhook,
            json=payload.model_dump(),
            headers={
                "Authorization": "Bearer " + settings.webhook_key,
                "Idempotency-Key": cid,
            },
            timeout=5,
            follow_redirects=False,
        ) as response:
            if 200 <= response.status_code < 300:
                state = "delivered"
    except httpx.HTTPError:
        pass
    with db.connection() as con:
        con.execute(
            "UPDATE outbox SET state=?,owner=NULL,updated_at=? WHERE case_id=? AND owner=?",
            (state, now(), cid, owner),
        )
    return state
