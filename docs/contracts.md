# Whistleblower intake integration

The [presenter launchers](../n8n/README.md) use the Python intake handler and its hosted BRANE adapter. The contract below describes the separate Node implementation. Use synthetic reports throughout the hackathon. Person B's service runs as a single Node 24 process. Run the contract tests from the repository root with `node --test legacy/node-adapter/intake.test.mjs`. They start disposable HTTP services on loopback and use in-memory SQLite. They exercise the application boundaries. The team still needs to run Person C's protocol against the actual BRANE deployment.

## Running the backend

Copy the settings from `.env.example` to a private environment file outside the synced checkout. Set a dedicated intake token for the callers, both local BRANE endpoints, the approved OpenAI model alias, and Person D's n8n webhook. Supply upstream credentials as required by each service. In PowerShell, start the backend with the path to that file.

```powershell
node --env-file="$env:LOCALAPPDATA\whistleblower.env" legacy/node-adapter/server.mjs
```

The server listens on 127.0.0.1:8000. Identity mappings are scoped to the case ID and stored in SQLite under the user's local application data directory. Keep the database and its journals on a private, unsynced volume. Each request emits a JSON log with a server-generated request ID, route, status, outcome and decision counts. The same request ID is returned in the response headers.

## Text intake and n8n

Send `POST /reports` with a bearer intake token, JSON content type and an optional client-generated `Idempotency-Key`. Supply a report in `text` and optional plain-text `evidence`. Both go through the same protection check before model inference.

```json
{"text":"Two identical invoices were paid on Monday.","evidence":"The synthetic ledger contains two matching entries."}
```

On success the HTTP response and n8n webhook contain the same case. The stable fields are `case_id` (an opaque WB-prefixed UUID), `reporter`, `category`, `summary`, `persons`, `received_at` (UTC), `decisions`, and `brane_status`. Additional fields are `acknowledgement` and `brief`, with arrays of protected source sentences for facts, timeline and evidence. The model selects categories and sentence indices. Only a human decides what action to take.

The backend returns 422 for a policy block, 503 for a failed protection check or unusable model result, and 502 for an unconfirmed webhook delivery. After a delivery failure, retry the same body with the same idempotency key. The backend saves the case before delivery and sends the case ID as the webhook idempotency key. Person D's workflow must deduplicate by case ID before notifications or other side effects, including when its response was lost. Callers should generate the intake key before the first request so they can recover after a lost response.

## Voice handoff for Person C

Configure the Custom LLM to reach `POST /v1/chat/completions` through the backend tunnel, authenticate with the intake token and disable alternate model routing. Set Person A's disclosure as the agent's opening message. The backend uses its own intake questions and accepts user turns as plain text. It supports ordinary Chat Completions JSON and SSE with a terminal `[DONE]` event. [ElevenLabs Custom LLM documentation](https://elevenlabs.io/docs/eleven-agents/customization/llm/custom-llm)

Pass an opaque, unique per-call ID as `elevenlabs_extra_body.conversation_id`. Send the full turn history. Voice intake asks for explicit submission. Saying “submit my report” immediately after the confirmation prompt files the case through the same path as text intake. Ordinary turns do not create a case. The call ID makes repeated final requests return the existing case.

## BRANE handoff for AI-Z and Person A

The challenge brief describes enforcement behavior. The following two operations form the Node loopback adapter contract. The hosted interface is documented in [BRANE.md](../BRANE.md). A hosted policy preview supplies routing predictions and cannot establish local P1–P4 span coverage. Configure the approved OpenAI deployment and P1–P5 in BRANE before running live tests.

| Policy | Required behavior |
| --- | --- |
| P1 | Identify each occurrence of reporter identity and contact details. Assign REPORTER_01. |
| P2 | Identify each named person, including repeated references. Assign a stable PERSON token within each case. |
| P3 | Block the whole submission on special-category data under the draft policy. |
| P4 | Block embedded attempts to override intake rules, including in evidence. |
| P5 | Stop if required checks are incomplete or unavailable. |
| P6 | Route the protected case to a human for the investigation decision. |

1. The local check operation receives `{text, policies}`. It must inspect the full text locally, without external inference, and report every sensitive span. A successful result contains `complete: true`, `checked: ["P1","P2","P3","P4"]`, and `findings`. Each finding includes `policy`, zero-based inclusive `start`, and exclusive `end` in UTF-16 code units. For P2, provide a stable `entity` string for aliases of the same person. An empty findings array means all checks completed and found nothing. Detection of unmarked identifiers and paraphrased instructions depends on this component.
2. The local chat operation receives OpenAI-compatible Chat Completions requests with a server-selected model. BRANE must enforce the approved policy profile on every request and route only to the approved OpenAI model. Disable raw input logging and identity restoration in model responses. The backend only accepts structured selections and constructs user-visible content from protected source sentences and fixed prompts.

Both configured BRANE URLs must use a numeric loopback host. The backend refuses redirects and has no direct OpenAI client. The presenter uses the Python local screener and case-scoped mapping before any hosted preview. Its adapter authenticates with BRANE_API_KEY, confirms the approved OpenAI model via GET /models, checks the reviewed policy and verifies the governed completion before releasing the case.

### Held intake receipts

A policy hold returns HTTP 202. An unverifiable automated check retains its 5xx status.
Both return a case ID and receipt. The encrypted original remains on the intake host.
Reusing the idempotency key replays the receipt for either kind and retries a pending
handoff. A duplicate never restarts automated processing. Older held records without
receipts acquire one when the same report and key are submitted again.
The register receives only the case ID, fixed reporter token, receipt time, hold status,
reason code, policy and two decisions. Its acknowledgement and feedback clocks run from
receipt under the same rules as an ordinary case. Check the register for actual delivery.
