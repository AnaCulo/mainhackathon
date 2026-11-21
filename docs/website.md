# Demo website: Anonymous Whistleblower Intake Hotline

A local page served by the Python backend at **http://127.0.0.1:8000/**. The left side is the reporter. The right side is a live "behind the scenes" panel showing every protection step for each message.

## Run it

Full chain, with n8n delivery and the handler page:

```bash
PATH="/opt/homebrew/opt/node@24/bin:$PATH" PYTHON=backend/.venv/bin/python n8n/demo.sh --python --hold
```

Then open http://127.0.0.1:8000/. Submitted cases go to the n8n handler at http://127.0.0.1:8788/review.

Backend only, without n8n (cases stay "pending delivery"):

```bash
cd backend && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Push-to-talk uses local speech-to-text, which `backend/requirements.txt` installs. The launcher checks it at start and prints the fix if something is missing. If Talk mode says speech-to-text cannot start, the hint under the button names the cause:
- **not installed:** run `python -m pip install -r backend/requirements.txt`
- **could not start (Windows):** install the Microsoft Visual C++ Redistributable (x64)
- **model unavailable:** the first use needs internet to download the model

The first time, the backend downloads the Whisper `small.en` model, about 480 MB, into `~/.cache/huggingface`. After that it runs offline. The model is preloaded in the background when the page opens. For speed over accuracy, set `STT_MODEL=base.en`.

**Speech-to-text quality (20 Nov).** Benchmark on generated workplace sentences in various voices:
- `small.en` with beam 5 and workplace hotwords: **1.3 % word error**, about 1.1 s per utterance
- `base.en`: 2.9 % (e.g. "harassed" heard as "Harris the")
- A lone acronym such as "CEO." is misheard by every model ("see ya"). Inside a sentence it is recognised.

The biggest problem was in the browser. Requesting the microphone on each press cut off the first word (with 0.3 s clipped, "Our CFO skipped…" became "CFO Skip…", and "CEO." became "you"). The page now opens the microphone once when Talk is selected and keeps a rolling 0.5 s pre-roll **in the tab's memory only**. It records 0.3 s past the release and sends 16 kHz WAV with noise suppression to 127.0.0.1. The microphone closes when you switch back to typing. The reporter always sees the text and can correct it before sending.

## Two ways to report

| Mode | Path | What leaves this machine |
|---|---|---|
| **Send messages** (typed) | browser → backend on 127.0.0.1 → screening → BRANE → model → fixed question | Only the protected outbound text shown in the panel |
| **Talk** (hold the button or the space bar) | browser mic → audio to 127.0.0.1 only → **local Whisper** → text appears in the box for the reporter to check → same path as typed | **No audio.** The recording is deleted right after transcription |
| Agent voice ("Speak replies") | pre-generated clips of the fixed questions and notice (`backend/app/static/voice/`) | Nothing at runtime |

The agent's spoken lines are fixed server-owned text, so no reporter data can reach a text-to-speech service. The clips are made with macOS `say`. `python3 voice/make_voice_clips.py` regenerates them with the agent's ElevenLabs voice using your own key; that sends only those fixed lines.

ElevenLabs therefore never hears the reporter. This "local ears, ElevenLabs mouth" design replaces the hosted ElevenLabs agent for live use, which Ana's matrix blocked because cloud speech-to-text hears raw audio before BRANE. The disclosure text on the page is a **draft for Ana**, because the previous Version A text described cloud speech-to-text.

## What the panel shows per message

1. Typed on this device, or speech-to-text on this device (engine, seconds of audio, time taken, recording deleted)
2. Received; P1/P2 names replaced with case tokens (counts only); or **stopped locally** with the reason (P3 sensitive or criminal content, P4 instructions, P5 checks)
3. BRANE team policy verified (fingerprint)
4. BRANE preview clean (each message plus the combined conversation)
5. **Sent to BRANE:** the exact protected JSON, meaning fixed sentences and `#P01` tokens, none of the original wording
6. BRANE decision headers (route, action, redacted, model)
7. Model reply checked against the allowed questions, and the reply sent to the reporter
8. On submit: reporter confirmation (P6), draft checked, case created, human-only decision, n8n delivery

The panel is built from the backend's own audit log for that request. It never shows the original report text.

## Safety of the page itself

- The page and every `/ui/*` endpoint answer **only on loopback** (`127.0.0.1` with a local Host header) and **only when `APP_ENV=development`**.
- Requests through the Cloudflare tunnel or any proxy get 404. The tunnel only serves the ElevenLabs Custom LLM endpoint, which needs the bridge key.
- The UI calls the same protected routes as everything else (`/v1/chat/completions`, voice finalize) internally, with server-held credentials. The browser never sees a key.
- Tests: `backend/tests/test_ui.py`.
