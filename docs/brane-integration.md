# BRANE integration and evidence

## What the checkout establishes

The team guide documents the hosted base URL, bearer authentication, the approved OpenAI model, the team policy endpoint, the non-executing preview and governed completions. The original evidence file records actual header names, preview fields and an all-allow baseline. Its injection example shows a preview/live discrepancy. That historical run used a different client and policy. It cannot establish successful protection by this backend. [Team BRANE guide](../BRANE.md) · [Baseline test protocol](test-protocol.md)

## Deployment and verification

1. Obtain the team key privately. Configure the team department in the organisers' workbench with Person A. Review structured identifiers, repeated references, person-linked allegations, indirect identifiers, special categories and instruction handling. The backend reads the tenant policy and never modifies it.
2. Check the workbench against the synthetic fixtures, including all five repeated names and a sensitive case. Verify the actual governed route, approved model, payload/zero egress, blocking semantics and any restoration on return. Resolve discrepancies with the organisers. Verify that the policy cannot be weakened during a run and that completion enforcement applies to all messages. An exported policy digest detects later changes but cannot prove the rules are sufficient.
3. In `backend/.env`, set the team key and approved model. Run `python scripts/policy_fingerprint.py` and compare its canonical GET /policy fingerprint with the reviewed export. Set BRANE_POLICY_SHA256 only for that reviewed configuration. If vendor responses contain volatile fields, pin validation will stop the request. Resolve this with the organisers before enabling release.
4. Run `RUN_LIVE_BRANE=1 python -m pytest -q -s tests/test_live_brane.py` from `backend/`. It sends the screened synthetic control through the actual adapter, validates the completion headers and schema, and prints the backend request ID. Use the workbench to inspect execution and correlate with the tenant's records. A second opt-in calibration sends a fixed synthetic mailbox twice to the non-executing preview and checks the reported protection, local route or refusal. The rich safety test also requests a live synthesis and validates its chosen IDs and grounded summary. A preview does not establish what a completion actually transmitted.
5. Use the normal API and the same synthetic T1–T5 fixtures. Preserve local audit records, tenant traces and actual outbound evidence independently. Confirm the appropriate policy decision on the tenant for each case. For P4/P3 cases held before BRANE, the application audit should show no completion attempt. Person C and D should verify a real voice call and webhook separately.

## Transfer boundary

The matrix treats hosted BRANE as external. The application holds raw reports, identity declarations and transcript history in its own environment. The closed vocabulary creates a new data object from a bounded package of typed facts, permitted question IDs and case pseudonyms. A name detector is only an indexing aid. Unrecognised narrative fragments never become outbound strings. This makes the summary less specific. A human with authority can consult the encrypted original locally. Case-scoped mappings cover only identities recognised or explicitly declared locally. They support local review. The adapter neither assumes nor accesses a hosted mapping vault. [Team policy matrix](policy-matrix.md)

For each model request the adapter performs the following operations against the fixed HTTPS origin under `/api/v1`. Redirects, environment proxy discovery and provider fallback are disabled.

| Operation | Release condition | Failure behavior |
| --- | --- | --- |
| GET /policy | Reviewed digest, recognised summary, semantic rules active, local/refuse controls enabled | Reject before completion |
| POST /policy/test for each exact message body with executeCompletion=false | Clean cloud preview, identical outgoing preview text, empty category and semantic matches, negative injection flag | Withhold on a different route, detection, missing field or altered payload |
| POST /chat/completions | Fixed model ID and server-constructed messages only | One attempt. No direct provider request, retry or alternate model |
| Read completion headers | X-Brane-Routed-To=cloud, Action=allow, Redacted=false, Pii-Detected=false, Model-Resolved matches the exact approved model, Lane=governed | Reject the result and suppress release |
| Validate output | A strict fact-ID plan selecting only approved material, or an approved voice question. Voice requires a complete, stopped SSE response ending in [DONE] | Return a content-free error, no unvalidated answer or handoff |

Here `allow` applies to the **already screened** candidate. This implementation withholds candidates that still require hosted redaction or local rerouting. The service does not make use of restored identity values. It buffers upstream voice content, validates the full question, then emits downstream SSE. Added latency is the cost of inspecting the answer before the voice platform speaks it.

## Interpreting the record

- The backend generates X-Request-ID, attaches it to each BRANE request, and records it locally. When a verified response includes an identifier-shaped upstream X-Request-ID, the adapter also retains that value. The docs supplied to the team do not guarantee upstream correlation, atomic policy pinning, persisted model-bound payloads or a request-level audit retrieval endpoint.
- `local` events include the application policy revision, case-local pseudonym counts, refusals, human-review status and replay. Compact P1/P2 counts are observed local matches. P5 ALLOW represents acceptance of BRANE's verified result. P6 HUMAN_ONLY is a workflow restriction. A null count means unavailable or inapplicable. BRANE supplies no verified per-occurrence count in the documented completion headers.
- `gateway` events reflect verified policy fingerprints, previews, refusal responses and actual completion headers. A preview is a prediction and is evaluated per message. It is not a capture of final assembled model input. No endpoint is claimed to expose a live OpenAI-bound payload to this backend.
- `transport/completion_attempted` records the attempt before network I/O. A timeout after that point leaves model execution unknown. An error before that point means the backend made zero completion attempts. Receiving invalid completion headers prevents downstream release. It cannot undo a transfer already made by the gateway.
- `model` events indicate that a returned extraction or question passed the local schema and grounding rules. Outbox records track n8n delivery independently.
- Restrict access to the audit database. Application errors and audit metadata omit original report text and arbitrary upstream error bodies. Inspect individual traces using the SQL in the backend README.

## Open items for the demo

Supply the team key, approved policy export/fingerprint and current tenant traces. Verify preview and completion agreement under the governed policy, including streaming headers, across the actual model configuration. Identify the tenant's supported request correlation or ask the organisers for a trace. Validate Person A's final matrix and storage/voice conditions. Existing mock tests exercise the transport and safety logic without claiming live cloud behavior.
