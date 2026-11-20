#!/usr/bin/env python3
"""Repair the hotline agent through the ElevenLabs API, as a DRAFT (never publishes).

Why: after a secret was added in the dashboard, the draft's custom_llm.url became empty and the
dashboard's LLM panel crashes ("null.matchAll"). The API does not return your draft, and the
committed config on the branch is still ElevenLabs' defaults, so `fix` writes the COMPLETE intended
configuration explicitly (from voice/agent_config.json and the policy decisions), not a patch.

Run it yourself with your own ElevenLabs API key in the environment (never pasted into chat):
  read -s ELEVENLABS_API_KEY && export ELEVENLABS_API_KEY
  python3 voice/elevenlabs_fix_llm.py inspect
  python3 voice/elevenlabs_fix_llm.py fix https://<tunnel>.trycloudflare.com/v1 <secret-name>

inspect: committed config summary, every boolean override path, every setting whose name mentions
         "file", and your workspace secrets (name + id only; values are never requested).
fix:     builds the full draft and saves it with POST .../drafts?branch_id=... . It does not
         commit a version or publish.
publish: commits the same config as a new version on the branch (PATCH ...?branch_id=...),
         with authentication ON (signed URLs only). Conversations only run committed versions.
Standard library only.
"""
import copy
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

AGENT = "agent_5001m7wyb7nbf1x8c7aan33vct1m"
BRANCH = "agtbrch_1901m7wyb8kre1zb880xtxs6aywv"
MODEL_ID = "openrouter:openai/gpt-6-luna"
BASE = "https://api.elevenlabs.io/v1/convai"
API = f"{BASE}/agents/{AGENT}"
CONFIG = Path(__file__).resolve().parent / "agent_config.json"
KEY = os.environ.get("ELEVENLABS_API_KEY") or sys.exit("Set ELEVENLABS_API_KEY in your own shell first.")


def call(method, url, body=None):
    req = urllib.request.Request(url, method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header("xi-api-key", KEY)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "hotline-agent-fix/1.1")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            text = r.read().decode()
            return r.status, json.loads(text) if text else None
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, json.loads(text)
        except ValueError:
            return e.code, text[:500]


def redact(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            lk = k.lower()
            if any(s in lk for s in ("key", "token", "secret", "password", "authorization", "value")) \
                    and lk not in ("secret_id", "env_var_label", "api_key", "model_id", "voice_id") \
                    and isinstance(v, str):
                out[k] = "***"
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj


def walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            yield p, v
            yield from walk(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")


def get_agent():
    status, agent = call("GET", f"{API}?branch_id={BRANCH}")
    if status != 200:
        sys.exit(f"GET agent failed: HTTP {status} {json.dumps(redact(agent))[:300]}")
    return agent


def secrets():
    status, body = call("GET", f"{BASE}/secrets")
    if status != 200:
        return status, []
    items = body.get("secrets", body) if isinstance(body, dict) else body
    return status, [{"name": s.get("name"), "secret_id": s.get("secret_id") or s.get("id")} for s in items]


def inspect():
    agent = get_agent()
    print("=== committed config (branch)")
    for p, v in walk(agent):
        if p.endswith(("prompt.llm", "custom_llm", "backup_llm_config", "privacy.zero_retention_mode",
                       "privacy.record_voice", "privacy.retention_days")):
            print(f"  {p}: {json.dumps(redact(v))[:200]}")
    print("\n=== boolean override paths (true ones marked *)")
    for p, v in walk(agent.get("platform_settings", {}).get("overrides", {}), "platform_settings.overrides"):
        if isinstance(v, bool):
            print(f"  {'*' if v else ' '} {p}")
    print("\n=== settings mentioning 'file' or 'extra_body'")
    for p, v in walk(agent):
        last = p.rsplit(".", 1)[-1].lower()
        if ("file" in last or "extra_body" in last) and not isinstance(v, (dict, list)):
            print(f"  {p}: {json.dumps(v)}")
    status, items = secrets()
    print(f"\n=== workspace secrets (GET /secrets: HTTP {status}; names and ids only)")
    for s in items:
        print(f"  {s['name']}: {s['secret_id']}")


def set_path(root, dotted, value):
    keys = dotted.split(".")
    node = root
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value


def build(url, secret_name):
    url = url.rstrip("/")
    if not url.startswith("https://") or url.endswith("/chat/completions"):
        sys.exit("Pass the base URL ending in /v1 (ElevenLabs appends /chat/completions).")
    _, items = secrets()
    match = [s for s in items if s["name"] == secret_name]
    if len(match) != 1:
        sys.exit(f"Secret named {secret_name!r} not found exactly once. Run inspect to see names.")
    secret_id = match[0]["secret_id"]

    agent = get_agent()
    spec = json.loads(CONFIG.read_text(encoding="utf-8"))["conversation_config"]["agent"]
    new = {k: copy.deepcopy(agent[k]) for k in ("conversation_config", "platform_settings", "workflow", "name", "tags")
           if k in agent and agent[k] is not None}
    new.setdefault("workflow", {})
    new["name"] = "[Culo] Whistleblower intake (synthetic)"
    cc, ps = new["conversation_config"], new["platform_settings"]

    # Version A wording from voice/agent_config.json (docs/voice-disclosure.md).
    set_path(cc, "agent.first_message", spec["first_message"])
    set_path(cc, "agent.language", spec.get("language", "en"))
    set_path(cc, "agent.prompt.prompt", spec["prompt"]["prompt"])
    # Custom LLM -> backend tunnel -> BRANE; no ElevenLabs fallback models (P5).
    set_path(cc, "agent.prompt.llm", "custom-llm")
    set_path(cc, "agent.prompt.custom_llm", {
        "url": url, "model_id": MODEL_ID, "api_key": {"secret_id": secret_id},
        "api_type": "chat_completions"})
    set_path(cc, "agent.prompt.backup_llm_config", {"preference": "disabled"})
    # Privacy: zero retention, no stored audio.
    set_path(ps, "privacy.zero_retention_mode", True)
    set_path(ps, "privacy.record_voice", False)
    # Only the Custom LLM extra body may be overridden by a client (carries session_id).
    for p, v in list(walk(ps.get("overrides", {}), "overrides")):
        if isinstance(v, bool):
            set_path(ps, p, p.rsplit(".", 1)[-1] == "custom_llm_extra_body")
    if not any(p.endswith("custom_llm_extra_body") for p, _ in walk(ps.get("overrides", {}), "overrides")):
        set_path(ps, "overrides.custom_llm_extra_body", True)
    # No file attachments (the backend accepts none).
    for p, v in list(walk(cc)):
        last = p.rsplit(".", 1)[-1]
        if isinstance(v, bool) and "file" in last and ("enable" in last or "allow" in last or last == "enabled"):
            set_path(cc, p, False)

    # The dashboard's "Allow file attachments" defaults to on; the committed config exposes no
    # boolean for it, so try conversation.file_input.enabled and drop it if the API rejects it.
    set_path(cc, "conversation.file_input.enabled", False)
    return new


def send(method, url_, new, label):
    status, body = call(method, url_, new)
    if status == 422 and "file_input" in json.dumps(body):
        print("API rejected file_input.enabled; retrying without it (turn attachments off in the dashboard).")
        new["conversation_config"]["conversation"]["file_input"].pop("enabled", None)
        status, body = call(method, url_, new)
    print(f"{label}: HTTP {status}")
    return status, body


def fix(url, secret_name):
    new = build(url, secret_name)
    cc, ps = new["conversation_config"], new["platform_settings"]
    status, body = send("POST", f"{API}/drafts?branch_id={BRANCH}", new, "POST draft")
    if status != 200:
        print(json.dumps(redact(body), ensure_ascii=False)[:2000])
        sys.exit(1)
    p = new["conversation_config"]["agent"]["prompt"]
    print("Draft saved (not published):")
    print(f"  llm={p['llm']} backup={p['backup_llm_config']} model_id={p['custom_llm']['model_id']}")
    print(f"  url={p['custom_llm']['url']} api_key.secret_id={p['custom_llm']['api_key']['secret_id']}")
    print(f"  zero_retention_mode={ps['privacy']['zero_retention_mode']} record_voice={ps['privacy']['record_voice']}")
    print("Reload the agent in the dashboard.")


def publish(url, secret_name):
    """Commit the intended config as a new version on the branch, WITH authentication on, so only
    signed URLs (created with your API key) can start a conversation."""
    new = build(url, secret_name)
    set_path(new["platform_settings"], "auth.enable_auth", True)
    # ElevenLabs refuses Custom LLM with zero retention (HTTP 400 custom_llm_not_allowed_in_zrm,
    # 20 Nov). Strictest alternative: no stored audio, 1-day retention, then transcript, PII and
    # audio deleted. Documented as a product gap in the policy matrix.
    privacy = new["platform_settings"]["privacy"]
    privacy.update({"zero_retention_mode": False, "record_voice": False, "retention_days": 1,
                    "delete_transcript_and_pii": True, "delete_audio": True})
    status, body = send("PATCH", f"{API}?branch_id={BRANCH}", new, "PATCH agent (commit version)")
    if status != 200:
        print(json.dumps(redact(body), ensure_ascii=False)[:2000])
        sys.exit(1)
    agent = get_agent()
    pr = agent["conversation_config"]["agent"]["prompt"]
    ps = agent["platform_settings"]
    print("Published version now on the branch:")
    print(f"  llm={pr.get('llm')} url={(pr.get('custom_llm') or {}).get('url')} backup={pr.get('backup_llm_config')}")
    print(f"  auth.enable_auth={(ps.get('auth') or {}).get('enable_auth')} "
          f"zero_retention_mode={ps['privacy'].get('zero_retention_mode')} record_voice={ps['privacy'].get('record_voice')}")
    print(f"  retention_days={ps['privacy'].get('retention_days')} "
          f"delete_transcript_and_pii={ps['privacy'].get('delete_transcript_and_pii')} "
          f"delete_audio={ps['privacy'].get('delete_audio')}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "inspect"
    if mode == "inspect":
        inspect()
    elif mode == "fix" and len(sys.argv) == 4:
        fix(sys.argv[2], sys.argv[3])
    elif mode == "publish" and len(sys.argv) == 4:
        publish(sys.argv[2], sys.argv[3])
    else:
        sys.exit("usage: inspect | fix|publish https://<tunnel>.trycloudflare.com/v1 <secret-name>")
