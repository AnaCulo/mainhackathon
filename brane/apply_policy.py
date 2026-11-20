#!/usr/bin/env python3
"""Apply brane/team-policy.json to the team's BRANE department and print its fingerprint.

Python 3.9+, standard library only. Reads BRANE_BASE_URL and BRANE_API_KEY from the
environment or the repo's .env. The fingerprint uses the same canonical form as the
backend (backend/app/brane_client.py: policy_digest), so it can be pinned as
BRANE_POLICY_SHA256.

  python3 brane/apply_policy.py --diff                 # show what would change, apply nothing
  python3 brane/apply_policy.py                        # apply, then print the fingerprint
  python3 brane/apply_policy.py --pin backend/.env     # apply and pin the fingerprint
  python3 brane/apply_policy.py --fingerprint --pin backend/.env   # only re-pin the live policy

The policy is shared by the whole team: announce changes before applying them.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY_FILE = Path(__file__).resolve().parent / "team-policy.json"


def load_env():
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    for key in ("BRANE_BASE_URL", "BRANE_API_KEY"):
        if not os.environ.get(key):
            sys.exit(f"Missing {key}. Copy .env.example to .env and add the team key.")


def call(method, path, body=None):
    url = os.environ["BRANE_BASE_URL"].rstrip("/") + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + os.environ["BRANE_API_KEY"])
    req.add_header("User-Agent", "hotline-policy/1.0")  # urllib's default UA is blocked (Cloudflare 1010)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        text = err.read().decode("utf-8", errors="replace")
        try:
            return err.code, json.loads(text)
        except ValueError:
            return err.code, text


def policy_digest(document):
    """Identical to backend/app/brane_client.py policy_digest."""
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def desired_body():
    spec = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
    return {k: v for k, v in spec.items() if not k.startswith("_") and k != "version"}, spec["version"]


def diff(current, body):
    changes = []
    for cat, action in body["categories"].items():
        old = current.get("categories", {}).get(cat)
        if old != action:
            changes.append(f"  {cat}: {old} -> {action}")
    old_codes = {s.get("code"): s.get("action") for s in current.get("semanticCategories", [])}
    new_codes = {s["code"]: s["action"] for s in body["semanticCategories"]}
    for code in sorted(set(old_codes) | set(new_codes)):
        if old_codes.get(code) != new_codes.get(code):
            changes.append(f"  semantic {code}: {old_codes.get(code)} -> {new_codes.get(code)}")
    for key in ("routingMode", "piiSensitivity"):
        if key in body and current.get(key) != body[key]:
            changes.append(f"  {key}: {current.get(key)} -> {body[key]}")
    return changes


def pin(env_path, digest):
    path = Path(env_path)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    line = f"BRANE_POLICY_SHA256={digest}"
    for i, existing in enumerate(lines):
        if re.match(r"\s*BRANE_POLICY_SHA256\s*=", existing):
            lines[i] = line
            break
    else:
        lines.append(line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    print(f"Pinned BRANE_POLICY_SHA256 in {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff", action="store_true", help="show changes, apply nothing")
    ap.add_argument("--fingerprint", action="store_true", help="do not apply; fingerprint the live policy")
    ap.add_argument("--pin", metavar="ENV_FILE", help="write BRANE_POLICY_SHA256 into this .env file")
    args = ap.parse_args()
    load_env()

    status, current = call("GET", "/policy")
    if status != 200:
        sys.exit(f"GET /policy failed: HTTP {status} {current}")
    body, version = desired_body()

    if not args.fingerprint:
        changes = diff(current, body)
        print(f"{len(changes)} change(s) for {version}:" if changes else "Live policy already matches the file.")
        print("\n".join(changes))
        if args.diff:
            return
        if changes:
            status, result = call("PUT", "/policy", body)
            if status != 200:
                sys.exit(f"PUT /policy failed: HTTP {status} {json.dumps(result)[:1000]}")
            status, current = call("GET", "/policy")
            remaining = diff(current, body)
            if remaining:
                sys.exit("Policy applied but the live policy still differs:\n" + "\n".join(remaining))

    digest = policy_digest(current)
    print(f"Live summary: {current.get('summary')}")
    print(f"Updated at:   {current.get('updatedAt')}")
    print(f"Fingerprint:  {digest}")
    if args.pin:
        pin(args.pin, digest)


if __name__ == "__main__":
    main()
