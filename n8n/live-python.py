"""Send synthetic reports through the running Python backend (live BRANE) into the n8n workflow.

Called by n8n/demo.sh --python. Arguments: demo.env, backend/.env, data/synthetic_reports.json.
Checks, for each case: the backend's HTTP result, that n8n received exactly the released cases
(the handler review page shows the protected summary), and that held cases never reached n8n.
Synthetic data only. Prints no credentials.
"""
import base64
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

demo_env, backend_env, fixtures = sys.argv[1:4]


def env(path):
    out = {}
    for line in open(path, encoding="utf-8").read().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


demo, backend = env(demo_env), env(backend_env)
cases = {c["id"]: c for c in json.load(open(fixtures, encoding="utf-8"))["cases"]}
auth = "Basic " + base64.b64encode(f"{demo['HANDLER_REF']}:{demo['HANDLER_PASSWORD']}".encode()).decode()


def request(url, body=None, headers=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 method="POST" if body else "GET")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


failures = 0
for cid, expect in [("T1", 200), ("P3a", 200), ("T3", 200), ("T5", 422), ("P3b", 422), ("T4", 422)]:
    c = cases[cid]
    text = c["report"] + ("\n\n" + c["evidence"] if c.get("evidence") else "")
    status, body = request("http://127.0.0.1:8000/reports",
                           {"text": text, "reporter_mode": "anonymous", "source": "text"},
                           {"Authorization": "Bearer " + backend["BACKEND_API_KEY"],
                            "Content-Type": "application/json", "Idempotency-Key": str(uuid.uuid4())})
    line = f"{cid:4} backend {status}"
    ok = status == expect
    if status == 200:
        case = json.loads(body)
        review = (0, "")
        for _ in range(10):  # the outbox delivers right after intake
            review = request("http://127.0.0.1:8788/review/" + case["case_id"], headers={"Authorization": auth})
            if review[0] == 200:
                break
            time.sleep(1)
        in_n8n = review[0] == 200 and case["summary"].split(". ")[0] in review[1]
        ok = ok and in_n8n
        line += f" -> n8n case {case['case_id'][:11]}… persons={case['persons']} handler view {'OK' if in_n8n else 'MISSING'}"
    else:
        line += f" -> held locally ({json.loads(body).get('error')}), not sent to n8n"
    failures += not ok
    print(("PASS " if ok else "FAIL ") + line)

if failures:
    sys.exit(f"{failures} case(s) did not behave as expected")
print("Python backend + live BRANE + n8n workflow: connected.")
