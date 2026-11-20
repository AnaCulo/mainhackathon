# Hotline API · synthetic demo

Use a trusted server-side caller. The backend returns a generated X-Request-ID and Cache-Control: no-store. OpenAPI schemas are available at `/openapi.json`. Send JSON bodies with Content-Type: application/json.

## POST /reports

Authenticate with `Authorization: Bearer <BACKEND_API_KEY>`. Optional `Idempotency-Key: <UUID>` deduplicates a submission. Use the same key and payload after a timeout. A changed payload with the same key returns 409.

```json
{"text":"A warehouse emergency exit was blocked with boxes.","reporter_mode":"anonymous","source":"text"}
```

Text is required, nonblank and at most 16,000 characters. Source defaults to text. Reporter mode is anonymous (default) or confidential. Optional local identity declarations use `"identities":[{"kind":"person","aliases":["李明","Ming"]}]`. Group only aliases of the same person. Kind can also be reporter. Unobserved aliases produce no claimed occurrence or person. The application accepts no file uploads.

**200 and n8n body.** This response was captured from the local HTTP smoke test with simulated upstreams.

```json
{
  "case_id": "WB-bee888852c1446f59aa7d2faf640c0db",
  "reporter": "REPORTER_01",
  "category": "safety",
  "summary": "The reporter describes an emergency exit blocked by boxes.",
  "persons": [],
  "received_at": "2026-11-20T15:42:15.715093Z",
  "decisions": [
    {"policy":"P5","action":"ALLOW","count":null},
    {"policy":"P6","action":"HUMAN_ONLY","count":null}
  ],
  "brane_status": "ok"
}
```

Case IDs are opaque strings. Category is one of fraud, harassment, corruption, safety, discrimination or other. Time is UTC at intake. Persons are case-scoped pseudonyms. The reporter token designates the role even for anonymous intake. P1/P2 PROTECT counts reflect local occurrences. Full source-level evidence lives in audit_events. The case remains awaiting human review even when a webhook succeeds.

## POST /v1/chat/completions

Use `Authorization: Bearer <ELEVENLABS_BRIDGE_KEY>`. Select the custom Chat Completions API with streaming. Send a unique per-conversation UUID in the custom body and a complete user history with exactly one new turn each time. On transport retry send the same history. Unsupported tools, models, content parts and unknown fields are rejected. Optional temperature, top_p, max_tokens, user and user_id are accepted as compatibility fields and do not override server policy. System and assistant strings in inbound messages never provide trusted instructions or consent.

```json
{
  "model":"openrouter:openai/gpt-6-luna",
  "stream":true,
  "messages":[{"role":"user","content":"A warehouse emergency exit was blocked with boxes."}],
  "elevenlabs_extra_body":{"session_id":"dd49ad82-062a-4ddb-b931-e67bebbb8ba4"}
}
```

Successful response has Content-Type: text/event-stream and X-Session-Revision. Example SSE frames:

```text
data: {"id":"chatcmpl-example","object":"chat.completion.chunk","created":1795186800,"model":"openrouter:openai/gpt-6-luna","choices":[{"index":0,"delta":{"role":"assistant","content":"When did this happen, roughly?"},"finish_reason":null}]}

data: {"id":"chatcmpl-example","object":"chat.completion.chunk","created":1795186800,"model":"openrouter:openai/gpt-6-luna","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

Before the first emitted chunk the backend can return a normal JSON error. No provider failover occurs. A disconnected stream may end before [DONE].

## Voice confirmation

Use the voice bearer for both routes. GET `/voice/sessions/{uuid}` returns e.g. `{"revision":2,"state":"open"}`. A trusted bridge reads the current revision, presents the report for review using its approved local flow, and captures explicit confirmation for that specific revision. POST `/voice/sessions/{uuid}/finalize` with `{"confirmed":true,"revision":2}`. Successful finalization returns the same Case JSON as /reports. Submitting the same confirmed revision again returns the same case. An unknown/stale revision, quarantined session or subsequent edit to a frozen session fails. The final extraction gets its own governed request.

## Health, delivery and errors

- GET `/health` is public. Example fresh start: `{"backend":"up","ready":false,"brane_configured":false,"brane_last_check":"unknown"}`. Readiness uses the last observed governed operation; this endpoint sends no report or probe.
- POST `/deliveries/retry` uses the backend bearer, takes no body and returns `{"deliveries":{"WB-…":"delivered"}}` or an empty map. Webhook requests use Bearer N8N_WEBHOOK_SECRET and Idempotency-Key equal to case_id.
- 400 means unsupported model, 401 an invalid credential, 409 a revision/key conflict, 413 an oversized body and 422 an invalid request or policy refusal. 502 means invalid or unsafe model output. 503 means configuration, transport or enforcement could not be verified.
- Policy and validation failures use `{"error":"<safe_code>","request_id":"<uuid>"}`. Authentication uses the framework's detail field. Oversized bodies receive `{"error":"request_too_large"}`. Never echo private values in an incident ticket.
