#!/usr/bin/env python3
"""Regenerate the website's agent voice clips with the ElevenLabs voice of the hotline agent.

Only the fixed, server-owned lines in backend/app/static/voice/lines.json are sent to
ElevenLabs text-to-speech (the disclosure and the six intake questions). No reporter data is ever
sent: at runtime the website only plays these pre-generated files.

Run yourself, with your own key in the environment (never in chat):
  read -s ELEVENLABS_API_KEY && export ELEVENLABS_API_KEY
  python3 voice/make_voice_clips.py
Without this script the website uses the macOS-voice clips already in the folder.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backend" / "app" / "static" / "voice"
AGENT = "agent_5001m7wyb7nbf1x8c7aan33vct1m"
KEY = os.environ.get("ELEVENLABS_API_KEY") or sys.exit("Set ELEVENLABS_API_KEY in your own shell first.")


def request(method, url, body=None, accept="application/json"):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None)
    req.add_header("xi-api-key", KEY)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", accept)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


agent = json.loads(request("GET", f"https://api.elevenlabs.io/v1/convai/agents/{AGENT}"))
voice_id = os.environ.get("ELEVENLABS_VOICE_ID") or agent["conversation_config"]["tts"]["voice_id"]
lines = json.loads((OUT / "lines.json").read_text(encoding="utf-8"))
for name, text in lines.items():
    try:
        audio = request("POST", f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128",
                        {"text": text, "model_id": "eleven_multilingual_v2"}, accept="audio/mpeg")
    except urllib.error.HTTPError as e:
        sys.exit(f"{name}: HTTP {e.code}")
    (OUT / f"{name}.mp3").write_bytes(audio)
    print(f"{name}.mp3  {len(audio)} bytes")
print("Done. The website now prefers these .mp3 clips over the .m4a fallbacks.")
