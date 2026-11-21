#!/usr/bin/env python3
"""Run every synthetic fixture through the running Python backend (live BRANE) and record evidence.

Start the backend first (from backend/: uvicorn app.main:app --port 8000). Then, from the repo root,
with an interpreter that has backend/requirements.txt installed:

  python tests/run_backend_evidence.py

For each case it records: HTTP result, the backend's local decisions (P1-P6 audit events), the
audited model-bound user content, BRANE completion headers, receipt and workflow delivery state. Writes
evidence/backend_run_<timestamp>.json. No credentials are written.
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import httpx
from dotenv import dotenv_values
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
private = BACKEND / ".env"
env = {}
if private.is_file() and subprocess.run(
    ["git", "check-ignore", "-q", "backend/.env"], cwd=ROOT
).returncode == 0:
    env.update(dotenv_values(private, interpolate=False))
env.update(os.environ)
if not all(env.get(key) for key in ("BRANE_API_KEY", "BRANE_POLICY_SHA256", "BACKEND_API_KEY")):
    raise SystemExit("The live evidence run requires the protected backend settings.")
db_url = env.get("DATABASE_URL", "sqlite:///./whistleblower.db")
if not db_url.startswith("sqlite:///"):
    raise SystemExit("Use the presenter's local SQLite database.")
db_path = (BACKEND / db_url[len("sqlite:///"):]).resolve()
url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
if not re.fullmatch(r"http://127\.0\.0\.1:[0-9]{1,5}", url):
    raise SystemExit("Use the numeric loopback intake URL.")

results = []
for case in json.loads((ROOT / "data" / "synthetic_reports.json").read_text(encoding="utf-8"))["cases"]:
    text = case["report"] + ("\n\n" + case["evidence"] if case.get("evidence") else "")
    with httpx.Client(trust_env=False, follow_redirects=False, timeout=120) as client:
        response = client.post(url + "/reports", json={"text": text},
                               headers={"Authorization": "Bearer " + env["BACKEND_API_KEY"],
                                        "Idempotency-Key": str(uuid.uuid4())})
    status, body = response.status_code, response.json()
    rid = response.headers["x-request-id"]
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as con:
        con.row_factory = sqlite3.Row
        events = [dict(r) for r in con.execute(
            "SELECT source, action, policy_id, count, model_route, success, metadata FROM audit_events "
            "WHERE request_id=? ORDER BY event_id", (rid,))]
        if not events:
            raise SystemExit("No matching request audit. Check the database path.")
        delivery = con.execute("SELECT state FROM outbox WHERE case_id=?", (body.get("case_id"),)).fetchone()
    outbound = [msg for e in events if e["action"] == "outbound_messages"
                for msg in json.loads(e["metadata"])["messages"]]
    gateway = next((json.loads(e["metadata"] or "{}") for e in events
                    if e["source"] == "gateway" and e["action"] in ("ALLOW", "headers_rejected")), {})
    completion = any(e["action"] == "completion_attempted" for e in events)
    results.append({
        "id": case["id"], "http_status": status, "response": body, "x_request_id": rid,
        "local_decisions": [{k: e[k] for k in ("action", "policy_id", "count")} for e in events if e["source"] == "local"],
        "block_reason": next((json.loads(e["metadata"] or "{}").get("reason") for e in events
                              if e["source"] == "local" and e["action"] == "BLOCK"), None),
        "completion_attempted": completion,
        "outbound_user_messages": outbound,
        "held_registered": any(e["action"] == "held_registered" for e in events),
        "outbox_state": delivery[0] if delivery else None,
        "brane_completion_headers": gateway,
    })
    print(f"{case['id']:4} HTTP {status} completion={'yes' if completion else 'no '} "
          f"{body.get('hold_reason') or body.get('summary')}")

out = ROOT / "evidence" / f"backend_run_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
version = json.loads((BACKEND / "app/policy.json").read_text(encoding="utf-8"))["version"]
out.write_text(json.dumps({"backend": url, "policy_version": version, "policy_sha256": env.get("BRANE_POLICY_SHA256"),
                           "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Wrote {out.relative_to(ROOT)}")
