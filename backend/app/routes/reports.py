from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from ..case_service import submit
from ..models import Case, DraftQuestions, Report
from ..policies import screen
from ..n8n_client import deliver
from ..security import backend_auth

router = APIRouter(dependencies=[Depends(backend_auth)])


@router.post("/reports/clarify", response_model=DraftQuestions)
async def clarify(body: Report):
    """Optional draft step. Submission and receipt use POST /reports."""
    fields = screen(body.text, body.identities, allow_incomplete=True).fields
    return DraftQuestions(missing=fields["missing"], follow_up=fields["follow_up"])


@router.post("/reports", response_model=Case)
async def reports(
    body: Report,
    request: Request,
    idempotency_key: Annotated[UUID | None, Header()] = None,
):
    return await submit(
        request.app.state,
        request.state.rid,
        "text:" + str(idempotency_key or request.state.rid),
        body.text,
        body.identities,
        "text",
        body.reporter_mode,
    )


@router.post("/deliveries/retry")
async def retry(request: Request):
    import time

    s = request.app.state
    with s.db.connection() as con:
        rows = con.execute(
            """SELECT case_id FROM outbox WHERE state='pending' OR
            (state='sending' AND lease<?) ORDER BY updated_at LIMIT 20""",
            (time.time(),),
        ).fetchall()
    return {
        "deliveries": {
            r[0]: await deliver(s.db, s.http, s.settings, r[0]) for r in rows
        }
    }
