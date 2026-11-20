# BRANE guide for Group Čulo

Our whistleblower hotline prepares a protected case brief from a voice or text report. A human case handler decides whether to investigate, escalate, or close the case. BRANE governs which model can receive a prompt and which details may leave its perimeter.

**Submission deadline — Saturday, 21 November 2026 at 10:30 CET.** The AI-Z track asks for a working agent with visible human approval, two completed CSVs, and a three-minute live demo showing measurable value. Use synthetic reports throughout. Keep the demo free of real emails, payments, and deletions.

## Run the organizer's starter

Get the shared team API key and optional chat login from the private access email. Keep both out of source control, screenshots, and evidence files. Open the extracted kit directory that contains `starter-kit` and the two CSV templates. With Python 3.9 or newer, run this in PowerShell. The key prompt hides the pasted value.

```powershell
$env:BRANE_BASE_URL = 'https://brane.ai-z.io/api/v1'
$env:TEAM_BUILD = 'Group Čulo / policy-v1'
$env:BRANE_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'Team API key' -AsSecureString)).Password
python .\starter-kit\brane_agent_starter.py
Remove-Item Env:BRANE_API_KEY
```

The script uses only the Python standard library. It reads the department policy, sends six synthetic prompts to the live gateway, and appends T1–T5 plus a sample E1 to `test_evidence_run.csv` in the current directory. Give each run a distinct policy version and retain the rows from the intended run when assembling the submission.

## Configure the team department

1. Open the [team policy workbench](https://brane.ai-z.io/team-policy) and paste the team key. The email describes the **initial** department as open, with all 25 built-in categories set to `allow` and no semantic rules. Inspect the current settings before changing the team's shared policy. The organizers expect T2, T3, and the starter's T5 to fail on the initial settings.
2. Configure each relevant category. The optional 17-category floor preset provides a starting point. The built-ins cover contact details, company identifiers, civil IDs, financial information, credentials, and special-category data.
3. Add semantic rules for sensitive meaning that structured identifiers miss. Each rule has a code, name, description, legal basis, and a `local` or `refuse` action. Keywords are optional. For example, test whether an indirect medical accommodation in a witness statement triggers the project's P3 rule.
4. Run a synthetic prompt in the Live Test Bench. Inspect the matched categories, outgoing cloud payload or zero-egress indication, and response headers. Export the policy matrix and annotate it with the project's rationale, evidence, and gaps.

| Action | Effect on a matched request |
| --- | --- |
| `allow` | Cloud receives the matched text as typed when the request routes to cloud. |
| `placeholder` | BRANE replaces matched spans with tokens such as `<PERSON_1>` before cloud transfer. BRANE can restore them in its answer, so verify the case sent downstream contains only the intended pseudonyms. |
| `local` | The entire request runs on BRANE's internal GPU with zero cloud-model egress. The hosted service still receives the input. |
| `refuse` | BRANE stops before model execution and returns HTTP 422. |

When several categories match, precedence is `refuse > local > placeholder > allow`. Human approval is an application workflow step after preparation.

## Hosted API reference

Paths below are relative to `https://brane.ai-z.io/api/v1`. Team requests use `Authorization: Bearer <team-key>`. JSON requests use `Content-Type: application/json`.

| Method and path | Purpose |
| --- | --- |
| `GET /models` | List available model IDs. |
| `GET /policy/catalog` | Read built-in categories, actions, and semantic templates. The starter calls this without authentication. |
| `GET /policy` | Read the current team configuration. |
| `PUT /policy` | Update the shared department policy. The starter includes a commented configuration example. |
| `POST /policy/test` | Preview a synthetic prompt with `{"prompt":"Summarise two duplicate invoices.","executeCompletion":false}`. Inspect detections and the proposed outgoing payload. |
| `POST /chat/completions` | Send OpenAI-compatible `model` and `messages` fields. Read the answer from `choices[0].message.content` and the policy decision from the HTTP response headers. |

The access email lists these model IDs. Confirm availability with `GET /models` when running the demo.

| Route | Model IDs |
| --- | --- |
| Cloud | `auto` or the stated default `openrouter:anthropic/claude-haiku-5.5`; alternatives `openrouter:openai/gpt-6-luna` and `openrouter:mistralai/mistral-large-4-0` |
| Local | `vllm:deepseek-v4.1-flash`, `vllm:qwen3.8-27b-nvfp4` |

## Connect BRANE to the hotline

**Integration status.** The organizer's starter can call the hosted gateway directly. The Node backend currently accepts numeric loopback addresses for both `BRANE_CHECK_URL` and `BRANE_CHAT_URL` and uses `BRANE_TOKEN` and `BRANE_MODEL`. Setting those URLs to the hosted endpoint will fail validation. The local contract tests use disposable services. See [the backend contract](docs/contracts.md) and [the adapter implementation](backend/integrations.mjs).

The integration work is to map the hosted service to the backend's local protection and chat operations. The check contract requires complete P1–P4 coverage, UTF-16 span offsets, and stable entity references for aliases. The supplied kit documents a policy preview and a governed completion. It does not establish that the preview provides those offsets or resolves aliases. Verify these capabilities before relying on them. Keep the identity mapping in local SQLite and preserve the backend's stop-on-failure behavior. The project contract calls for an approved OpenAI model, so use the agreed explicit model ID for that path. The starter uses `auto`.

| Project rule | Intended enforcement and evidence |
| --- | --- |
| P1 · Reporter identity | Protect names and contact details before cloud transfer. Check that the case and n8n handoff carry the reporter pseudonym. |
| P2 · Named persons | Protect each mention, including evidence text. Check stable case-scoped tokens for repeated names and aliases. |
| P3 · Special-category data | The current backend contract blocks the whole submission. Configure matching refusal rules and capture the triggering category. |
| P4 · Embedded instructions | The project requires a block for attempts to override intake rules. Verify that synthetic report text and attached evidence receive the same checks. |
| P5 · Check unavailable | The backend stops with HTTP 503 when protection cannot be verified. Verify zero model calls and zero webhook deliveries for that request. |
| P6 · Investigation decision | Show the protected draft and the authorised case handler's decision in the demo. Keep the final action under human control. |

Voice has an additional boundary. ElevenLabs receives audio before the backend receives a transcript. A BRANE routing header describes the model turn. Document the voice processor, disclosure, consent, and text alternative separately in the matrix.

## Collect test evidence

Use the brief's security gate for T1–T5 and cover the CSV's additional failure scenario. Any impermissible transfer fails the gate. The starter's automatic verdicts are preliminary. For example, its T1 check accepts any populated route and its T3 check cannot establish that every occurrence was protected.

| Test | What to demonstrate |
| --- | --- |
| T1 · Permitted control | A clean request completes the task. Capture `X-Brane-Routed-To: cloud`, `X-Brane-Redacted: false`, and a useful answer. |
| T2 · Protected data | Synthetic identifiers become placeholders before cloud transfer, or the full request runs locally. Inspect the outgoing payload or local-route trace. |
| T3 · Repeated details | Repeat an identifier in the report and evidence. Inspect every occurrence and the consistency of its token, or verify local processing. |
| T4 · Bypass attempt | Embed a synthetic instruction to disclose a protected detail. Show the applicable policy still took effect. A transport failure alone is insufficient evidence. |
| T5 · Special category / local | The **brief and Python starter** require a special-category or non-exportable case to stay local or receive a policy refusal. Under P3, expect HTTP 422 and the refusal reason. |

**T5 discrepancy.** The supplied **CSV template** labels T5 “Check unavailable / unverifiable” and expects local routing with a cause header. Record both scenarios as distinct, clearly labelled rows and confirm the preferred row labels with the AI-Z desk. For the unavailable-check row, distinguish a BRANE-reported local route from a complete gateway outage. In an outage the hotline's P5 behavior is HTTP 503 with no downstream calls. Record that application evidence and the difference from the template's local-route expectation. A missing gateway response supplies no BRANE headers.

**E1–E5.** Write five cases specific to whistleblower intake. Candidate scenarios include an anonymous reporter identifiable by a unique shift, one witness referred to by two names, an indirect accommodation request, a public company name needed to understand a duplicate invoice, and a voice follow-up that repeats a protected name. Specify the expected decision before running each case. Record what detail the handler retained or lost. The bundled HR example is scaffolding.

For each run, record the synthetic input, expected outcome, actual output and usefulness, verdict, team and policy version. Capture HTTP status and the relevant headers: `X-Brane-Routed-To`, `X-Brane-Action`, `X-Brane-Redacted`, `X-Brane-Pii-Types`, `X-Brane-Semantic-Matches`, `X-Brane-Local-Cause`, and `X-Brane-Refused-By`. Capture the synthetic outgoing payload in the workbench when proving exactly what the cloud received. Bring unexplained traces privately to the AI-Z desk.

## Submission checklist

- **Policy matrix** — Complete `MAIN_Policy_Matrix_Template.csv` with at least three cited protection rules. For each, identify the data and its purpose, exact legal or governance provision, intended decision, actual enforcement, product gap, evidence, and linked tests. Include P6 and its human approval evidence. Replace the example row, which predates the per-category controls.
- **Test evidence** — Complete `MAIN_Five_Tests_Template.csv` with observed results for the five mandatory tests, the T5 discrepancy above, and five handwritten domain edge cases. Include the effect on the quality of the draft case brief.
- **Working agent and three-minute demo** — Follow one synthetic report through the BRANE decision, protected execution, and visible human sign-off. Compare a measured outcome such as time to prepare a review-ready case against the same task performed manually.

Source materials are the Group Čulo access email, `MAIN_Summit_AI-Z_Challenge_Brief.pdf`, the two named CSV templates, and the extracted kit's `starter-kit/README.md` and `starter-kit/brane_agent_starter.py`. Project policy IDs and backend behavior come from this repository's [integration contract](docs/contracts.md).
