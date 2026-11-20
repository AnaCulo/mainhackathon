"""Live evidence trace for the demo: one synthetic report end to end, with a human decision.

Called by n8n/demo.sh --trace (backend on 127.0.0.1:8000, n8n + register running).
Arguments: demo.env, backend/.env, backend directory, evidence directory.

Records, without any credentials:
  1. the exact messages the backend sends to BRANE, and BRANE's non-executing preview of
     each (route, detections, outgoing cloud payload: proof of what the cloud model receives),
  2. elapsed time from submission until the handler can open a brief with reported fact,
     timeline, evidence and "Human decision · pending",
  3. BRANE's completion headers from the backend's audit log for that request,
  4. a human decision recorded on the review form (scripted only with --decide; otherwise
     the script waits for a person to decide in the browser).
"""
import base64
import html
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

demo_env, backend_env, backend_dir, evidence_dir = sys.argv[1:5]
decide = "--decide" in sys.argv
REPORT = "Two invoice totals differ. The discrepancy appeared on Monday. The ledger has both entries."


def env(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


demo, backend = env(demo_env), env(backend_env)
handler = "Basic " + base64.b64encode(f"{demo['HANDLER_REF']}:{demo['HANDLER_PASSWORD']}".encode()).decode()


def call(url, body=None, headers=None, form=None):
    data = json.dumps(body).encode() if body is not None else (form.encode() if form else None)
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("User-Agent", "hotline-trace/1.0")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, dict(r.headers), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode()


# 1. What leaves: rebuild the backend's outbound messages and preview each at BRANE.
sys.path.insert(0, str(Path(backend_dir).resolve()))
from app.agent import report_messages  # noqa: E402
from app.policies import screen  # noqa: E402

messages = report_messages(screen(REPORT, []))
brane = backend["BRANE_BASE_URL"].rstrip("/")
previews = []
for m in messages:
    _, _, body = call(brane + "/policy/test", {"prompt": m["content"], "executeCompletion": False},
                      {"Authorization": "Bearer " + backend["BRANE_API_KEY"], "Content-Type": "application/json"})
    p = json.loads(body)
    previews.append({
        "role": m["role"],
        "route": p["decision"]["route"],
        "detected_categories": p["detectedCategories"],
        "semantic_matches": p["matchedSemanticCategories"],
        "prompt_injection": p["promptInjection"]["detected"],
        "outgoing_cloud_payload": p["outgoingCloudPayloadPreview"],
        "payload_identical_to_message": p["outgoingCloudPayloadPreview"] == m["content"],
    })

# 2. Submit and time until the handler can open a complete brief.
t0 = time.perf_counter()
status, headers, body = call("http://127.0.0.1:8000/reports",
                             {"text": REPORT, "reporter_mode": "anonymous", "source": "text"},
                             {"Authorization": "Bearer " + backend["BACKEND_API_KEY"],
                              "Content-Type": "application/json", "Idempotency-Key": str(uuid.uuid4())})
if status != 200:
    sys.exit(f"backend returned HTTP {status}: {body[:200]}")
case = json.loads(body)
request_id = next((v for k, v in headers.items() if k.lower() == "x-request-id"), None)
review_url = "http://127.0.0.1:8788/review/" + case["case_id"]
page = ""
for _ in range(60):
    code, _, page = call(review_url, headers={"Authorization": handler})
    if code == 200 and "Human decision · pending" in page:
        break
    time.sleep(0.25)
elapsed = time.perf_counter() - t0
text = html.unescape(page)


def section(label):
    m = re.search(rf"<b>{label}</b><ul>(.*?)</ul>", text, re.S)
    return [re.sub("<[^>]+>", "", li).strip() for li in re.findall(r"<li>(.*?)</li>", m[1], re.S)] if m else []


brief_view = {"facts": section("Reported facts"), "timeline": section("Timeline"), "evidence": section("Evidence"),
              "decision_pending": "Human decision · pending" in text}
fields_ok = all(brief_view[k] and brief_view[k] != ["None supplied"] for k in ("facts", "timeline", "evidence")) \
    and brief_view["decision_pending"]

# 3. BRANE's completion headers as recorded by the backend for this request.
db_url = backend.get("DATABASE_URL", "sqlite:///./whistleblower.db")
db_path = (Path(backend_dir) / db_url[len("sqlite:///"):]).resolve()
with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as con:
    con.row_factory = sqlite3.Row
    events = [dict(r) for r in con.execute(
        "SELECT source, action, policy_id, count, model_route, success, metadata FROM audit_events "
        "WHERE request_id=? ORDER BY event_id", (request_id,))]
gateway = next((json.loads(e["metadata"] or "{}") for e in events if e["source"] == "gateway" and e["action"] == "ALLOW"), {})

# 4. Human decision.
decision = None
if decide:
    form = {k: re.search(rf'name="{k}" value="([^"]+)"', page)[1] for k in ("task", "ticket", "expires")}
    form.update(action="investigate", reason="Synthetic demo: compare the two ledger entries before any contact.",
                clear="yes")
    code, _, _ = call(review_url, form=urllib.parse.urlencode(form),
                      headers={"Authorization": handler, "Content-Type": "application/x-www-form-urlencoded"})
    _, _, after = call(review_url, headers={"Authorization": handler})
    m = re.search(r"Human decision · ([a-z]+)", after)
    decision = {"submitted_status": code, "recorded": m[1] if m else None, "by": "scripted on behalf of the handler"}
else:
    print(f"Open {review_url} as the handler and record the decision in the browser.")

result = {
    "fixture": REPORT,
    "outbound_messages_previewed_at_brane": previews,
    "backend_response": case,
    "x_request_id": request_id,
    "brane_completion_headers": gateway,
    "audit_events": events,
    "seconds_until_handler_can_open_brief": round(elapsed, 2),
    "handler_view": brief_view,
    "four_fields_present": fields_ok,
    "human_decision": decision,
}
Path(evidence_dir).mkdir(exist_ok=True)
stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
out = Path(evidence_dir) / f"live_trace_{stamp}.json"
out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"Outbound to BRANE: {len(previews)} messages, routes {[p['route'] for p in previews]}, "
      f"detections {sum(len(p['detected_categories']) for p in previews)}, "
      f"payload identical {all(p['payload_identical_to_message'] for p in previews)}")
print(f"BRANE completion: {gateway.get('X-Brane-Routed-To')} / action {gateway.get('X-Brane-Action')} / "
      f"redacted {gateway.get('X-Brane-Redacted')} / model {gateway.get('X-Brane-Model-Resolved')}")
print(f"Agent: {elapsed:.1f} s until the handler can open the brief "
      f"(fact, timeline, evidence, decision pending: {'all present' if fields_ok else 'INCOMPLETE'})")
print(f"Handler view: {brief_view}")
print(f"Human decision: {decision}")
print(f"Evidence written to {out}")
if not fields_ok:
    sys.exit(1)
