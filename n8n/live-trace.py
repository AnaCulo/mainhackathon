"""Submit the presenter form, or inspect a form submission by its X-Request-ID."""
import argparse
import json
from pathlib import Path
import re
import sqlite3
from uuid import UUID

import httpx
from dotenv import dotenv_values



def inspect(directory, rid):
    with sqlite3.connect((directory / "intake.sqlite").as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        events = db.execute("SELECT case_id,timestamp,source,action,metadata FROM audit_events "
                            "WHERE request_id=? ORDER BY event_id", (rid,)).fetchall()
        if not events:
            raise SystemExit("No intake audit for that request.")
        cid = events[0]["case_id"]
        delivered = db.execute("SELECT state,attempts FROM outbox WHERE case_id=?", (cid,)).fetchone()
    with sqlite3.connect((directory / "register.sqlite").as_uri() + "?mode=ro", uri=True) as db:
        review = db.execute("SELECT decision FROM cases WHERE id=?", (cid,)).fetchone()
    headers = next((json.loads(e["metadata"]) for e in events
                    if (e["source"], e["action"]) == ("gateway", "ALLOW")), {})
    return {**json.loads((directory / "revision.json").read_text(encoding="utf-8")), "timestamp_utc": events[0]["timestamp"], "request_id": rid, "case_id": cid,
            "reason": next((json.loads(e["metadata"]).get("reason") for e in events if e["action"] == "BLOCK"), None),
            "completion_attempts": sum(e["action"] == "completion_attempted" for e in events),
            "validated_model_results": sum(e["action"] == "schema_and_grounding_validated" for e in events),
            "completion_headers": headers, "model": headers.get("X-Brane-Model-Resolved"),
            "n8n_delivery_attempts": delivered["attempts"] if delivered else 0,
            "outbox_state": delivered["state"] if delivered else None,
            "registered": review is not None, "human_decision": (review[0] or "pending") if review else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--request-id", type=UUID, help="Inspect an existing browser submission")
    args = parser.parse_args()
    config = dotenv_values(args.config)
    intake = f"http://127.0.0.1:{int(config['DEMO_INTAKE_PORT'])}/demo"
    queue = f"http://127.0.0.1:{int(config['DEMO_REGISTER_PORT'])}/review"
    auth = (config["HANDLER_REF"], config["HANDLER_PASSWORD"])
    rid = args.request_id
    with httpx.Client(auth=auth, trust_env=False, follow_redirects=False, timeout=135) as client:
        if rid is None:
            form = client.get(intake)
            form.raise_for_status()
            fields = dict(re.findall(r'<input type="hidden" name="(key|ticket)" value="([^"]+)">', form.text))
            if set(fields) != {"key", "ticket"}:
                raise SystemExit("Presenter form unavailable.")
            response = client.post(intake, data={**fields, "text":
                "Two invoice totals differ. The discrepancy appeared on Thursday. The ledger has both entries."})
            rid = UUID(response.headers["X-Request-ID"])
        evidence = inspect(args.config.resolve().parent, str(rid))
        if args.request_id is None:
            evidence["form_http_status"] = response.status_code
            if response.is_success:
                url = queue + "/" + evidence["case_id"]
                review = client.get(url)
                evidence["review_link_verified"] = (url in response.text and review.status_code == 200
                                                     and "Human decision \u00b7 pending" in review.text)
        print(json.dumps(evidence, indent=2))
        out = args.config.parent / f"presenter-{rid}.json"
        out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        if args.request_id is None and not (
            response.status_code == 200 and evidence["completion_headers"] and evidence["validated_model_results"] == 1
            and evidence["outbox_state"] == "delivered" and evidence.get("review_link_verified")
        ):
            raise SystemExit("Presenter smoke failed. See the correlated status above.")


if __name__ == "__main__":
    main()
