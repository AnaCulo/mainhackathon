# Voice channel (Person C)

**MVP decision (from [policy-matrix.md](../docs/policy-matrix.md#voice-data-processing-decision) and [voice-disclosure.md](../docs/voice-disclosure.md)):**
- **Live caller voice is blocked.** No live microphone, no real phone calls, and no cloned or real voices. Raw audio would reach ElevenLabs before BRANE can protect anything (matrix row "Raw audio, real speaker in MVP → BLOCK").
- **The public entry point plays Version B**, the privacy-first fallback, *locally*, before any microphone, call or ElevenLabs session is opened. It sends people to the text channel.
- **Version A**, recorded voice, is only demonstrated in a **closed test harness**. That means fully generated fictional caller audio, fabricated session details, and the custom-LLM route through BRANE.
- If any part of the voice path can't be verified, demonstrate the text route only.

## End-to-end ElevenLabs call (20 Nov, 20:05)

`voice/elevenlabs_call.py` ran a full call with **generated** caller audio: macOS `say`, fictional lines, no microphone. Evidence: `evidence/elevenlabs_call_20261120-200549.json`, plus the agent's speech in `…_agent.wav`.

The path: ElevenLabs speech-to-text → Custom LLM → tunnel → backend → live BRANE → model → the backend's fixed question → ElevenLabs text-to-speech. Then the trusted-bridge confirmation filed the case.

| Caller (ElevenLabs transcript) | Agent (backend question) |
|---|---|
| Start recorded voice. | What happened? |
| A warehouse emergency exit was blocked with boxes. | What evidence, if any, is available? |
| It happened yesterday in the warehouse. | Who was involved? Roles are enough. |
| I have a photo of it. | Would you like to submit this report for human review? |

Bridge finalize returned HTTP 200 and case `WB-6b3c…`. Brief:
- fact: emergency exit
- timeline: yesterday
- evidence: photo (original held locally)

Backend audit for every turn: BRANE preview clean (each message and combined), completion `Routed-To: cloud`, `Action: allow`, `Redacted: false`, approved model, reply validated, then P6 `HUMAN_ONLY`. The backend had no webhook configured, so the case is stored and its n8n delivery is pending. Run `n8n/demo.sh` for that leg.

Fixes this needed:
- **Publishing:** ElevenLabs refuses **Custom LLM with Zero Retention Mode** (HTTP 400 `custom_llm_not_allowed_in_zrm`). The published version therefore uses the strictest alternative: no stored audio, 1-day retention, then transcript, PII and audio deleted. Authentication is **on** (signed URLs only). **Product gap for the policy matrix:** ElevenLabs holds the transcript for up to a day.
- **Backend:** ElevenLabs' Custom LLM requests include `max_completion_tokens` and `stream_options`. The backend accepts them as ignored compatibility fields; any other unknown field is still rejected.
- **Call client:** it streams like a continuous microphone (silence between lines), so ElevenLabs can detect the end of each turn.
- **Incident:** the first call attempt ran before publishing succeeded and reached ElevenLabs' default agent (DeepSeek, no BRANE). The record is `evidence/elevenlabs_call_20261120-195233.json`. No caller transcript was produced, so no caller text reached that model. The call script now refuses to run unless the published version uses the Custom LLM, the tunnel, disabled backup LLMs and authentication.
- **Recommendation:** turn off ElevenLabs' **Speculative turn**, which is on by default. It sent two early requests on unfinished transcripts, which the backend checked through BRANE and then discarded as `stale_history`.

## ElevenLabs agent repair (20 Nov, 19:45)

After the API key secret was added in the dashboard, the agent's draft had `custom_llm.url: null`. The LLM panel then crashed (`null.matchAll`) and publishing showed "Server URL is invalid".

How it was fixed:
1. [`elevenlabs_fix_llm.py`](elevenlabs_fix_llm.py) wrote the complete intended config as a **server-side draft** (`POST /v1/convai/agents/{id}/drafts`; never published). The person running it supplies their own `ELEVENLABS_API_KEY` in their shell.
2. The dashboard keeps its own draft in browser localStorage (`xi:convai-agent-draft-<agent>-branch-<branch>`), and that copy still had the empty URL. Removing that one cache entry made the dashboard load the server draft.

Verified in the dashboard afterwards:
- the LLM panel opens
- Server URL is the tunnel, model `openrouter:openai/gpt-6-luna`, secret `hotline_llm_key`
- backup LLMs disabled
- Zero Retention on, Store Call Audio off, Text only off, file attachments off
- the only client override is Custom LLM extra body
- the publish button no longer shows an error

The agent is still **unpublished**.

**Quick tunnels expire.** The first one returned "Tunnel not found" after about 40 minutes. After restarting cloudflared, update the URL with:

```bash
python3 voice/elevenlabs_fix_llm.py fix https://<new>.trycloudflare.com/v1 hotline_llm_key
```

Then clear that localStorage entry again if the dashboard still shows the old URL.

## Status (20 Nov, 17:48)

| Part | State |
|---|---|
| Voice path behind ElevenLabs: backend `/v1/chat/completions` (SSE) → live BRANE → model → bridge confirmation → n8n | **Works live.** Run `n8n/demo.sh --voice` to use [`harness.py`](harness.py). Scripted fictional transcript turns stand in for speech-to-text. A 4-turn safety call took 3–4 s per turn, got one fixed question per turn, was finalised by the bridge, and reached the n8n handler (timeline "yesterday", evidence "photo"). A health-data call was held on turn 1 (`restricted_material`, session `held_for_review`). Evidence: `evidence/voice_harness_*.json` |
| Version B entry clip | **Done:** [`version_b_disclosure.m4a`](version_b_disclosure.m4a), 18 s. Generated with macOS `say` from the exact wording in `docs/voice-disclosure.md`. No audio or text left the machine. Re-generate it with an ElevenLabs stock voice if you prefer that sound |
| ElevenLabs agent (job 3) | **Created 20 Nov as an unpublished draft:** `[Culo] Whistleblower intake (synthetic)`, agent ID `agent_5001m7wyb7nbf1x8c7aan33vct1m`. Settings:<ul><li>System prompt and first message: Version A, verbatim</li><li>LLM: Custom LLM, model ID `openrouter:openai/gpt-6-luna`</li><li>Backup LLMs: **disabled**. The default would fall back to ElevenLabs' own models, which breaks P5</li><li>**Zero Retention Mode on**, Store Call Audio off</li></ul>Also set:<ul><li>Allow file attachments: off (the backend accepts no uploads)</li><li>Only one client override allowed, **Custom LLM extra body** (it carries `session_id`). System prompt, LLM and every other override stay locked</li><li>Server URL: a Cloudflare quick tunnel (`cloudflared tunnel --url http://127.0.0.1:8000`, release 2026.10.7, notarised by Cloudflare) pointing at `https://<random>.trycloudflare.com/v1`. Verified through the tunnel: without the key the backend answers 401, with the bridge key a synthetic turn returns its question over SSE via live BRANE</li></ul>The quick-tunnel URL changes every time cloudflared restarts, so update the server URL after a restart. Still open: the API key secret (a team member pastes `ELEVENLABS_BRIDGE_KEY` under Custom LLM → API Key → Add new secret) and, before any public use, **Enable authentication** (Security tab). The dashboard's own test call sends no `elevenlabs_extra_body.session_id`, so the backend rejects it. Use the SDK or a client that sets `customLlmExtraBody`, and generated audio only, never a live microphone. Original instructions: Create the agent from `agent_config.json`, set Custom LLM → backend tunnel `/v1/chat/completions` with the `ELEVENLABS_BRIDGE_KEY` secret, and pass `elevenlabs_extra_body.session_id`. The backend side of this contract is what `harness.py` exercises |

Fixes the live voice run needed:
- BRANE's prompt guard flags the voice system prompt when it's scanned alone. System prompts are now previewed only inside the combined check.
- OpenRouter sends an empty usage chunk after the stop chunk. The stream parser now accepts it, but only when it carries no content.
- The location field was flagged as ADDRESS. Only category and summary now leave the backend.

So ElevenLabs does three jobs here, none of which touch a real caller:

| Job | What | Real caller data? |
|---|---|---|
| 1. Version B prompt | Text-to-speech of the fixed Version B wording. Save the clip and play it **locally** on the entry page | No |
| 2. Fictional caller clips | Generate the "caller" audio for the demo from synthetic reports (T2, T5, E5) with a stock voice | No (synthetic) |
| 3. Version A agent | [`agent_config.json`](agent_config.json), fed only the clips from job 2, LLM = Custom LLM → backend → BRANE | No (closed harness) |

## 1. Get credits
Join the ElevenLabs Discord → `#coupon-codes` → "Start Redemption". Use the email you registered for the hackathon with. Full steps are in `docs/reference/Get-ElevenLabs-Credits.docx`.

## 2. Version B entry prompt (job 1)
Generate this wording, taken verbatim from `voice-disclosure.md`, with a stock voice in the ElevenLabs text-to-speech tool. Save it as `voice/version_b_disclosure.mp3` and play it from the local entry page. **Also display the same text** as the accessible equivalent. The page must not request microphone access or connect to ElevenLabs.

> This is an AI reporting assistant with a computer-generated voice. Please don’t say your report aloud. Voice reporting is turned off because we haven’t verified how the voice service would handle the call. Choose “Report by text” to use the secure text channel.
>
> This is a demonstration. Please use only made-up names and events.

## 3. Fictional caller clips (job 2)
Use text-to-speech with a **stock voice** (never clone a teammate) on the `report` text of the voice cases in [`../data/synthetic_reports.json`](../data/synthetic_reports.json):
- T2 (`channel: voice`)
- T5
- E5, which mimics speech-to-text output

Save the clips locally. Don't use a teammate reading into a real microphone: per `voice-disclosure.md`, that still supplies a real person's voice.

## 4. Version A agent in the closed harness (job 3)
In the ElevenLabs dashboard, create a blank agent with the settings from [`agent_config.json`](agent_config.json). Its wording comes verbatim from `voice-disclosure.md`, so change it there first.
- **LLM:** select **Custom LLM**. ElevenLabs' built-in or auxiliary LLMs must stay off.
  - **Model ID:** `openrouter:openai/gpt-6-luna`
  - **API key:** a workspace secret named `hotline_llm_key`
- **Privacy:** turn off audio storage and set the shortest retention the dashboard allows ([ElevenLabs retention controls](https://elevenlabs.io/docs/eleven-agents/customization/privacy/retention)). Write down exactly which settings this tenant offers for Person A.
- **Custom LLM URL.** ElevenLabs needs an OpenAI-compatible `/v1/chat/completions` endpoint that streams SSE. We checked on 20 Nov that BRANE streams correctly.

| Stage | Server URL |
|---|---|
| Final / demo | `https://<tunnel>/v1/chat/completions`, i.e. Person B's backend (applies P1–P5 locally, then BRANE) |
| Early check only | `https://brane.ai-z.io/api/v1/chat/completions` with the team key. This skips the backend's local stripping, mapping and P5, so **never for the demo** |

  Expose the backend with `cloudflared tunnel --url http://localhost:8000` or `ngrok http 8000`.
- **Feeding clips.** Play the generated clips into the agent's test conversation. Don't use a live microphone with a real person speaking. If the dashboard can't accept generated audio without a live mic, demonstrate the text route instead, as the matrix says.

## Stop conditions to demonstrate (from the wiring table in voice-disclosure.md)
- **The caller asks to stop recording.** The agent says the stop line and ends the session.
- **The model or gateway fails mid-session.** The backend returns an error and the agent stops. Never fall back to an unfiltered transcript or another LLM (P5).
- **The choice is ambiguous or times out.** The microphone stays off.
