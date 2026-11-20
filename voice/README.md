# Voice channel (Person C)

**MVP decision (from [policy-matrix.md](../docs/policy-matrix.md#voice-data-processing-decision) and [voice-disclosure.md](../docs/voice-disclosure.md)):**
- **Live caller voice is blocked.** No live microphone, no real phone calls, and no cloned or real voices. Raw audio would reach ElevenLabs before BRANE can protect anything (matrix row "Raw audio, real speaker in MVP → BLOCK").
- **The public entry point plays Version B**, the privacy-first fallback, *locally*, before any microphone, call or ElevenLabs session is opened. It sends people to the text channel.
- **Version A**, recorded voice, is only demonstrated in a **closed test harness**. That means fully generated fictional caller audio, fabricated session details, and the custom-LLM route through BRANE.
- If any part of the voice path can't be verified, demonstrate the text route only.

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
