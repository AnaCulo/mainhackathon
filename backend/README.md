# Whistleblower intake backend

A synthetic text or voice report becomes a protected draft for a human case handler. The service stores the original locally, builds a constrained factual extract, checks the team's policy and both message bodies at BRANE, and requests a governed completion. It releases a validated case to the caller and a durable n8n outbox. There is no model tool with authority to investigate, substantiate or close a case.

## Run locally

From the repository root, use Python 3.13 on Windows for the local encrypted evidence store. The presenter setup also uses Python 3.13.

```sh
cd backend
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --only-binary=:all: -r requirements.txt
python scripts/init_demo.py
uvicorn app.main:app --reload --no-access-log
```

The initialization script creates a private, git-ignored `.env` with separate random intake, voice and encryption keys. Keep the storage key with the database for restarts. Swagger is at <http://127.0.0.1:8000/docs>. The public health endpoint works before the BRANE team key is installed. Model requests return a content-free 503 until the tenant is configured.

## Exercise the whole flow without vendor accounts

```sh
python -m pytest -q
python scripts/smoke_test.py
```

The smoke test starts Uvicorn on an ephemeral loopback port with a temporary encrypted-evidence database. It posts a report, checks the webhook body, consumes a voice stream and confirms a second case. Only the upstream transports are simulated. Its printed JSON includes a real case ID and receipt time from that run. The test doubles are in `tests/doubles.py`. The service entry point always constructs the hosted BRANE client.

## Configuration

| Setting | Purpose |
| --- | --- |
| BRANE_BASE_URL | Verified hosted API root, `https://brane.ai-z.io/api/v1` |
| BRANE_API_KEY | Team bearer credential from the organisers |
| BRANE_MODEL | Approved explicit ID, `openrouter:openai/gpt-6-luna` |
| BRANE_TIMEOUT_SECONDS | Total budget per preflight plus completion, default 30 seconds |
| BRANE_POLICY_SHA256 | Digest of the reviewed team's GET /policy JSON. Any change blocks completions pending review |
| DATABASE_URL | File URL such as `sqlite:///./whistleblower.db`. Use a private directory with an existing parent |
| STORAGE_KEY | Fernet key. Protect separately from backups and retain for the lifetime of the database |
| BACKEND_API_KEY | Bearer secret for a trusted text intake service and delivery retries. Keep it out of public client code |
| ELEVENLABS_BRIDGE_KEY | Separate voice bridge bearer credential |
| N8N_WEBHOOK_URL, N8N_WEBHOOK_SECRET | HTTPS destination and bearer secret. An empty URL leaves cases pending |
| APP_ENV | Deployment label, default development. Changing the label does not enable real-person intake |

Prepare the team policy and review the workbench with Person A before pinning its fingerprint. The adapter never edits the shared policy. See [BRANE setup and evidence](../docs/brane-integration.md).

## Send a synthetic report

From `backend/`, with the virtual environment active, export the server credentials in your local shell. The example reads the intake key without printing it.

```sh
export BACKEND_API_KEY="$(python -c 'from dotenv import dotenv_values; print(dotenv_values(".env")["BACKEND_API_KEY"])')"
curl -sS http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/reports \
  -H "Authorization: Bearer $BACKEND_API_KEY" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: fd1af813-406e-4bef-9937-ecdd4aeb3fee' \
  -d '{"text":"A warehouse emergency exit was blocked with boxes.","reporter_mode":"anonymous","source":"text"}'
```

Generate a fresh UUID for each distinct submission and reuse it on retries. Processing records the first receipt before contacting BRANE. A blocked report is held locally for human review. Correlate the response's X-Request-ID with local audit events. A retry of the same input/key reuses the receipt. Another active attempt returns 409. A crashed attempt's reservation expires after five minutes.

## Person C · ElevenLabs

Configure the synthetic agent's Custom LLM with Chat Completions, the approved model ID, the backend HTTPS endpoint ending in `/v1/chat/completions`, and a secret containing ELEVENLABS_BRIDGE_KEY. Disable tools, alternative LLMs, cascading, reasoning and post-call AI summarisation. Use synthetic audio and the team's disclosure before connecting. ElevenLabs receives audio at the speech boundary.

The bridge must supply a fresh, opaque UUID per conversation through the custom body parameter `elevenlabs_extra_body.session_id`. Include complete, append-only user history on every request. The response streams a screened question after verification. The bridge can read the revision header or fetch session status. After independently capturing the reporter's affirmative submission decision for that revision, the trusted bridge calls the finalization endpoint. Ordinary chat, the model, and an end-call event cannot authorize submission. Person C needs to wire that confirmation in the client or bridge and verify body propagation on the tenant. See the [wire contract](../docs/backend-api.md) and [ElevenLabs Custom LLM documentation](https://elevenlabs.io/docs/eleven-agents/customization/llm/custom-llm).

## Person D · n8n

Create an authenticated POST webhook, configure both N8N settings and upsert by case_id with a unique constraint. Acknowledge with 2xx once durable. The body is exactly the public Case JSON. The Idempotency-Key header equals case_id. The handler uses received_at to calculate deadlines and routes to a human. Response bodies are ignored. A network error, non-2xx or missing URL leaves delivery pending. To retry up to 20 pending or expired entries per call, invoke this from a trusted scheduler:

```sh
curl -X POST -H "Authorization: Bearer $BACKEND_API_KEY" http://127.0.0.1:8000/deliveries/retry
```

Delivery is at least once. A lost acknowledgement can cause the same case to be posted again. Keep retry credentials server-side. Originals and mappings are accessible only on the database host.

## Data, audit and scope

Tables include cases, identity_mappings, sessions, outbox and audit_events. Originals, detailed extracts, alias values and raw voice histories are encrypted. SQLite metadata, timestamps, pseudonyms, delivery state and protected summaries are readable to database users. The database file is created mode 0600. SQLite and a local key file are a hackathon storage choice. Set retention, deletion, separate key custody, operator access, notification controls and a human reporting channel before any deployment involving people. A blocked receipt still needs local human follow-up.

Inspect a synthetic run on the host using the returned request ID:

```sql
SELECT timestamp, source, policy_id, action, count, model_route, success, metadata
FROM audit_events WHERE request_id = :request_id ORDER BY event_id;
SELECT case_id, state, attempts, updated_at FROM outbox;
```

Local facts are deliberately coarse. The extractor admits configured topics and safe observation patterns, broad place/time hints, evidence types and limited identity introductions. Trusted callers can supply Unicode aliases. Unrecognised free text stays in encrypted evidence. A supported ordinary purchase-approval allegation can appear under a case token. Exact contact details, rare roles and arbitrary model prose are excluded from shared summaries. A report without a recognised independent topic is held locally with HTTP 422. A generic draft can require substantial manual reconstruction. Automatic identification and sensitive-category recognition have limited coverage. The protected vocabulary is the egress control even when recognition misses something.

The backend contains no human decision endpoint. The open item goes to Person D's authorised workflow. Person A must approve local retention, the release vocabulary, the final policy matrix, tenant settings and the synthetic voice workflow. The live BRANE test is opt-in. ElevenLabs and n8n tenant operation remain separate integration checks.

### Reviewing an incomplete report

The optional [text clarification endpoint](../docs/backend-api.md#post-reportsclarify) uses the same local gap checks as the voice bridge. For a synthetic demo, start with “I was told that the emergency exit was blocked by boxes.” Add “It happened yesterday. I have a photo.” and review the questions again. On submission, supported descriptions can distinguish what the reporter observed, heard or suspected. The model selects and orders released observations. The handler sees an unverified account and the types of evidence mentioned. Intake accepts text and has no attachment custody mechanism.

The local extraction version is `synthetic-intake-4`. It recognises bounded English constructions, including a duplicate invoice posting and a named actor directly linked to a purchase approval. Incidental witnesses and mentions of an approval requirement cannot supply the actor or establish a missing approval. Broad topic matches can still produce a generic draft. Recognised P3/P4 content is held before a hosted call. All mandatory previews, including the combined conversation, must report a clean cloud route and return the exact submitted preview text. A missing, truncated or changed preview stops the request before completion.

The submission archives and previously captured live timings describe earlier code. Run the changed release vocabulary and exact combined-preview check against the approved tenant before packaging new live results.
