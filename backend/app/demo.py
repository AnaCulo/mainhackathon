"""Presenter-only loopback UI. Raw form data stays in the intake process."""

import json
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
from .case_service import http_status
from .models import HeldCase, Report
from .routes.ui import local_only
from .routes.reports import submit_report
from .security import Stop


# Same design tokens as the intake site (static/index.html) and the handler queue (n8n/service.mjs).
STYLE = (
    ":root{--bg:#eef1f4;--surface:#fff;--surface-2:#f6f8fa;--ink:#121820;--muted:#4f5968;--line:#dde2e8;"
    "--line-strong:#c3cad4;--brand-1:#0c3b33;--brand-2:#17594c;--brand-3:#22796a;--on-brand-muted:#d3ebe5;"
    "--accent:#17594c;--accent-hover:#10463c;--accent-ink:#fff;--held:#8a4b00;--held-soft:#fcefd9;"
    "--stop:#b42318;--stop-soft:#fdeceb;--banner:#fff4dc;--banner-ink:#6b3d00;--code:#f3f5f8;--focus:#2563eb;"
    "--shadow:0 1px 2px rgba(16,24,40,.06),0 4px 14px rgba(16,24,40,.06)}"
    "@media (prefers-color-scheme:dark){:root{--bg:#0b0e12;--surface:#141920;--surface-2:#19202a;--ink:#eaedf1;"
    "--muted:#b0b8c5;--line:#262e39;--line-strong:#36404d;--brand-1:#0e3530;--brand-2:#155247;--brand-3:#1f7062;"
    "--on-brand-muted:#b9ddd4;--accent:#6fd0b8;--accent-hover:#8fdcc8;--accent-ink:#072019;--held:#f5bb63;"
    "--held-soft:#35270e;--stop:#ff978e;--stop-soft:#3b1a18;--banner:#2c2209;--banner-ink:#f5d08a;--code:#0f1318;"
    "--focus:#7aa7ff;--shadow:0 1px 2px rgba(0,0,0,.5),0 6px 18px rgba(0,0,0,.25)}}"
    "*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);overflow-x:hidden;"
    "font:15.5px/1.5 system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif}"
    ":focus-visible{outline:3px solid var(--focus);outline-offset:2px}a{color:var(--accent)}"
    ".banner{background:var(--banner);color:var(--banner-ink);font-size:13px;font-weight:600;text-align:center;padding:6px 14px}"
    "header{background:linear-gradient(120deg,var(--brand-1),var(--brand-2) 55%,var(--brand-3));color:#fff}"
    "header div{max-width:1040px;margin:0 auto;padding:20px 28px}header b{display:block;font-size:23px;letter-spacing:-.015em}"
    "header span{color:var(--on-brand-muted);font-size:14px}"
    "main{max-width:1040px;margin:0 auto;padding:22px 28px 36px;display:grid;gap:16px}"
    ".card{background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);min-width:0}"
    ".card h1{margin:0;padding:14px 20px;border-bottom:1px solid var(--line);font-size:17px}"
    ".card .body{padding:16px 20px 18px}.card .body>:first-child{margin-top:0}.card .body>:last-child{margin-bottom:0}"
    ".card.held h1{color:var(--held)}.card.stop h1{color:var(--stop)}"
    "h2{font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);margin:18px 0 6px}"
    "pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--code);border:1px solid var(--line);"
    "border-radius:12px;padding:12px 14px;margin:0;font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}"
    "form{display:grid;gap:14px}label{display:grid;gap:6px;font-weight:600}"
    "textarea{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--line-strong);"
    "border-radius:10px;padding:10px 12px;width:100%;resize:vertical}"
    "button,a.btn{font:inherit;font-weight:650;background:var(--accent);color:var(--accent-ink);border:1px solid var(--accent);"
    "padding:9px 16px;border-radius:10px;cursor:pointer;min-height:42px;justify-self:start;text-decoration:none;display:inline-block}"
    "button:hover,a.btn:hover{background:var(--accent-hover)}"
    "@media (max-width:640px){header div{padding:16px}main{padding:14px}.card h1,.card .body{padding-left:14px;padding-right:14px}}"
)


def page(title, content, status=200):
    tone = " stop" if status >= 400 else " held" if status in (202, 503) else ""
    return HTMLResponse(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        f'<title>{title}</title><style>{STYLE}</style>'
        '<div class="banner" role="note">Synthetic demo: every name and event on this page is made up</div>'
        '<header><div><b>Anonymous Whistleblower Intake Hotline</b>'
        '<span>Intake host · local only · 127.0.0.1. Designated handler only.</span></div></header>'
        f'<main><section class="card{tone}"><h1>{title}</h1><div class="body">{content}</div></section></main></html>',
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
            case = await submit_report(body, request, key)
            if isinstance(case, HeldCase):
                title = ("Report received, held for human review" if http_status(case) == 202 else
                         "Automated check unavailable. Report received and held")
                return page(title, f"<p>Case {case.case_id}</p><p>{case.hold_reason} ({case.policy})</p>",
                            http_status(case))
            with request.app.state.db.connection() as con:
                delivery = con.execute("SELECT state FROM outbox WHERE case_id=?", (case.case_id,)).fetchone()
            if not delivery or delivery["state"] != "delivered":
                raise Stop(502, "handoff_unconfirmed")
        except Stop as exc:
            return page("Submission failed",
                        f"<p>HTTP {exc.status} · {escape(exc.reason)}</p><p>Request {rid}</p>"
                        '<a class="btn" href="/demo">Open a new report</a>', exc.status)
        return page("Case ready for human review",
                    f"<p>{escape(case.summary)}</p><p>Request {rid}</p>"
                    f'<a class="btn" href="{review_origin}/review/{case.case_id}">Review {case.case_id}</a>')

    @app.get("/demo/held/{case_id}", dependencies=[Depends(local_only), Depends(authenticate)])
    async def held_original(case_id: str):
        db = app.state.db
        with db.connection() as con:
            row = con.execute("SELECT evidence, extraction, receipt FROM cases WHERE case_id=? AND receipt IS NOT NULL",
                              (case_id,)).fetchone()
        if not row:
            raise HTTPException(404)
        receipt = HeldCase.model_validate_json(row["receipt"])
        provenance = db.unseal(row["extraction"]).get("local_fact_provenance", []) if row["extraction"] else []
        return page("Review original on the intake host",
                    f"<p>{escape(receipt.case_id)} · held: {escape(receipt.hold_reason)} ({escape(receipt.policy)}). "
                    "This original never left this machine. Read it here, then record your decision in the handler queue.</p>"
                    f"<h2>Original report</h2><pre>{escape(db.unseal(row['evidence'])['text'])}</pre>"
                    f"<h2>Local fact provenance</h2><pre>{escape(json.dumps(provenance, ensure_ascii=False))}</pre>")

    return app
