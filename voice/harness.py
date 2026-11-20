"""Closed voice harness: the ElevenLabs bridge's side of a call, with scripted fictional turns.

No microphone, no real voice, no ElevenLabs session (MVP voice decision, docs/policy-matrix.md).
The transcript turns stand in for ElevenLabs speech-to-text output; everything after that is the
real path: backend /v1/chat/completions (Custom LLM contract, SSE) -> live BRANE -> model ->
one server-owned question per turn; then the bridge's explicit confirmation step
(/voice/sessions/{id}/finalize) files the case -> n8n handler review.

Called by n8n/demo.sh --voice (backend on 127.0.0.1:8000, n8n + register running).
Arguments: demo.env, backend/.env, evidence directory.
"""
import base64
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

demo_env, backend_env, evidence_dir = sys.argv[1:4]
MODEL = "openrouter:openai/gpt-6-luna"

CALLS = {
    # Fictional caller, safety report: should end in a case for the handler.
    "safety_call": [
        "A warehouse emergency exit was blocked with boxes.",
        "It happened yesterday, in the warehouse.",
        "Roles are enough, a shift lead stacked them there.",
        "I have a photo of it.",
    ],
    # Fictional caller mentions health data: P3 must hold the session locally.
    "health_call": [
        "My supervisor keeps commenting on my burnout and medication in front of the team.",
    ],
}


def env(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


demo, backend = env(demo_env), env(backend_env)
bridge = {"Authorization": "Bearer " + backend["ELEVENLABS_BRIDGE_KEY"], "Content-Type": "application/json"}
handler = "Basic " + base64.b64encode(f"{demo['HANDLER_REF']}:{demo['HANDLER_PASSWORD']}".encode()).decode()


def call(url, body=None, headers=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 method="POST" if body is not None else "GET")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, dict(r.headers), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode()


def sse_text(raw):
    """Join the assistant content of an SSE stream; require the terminal [DONE]."""
    parts, done = [], False
    for line in raw.splitlines():
        if line.startswith("data: "):
            payload = line[6:]
            if payload == "[DONE]":
                done = True
                continue
            delta = json.loads(payload)["choices"][0]["delta"]
            parts.append(delta.get("content") or "")
    return "".join(parts), done


results, failures = {}, 0
for name, turns in CALLS.items():
    sid = str(uuid.uuid4())
    history, log = [], []
    held = None
    for turn in turns:
        history.append({"role": "user", "content": turn})
        t0 = time.perf_counter()
        status, headers, body = call("http://127.0.0.1:8000/v1/chat/completions", {
            "model": MODEL, "stream": True, "messages": history,
            "elevenlabs_extra_body": {"session_id": sid}}, bridge)
        ms = round((time.perf_counter() - t0) * 1000)
        if status != 200:
            held = json.loads(body).get("error")
            log.append({"caller": turn, "status": status, "error": held, "ms": ms})
            break
        question, done = sse_text(body)
        log.append({"caller": turn, "status": 200, "agent": question, "sse_done": done, "ms": ms,
                    "revision": headers.get("x-session-revision") or headers.get("X-Session-Revision")})
        history.append({"role": "assistant", "content": question})
    outcome = {"turns": log}
    if held is None:
        # Trusted bridge: read the revision, capture the caller's explicit "submit", then finalize.
        _, _, st = call(f"http://127.0.0.1:8000/voice/sessions/{sid}", headers=bridge)
        revision = json.loads(st)["revision"]
        status, _, body = call(f"http://127.0.0.1:8000/voice/sessions/{sid}/finalize",
                               {"confirmed": True, "revision": revision}, bridge)
        case = json.loads(body)
        outcome["finalize"] = {"status": status, "case": case}
        seen = False
        if status == 200:
            for _ in range(20):
                code, _, page = call("http://127.0.0.1:8788/review/" + case["case_id"], headers={"Authorization": handler})
                if code == 200 and "Human decision · pending" in page:
                    seen = True
                    break
                time.sleep(0.25)
        outcome["handler_view_ok"] = seen
        ok = status == 200 and seen and all(t.get("sse_done") for t in log)
        print(("PASS " if ok else "FAIL ") + f"{name}: {len(log)} live turns "
              f"({', '.join(str(t['ms']) + ' ms' for t in log)}), questions {[t['agent'] for t in log]}, "
              f"finalize {status} -> n8n case {case.get('case_id', '?')[:11]}… handler view {'OK' if seen else 'MISSING'}")
        if status == 200:
            print(f"     brief: {case.get('brief')}")
    else:
        _, _, st = call(f"http://127.0.0.1:8000/voice/sessions/{sid}", headers=bridge)
        state = json.loads(st).get("state") if st.startswith("{") else None
        outcome["held"] = {"error": held, "session_state": state}
        ok = held == "restricted_material"
        print(("PASS " if ok else "FAIL ") + f"{name}: held locally on turn {len(log)} ({held}), "
              f"session state {state}, nothing sent to the model or n8n")
    failures += not ok
    results[name] = outcome

Path(evidence_dir).mkdir(exist_ok=True)
out = Path(evidence_dir) / f"voice_harness_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
out.write_text(json.dumps({"note": "Scripted fictional transcript turns stand in for ElevenLabs STT; "
                                   "backend, BRANE, model and n8n are live.", "calls": results},
                          indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Evidence written to {out}")
if failures:
    sys.exit(f"{failures} voice call(s) did not behave as expected")
