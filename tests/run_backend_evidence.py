#!/usr/bin/env python3
"""Run every synthetic fixture through the running Python backend (live BRANE) and record evidence.

Start the backend first (from backend/: uvicorn app.main:app --port 8000). Then, from the repo root,
with an interpreter that has backend/requirements.txt installed:

  python tests/run_backend_evidence.py

For each case it records: HTTP result, the backend's local decisions (P1-P6 audit events), the
exact text the backend sent towards BRANE (rebuilt with the backend's own message builder, in
gateway form), BRANE's completion headers from the audit log, and the handler brief. Writes
evidence/backend_run_<timestamp>.json. No credentials are written.
"""
import json
import sqlite3
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
from app.agent import report_messages  # noqa: E402
from app.policies import screen  # noqa: E402
from app.security import Stop  # noqa: E402

env = {}
for line in (BACKEND / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"')
db_path = (BACKEND / env.get("DATABASE_URL", "sqlite:///./whistleblower.db")[len("sqlite:///"):]).resolve()
url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"

results = []
for case in json.loads((ROOT / "data" / "synthetic_reports.json").read_text(encoding="utf-8"))["cases"]:
    text = case["report"] + ("\n\n" + case["evidence"] if case.get("evidence") else "")
    try:
        msgs = report_messages(screen(text, []))
        outbound = "\n\n".join(m["content"] for m in msgs)
    except Stop:
        outbound = None
    req = urllib.request.Request(url + "/reports", method="POST", data=json.dumps(
        {"text": text, "reporter_mode": "anonymous", "source": "text"}).encode())
    for k, v in {"Authorization": "Bearer " + env["BACKEND_API_KEY"], "Content-Type": "application/json",
                 "Idempotency-Key": str(uuid.uuid4())}.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            status, headers, body = r.status, dict(r.headers), json.loads(r.read())
    except urllib.error.HTTPError as e:
        status, headers, body = e.code, dict(e.headers), json.loads(e.read())
    rid = next((v for k, v in headers.items() if k.lower() == "x-request-id"), None)
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as con:
        con.row_factory = sqlite3.Row
        events = [dict(r) for r in con.execute(
            "SELECT source, action, policy_id, count, model_route, success, metadata FROM audit_events "
            "WHERE request_id=? ORDER BY event_id", (rid,))]
    gateway = next((json.loads(e["metadata"] or "{}") for e in events
                    if e["source"] == "gateway" and e["action"] in ("ALLOW", "headers_rejected")), {})
    completion = any(e["action"] == "completion_attempted" for e in events)
    results.append({
        "id": case["id"], "http_status": status, "response": body, "x_request_id": rid,
        "local_decisions": [{k: e[k] for k in ("action", "policy_id", "count")} for e in events if e["source"] == "local"],
        "block_reason": next((json.loads(e["metadata"] or "{}").get("reason") for e in events
                              if e["source"] == "local" and e["action"] == "BLOCK"), None),
        "completion_attempted": completion,
        "outbound_text_to_brane": outbound if completion else None,
        "brane_completion_headers": gateway,
    })
    print(f"{case['id']:4} HTTP {status} completion={'yes' if completion else 'no '} "
          f"{body.get('error') or body.get('summary')}")

out = ROOT / "evidence" / f"backend_run_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
out.write_text(json.dumps({"backend": url, "policy_sha256": env.get("BRANE_POLICY_SHA256"),
                           "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {out.relative_to(ROOT)}")
