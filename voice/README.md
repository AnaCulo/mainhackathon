# Voice channel: ElevenLabs agent setup (Person C)

The hotline's phone and voice channel is an ElevenLabs Agent. ElevenLabs only does speech-to-text and text-to-speech. **Every model turn goes through our own LLM endpoint, and from there through BRANE.** The agent must never use ElevenLabs' built-in LLMs, because that would send the report to a model outside BRANE.

```
Caller ─► ElevenLabs (STT) ─► Custom LLM URL ─► backend /v1/chat/completions ─► BRANE ─► model
       ◄─ ElevenLabs (TTS) ◄──────────────────────────── streamed answer (SSE) ◄─┘
```

## 1. Get credits
Join the ElevenLabs Discord → `#coupon-codes` → "Start Redemption". Use the email you registered for the hackathon with. Full steps are in `docs/reference/Get-ElevenLabs-Credits.docx`. Every team member has to do this themselves.

## 2. Create the agent
In the ElevenLabs dashboard, create a blank agent. Copy the settings from [`agent_config.json`](agent_config.json):
- **First message:** the AI disclosure plus consent text (EU AI Act Art. 50, Whistleblower Directive Art. 18). It is a draft: Person A signs off the final wording.
- **System prompt:** copy the `prompt` text.
- **LLM:** select **Custom LLM**:
  - **Server URL:** see step 3
  - **Model ID:** `openrouter:openai/gpt-6-luna`
  - **API key:** a workspace secret named `hotline_llm_key`. Never paste the key into the repo.
- **Privacy:** turn off audio storage and set conversation retention to the shortest period the dashboard allows. Write down which settings were available, because Person A needs them for the policy matrix (ElevenLabs as processor under GDPR Art. 28).

## 3. Point the Custom LLM at the right URL

ElevenLabs needs an **OpenAI-compatible `/v1/chat/completions` endpoint that streams SSE**. We checked on 20 Nov that BRANE streams correctly with `"stream": true`.

| Stage | Server URL | API key secret |
|---|---|---|
| **Final / demo** | `https://<tunnel>/v1/chat/completions`, i.e. Person B's backend exposed through a tunnel | the backend's token |
| Early voice testing, before the backend exists | `https://brane.ai-z.io/api/v1/chat/completions` | the BRANE team key |

The early option is still governed by BRANE. However, it skips the backend's pseudonym mapping, logging, P5 fail-closed check and n8n handoff, so **do not use it for the demo**.

Expose the local backend with a tunnel:
```bash
cloudflared tunnel --url http://localhost:8000
```
or `ngrok http 8000`. Then paste the printed `https://…` URL plus `/v1/chat/completions` into the agent.

## 4. Test the call
1. Use the dashboard's test button and read one of the voice cases from [`../data/synthetic_reports.json`](../data/synthetic_reports.json) (T2, T5 or E5) aloud.
2. Check BRANE's decision in the backend log or the `X-Brane-*` headers.
3. Check that no real names come back in the spoken summary.

Synthetic voices and names only.

## Legal points for the policy matrix (hand to Person A)
- ElevenLabs receives **raw audio before BRANE sees anything**. BRANE cannot protect speech-to-text. Mitigations:
  - The prompt never asks for identity, and the opening message says a name is not needed.
  - Short or no retention, under a processor agreement (Art. 28).
  - A written text channel is offered as an alternative.
- Directive Art. 18(2): a recording or transcript of a phone report needs the reporter's consent. That is why the first message asks for it.
- AI Act Art. 50(1): callers must be told they are talking to an AI. The first message does this.
