"""Presenter-only loopback UI. Raw form data stays in the intake process."""

import hashlib
import hmac
import os
from html import escape
from secrets import compare_digest
from urllib.parse import parse_qs
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .main import create_app
from .models import Report
from .routes.reports import reports
from .security import Stop


def page(title, content, status=200):
    return HTMLResponse(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{title}</title><style>body{{max-width:44rem;margin:3rem auto;'
        'padding:0 1rem;background:#f6f4ee;color:#172c31;font:18px/1.5 system-ui}'
        'textarea{display:block;width:95%;margin:.5rem 0 1rem;padding:.6rem}'
        'button{font:inherit;padding:.4rem 1rem}a{color:#136963}</style>'
        f'<main><h1>{title}</h1>{content}</main></html>',
        status_code=status,
        headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; "
                 "form-action 'self'; frame-ancestors 'none'", "Referrer-Policy": "no-referrer"},
    )


def create_demo(settings=None, transport=None):
    app = create_app(settings, transport)
    user, password = os.environ["HANDLER_REF"], os.environ["HANDLER_PASSWORD"]
    review_origin = "http://127.0.0.1:" + str(int(os.environ.get("DEMO_REGISTER_PORT", 8788)))
    if not user or len(password) < 16:
        raise ValueError("Configure the private presenter login")

    def authenticate(credentials: HTTPBasicCredentials = Depends(HTTPBasic())):
        if not (compare_digest(credentials.username.encode(), user.encode())
                and compare_digest(credentials.password.encode(), password.encode())):
            raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})

    def ticket(key):
        return hmac.new(password.encode(), f"intake:{key}".encode(), hashlib.sha256).hexdigest()

    @app.get("/demo", dependencies=[Depends(authenticate)])
    async def form():
        key = uuid4()
        return page("Submit a synthetic report",
                    '<form method="post" action="/demo">'
                    f'<input type="hidden" name="key" value="{key}">'
                    f'<input type="hidden" name="ticket" value="{ticket(key)}">'
                    '<label>Report<textarea required maxlength="16000" rows="7" name="text">'
                    '</textarea></label><button>Prepare case for review</button></form>')

    @app.post("/demo", dependencies=[Depends(authenticate)])
    async def submit_form(request: Request):
        rid = escape(request.state.rid)
        try:
            if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
                return page("Submission failed", f"<p>Unsupported form format.</p><p>Request {rid}</p>", 415)
            fields = parse_qs((await request.body()).decode(), strict_parsing=True, max_num_fields=3)
            key = UUID(fields["key"][0])
            if not compare_digest(fields["ticket"][0].encode(), ticket(key).encode()):
                return page("Submission failed", f"<p>Invalid form ticket.</p><p>Request {rid}</p>", 403)
            body = Report(text=fields["text"][0])
        except (KeyError, ValueError):
            return page("Submission failed", f"<p>Invalid form.</p><p>Request {rid}</p>", 422)
        try:
            # Same validated input and handler as POST /reports, including idempotency.
            case = await reports(body, request, key)
            with request.app.state.db.connection() as con:
                delivery = con.execute("SELECT state FROM outbox WHERE case_id=?", (case.case_id,)).fetchone()
            if not delivery or delivery["state"] != "delivered":
                raise Stop(502, "handoff_unconfirmed")
        except Stop as exc:
            return page("Submission failed",
                        f"<p>HTTP {exc.status} · {escape(exc.reason)}</p><p>Request {rid}</p>"
                        '<a href="/demo">Open a new report</a>', exc.status)
        return page("Case ready for human review",
                    f"<p>{escape(case.summary)}</p><p>Request {rid}</p>"
                    f'<a href="{review_origin}/review/{case.case_id}">Review {case.case_id}</a>')

    return app
