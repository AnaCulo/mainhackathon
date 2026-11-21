#!/usr/bin/env python3
"""End-to-end ElevenLabs call with GENERATED audio (no microphone, no real voice).

Path: macOS `say` (fictional caller lines) -> ElevenLabs agent (speech-to-text, WebSocket)
-> Custom LLM -> tunnel -> backend /v1/chat/completions -> live BRANE -> model -> one server-owned
question -> ElevenLabs text-to-speech. Afterwards the script acts as the trusted bridge: it reads
the session revision and finalizes it, which files the case (n8n delivery if the backend has a
webhook configured).

Run in your own terminal, with your ElevenLabs API key in the environment (never in chat):
  read -s ELEVENLABS_API_KEY && export ELEVENLABS_API_KEY
  <python with websockets> voice/elevenlabs_call.py

Requires: the agent published with authentication on (voice/elevenlabs_fix_llm.py publish), the
backend on 127.0.0.1:8000 and the tunnel up. Writes evidence/elevenlabs_call_<ts>.json and the
agent's speech as evidence/elevenlabs_call_<ts>_agent.wav. No keys are written.
"""
import asyncio
import base64
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
import wave
from datetime import datetime
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parent.parent
AGENT = "agent_5001m7wyb7nbf1x8c7aan33vct1m"
BRANCH = "agtbrch_1901m7wyb8kre1zb880xtxs6aywv"
BACKEND = "http://127.0.0.1:8000"
TURNS = [  # fictional caller, synthetic report only
    "Start recorded voice.",
    "A warehouse emergency exit was blocked with boxes.",
    "It happened yesterday, in the warehouse.",
    "I have a photo of it.",
]
KEY = os.environ.get("ELEVENLABS_API_KEY") or sys.exit("Set ELEVENLABS_API_KEY in your own shell first.")


def env(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def http(method, url, headers, body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None)
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except ValueError:
            return e.code, None


def synth(text, workdir):
    """Fictional caller line -> 16 kHz mono 16-bit PCM bytes, generated locally with macOS say."""
    aiff, wav = workdir / f"{uuid.uuid4().hex}.aiff", workdir / f"{uuid.uuid4().hex}.wav"
    subprocess.run(["say", "-v", "Samantha", "-o", str(aiff), text], check=True)
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(aiff), str(wav)], check=True)
    with wave.open(str(wav)) as w:
        return w.readframes(w.getnframes())


def require_safe_published_version():
    """Refuse to call unless the version conversations will run is ours: Custom LLM -> tunnel,
    no backup LLMs, authentication on. Otherwise ElevenLabs would run its own model outside BRANE."""
    status, agent = http("GET", f"https://api.elevenlabs.io/v1/convai/agents/{AGENT}?branch_id={BRANCH}",
                         {"xi-api-key": KEY})
    if status != 200:
        sys.exit(f"Could not read the agent: HTTP {status}")
    prompt = agent["conversation_config"]["agent"]["prompt"]
    url = (prompt.get("custom_llm") or {}).get("url") or ""
    problems = []
    if prompt.get("llm") != "custom-llm":
        problems.append(f"published LLM is {prompt.get('llm')!r}, not custom-llm")
    if ".trycloudflare.com/" not in url:
        problems.append("published Custom LLM URL is not the backend tunnel")
    if (prompt.get("backup_llm_config") or {}).get("preference") != "disabled":
        problems.append("backup LLMs are not disabled")
    if not ((agent.get("platform_settings") or {}).get("auth") or {}).get("enable_auth"):
        problems.append("authentication is off")
    if problems:
        sys.exit("Refusing to call, the published version is not safe: " + "; ".join(problems)
                 + ". Run voice/elevenlabs_fix_llm.py publish first.")


async def call():
    require_safe_published_version()
    status, body = http("GET", f"https://api.elevenlabs.io/v1/convai/conversation/get-signed-url"
                               f"?agent_id={AGENT}&branch_id={BRANCH}", {"xi-api-key": KEY})
    if status != 200:
        sys.exit(f"Signed URL failed: HTTP {status} {json.dumps(body)[:300]}")
    signed_url = body["signed_url"]
    session_id = str(uuid.uuid4())
    log, agent_audio, meta = [], bytearray(), {}
    responses = asyncio.Queue()

    with tempfile.TemporaryDirectory() as tmp:
        clips = [synth(t, Path(tmp)) for t in TURNS]

    async with websockets.connect(signed_url, max_size=None) as ws:
        await ws.send(json.dumps({"type": "conversation_initiation_client_data",
                                  "custom_llm_extra_body": {"session_id": session_id}}))
        loop = asyncio.get_running_loop()
        playback = {"bytes": 0, "rate": 16000, "first": None}  # simulated speaker playback of agent audio
        speaking = asyncio.Queue()  # caller clips waiting to be "spoken" into the mic

        async def receive():
            async for raw in ws:
                ev = json.loads(raw)
                kind = ev.get("type")
                if kind == "ping":
                    await ws.send(json.dumps({"type": "pong", "event_id": ev["ping_event"]["event_id"]}))
                elif kind == "conversation_initiation_metadata":
                    meta.update(ev["conversation_initiation_metadata_event"])
                    fmt = meta.get("agent_output_audio_format", "pcm_16000")
                    if fmt.startswith("pcm_"):
                        playback["rate"] = int(fmt.split("_")[1])
                elif kind == "audio":
                    chunk = base64.b64decode(ev["audio_event"]["audio_base_64"])
                    agent_audio.extend(chunk)
                    playback["first"] = playback["first"] or loop.time()
                    playback["bytes"] += len(chunk)
                elif kind == "user_transcript":
                    text = ev["user_transcription_event"]["user_transcript"]
                    log.append({"caller_transcript": text})
                    print(f"  caller (STT): {text}")
                elif kind == "agent_response":
                    text = ev["agent_response_event"]["agent_response"]
                    log.append({"agent": text})
                    print(f"  agent: {text[:110]}{'…' if len(text) > 110 else ''}")
                    await responses.put(text)

        async def microphone():
            """Like a real mic: a continuous 16 kHz stream, silence unless a clip is being spoken."""
            silence = bytes(3200)  # 100 ms
            clip, pos = None, 0
            while True:
                if clip is None and not speaking.empty():
                    clip, pos = speaking.get_nowait(), 0
                if clip is not None:
                    frame, pos = clip[pos:pos + 3200], pos + 3200
                    if pos >= len(clip):
                        clip = None
                else:
                    frame = silence
                await ws.send(json.dumps({"user_audio_chunk": base64.b64encode(frame).decode()}))
                await asyncio.sleep(0.1)

        async def until_agent_finished_speaking():
            """Wait until the agent's audio would have finished playing on a speaker."""
            while True:
                if playback["first"] is not None:
                    end = playback["first"] + playback["bytes"] / (2 * playback["rate"])
                    if loop.time() >= end + 0.8:
                        return
                await asyncio.sleep(0.2)

        receiver = asyncio.create_task(receive())
        mic = asyncio.create_task(microphone())
        try:
            await asyncio.wait_for(responses.get(), 90)  # the first message (disclosure)
            for clip in clips:
                await until_agent_finished_speaking()
                await speaking.put(clip)
                try:
                    await asyncio.wait_for(responses.get(), 60)
                except asyncio.TimeoutError:
                    log.append({"error": "no agent response within 60 s"})
                    print("  (no agent response within 60 s)")
                    break
            await until_agent_finished_speaking()
        finally:
            mic.cancel()
            receiver.cancel()
    return session_id, meta, log, bytes(agent_audio)


def finalize(session_id):
    """Trusted-bridge step: read the revision, confirm explicitly, file the case."""
    bridge = {"Authorization": "Bearer " + env(ROOT / "backend" / ".env")["ELEVENLABS_BRIDGE_KEY"],
              "Content-Type": "application/json"}
    status, st = http("GET", f"{BACKEND}/voice/sessions/{session_id}", bridge)
    if status != 200:
        return {"session_status": status, "detail": st}
    status, case = http("POST", f"{BACKEND}/voice/sessions/{session_id}/finalize",
                        bridge, {"confirmed": True, "revision": st["revision"]})
    return {"session": st, "finalize_status": status, "case": case}


def main():
    print(f"Calling agent {AGENT} with generated audio…")
    session_id, meta, log, audio = asyncio.run(call())
    result = finalize(session_id)
    print(f"Finalize: {json.dumps(result)[:400]}")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = ROOT / "evidence" / f"elevenlabs_call_{stamp}.json"
    out.write_text(json.dumps({
        "note": "Generated caller audio (macOS say), synthetic report. ElevenLabs STT/TTS, backend + live BRANE.",
        "agent_id": AGENT, "conversation_id": meta.get("conversation_id"), "session_id": session_id,
        "caller_lines_spoken": TURNS, "events": log, "bridge_finalize": result}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    fmt = meta.get("agent_output_audio_format", "pcm_16000")
    if audio and fmt.startswith("pcm_"):
        with wave.open(str(out.with_name(out.stem + "_agent.wav")), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(int(fmt.split("_")[1]))
            w.writeframes(audio)
    print(f"Evidence: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
