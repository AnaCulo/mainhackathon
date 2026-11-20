# Protected case workflow

## Run the presenter

Use the checkout or extract the working-agent ZIP. Install Node 24, npm and Python 3.13. In a private virtual environment, run `python -m pip install -r backend/requirements.txt` from the repository root. Set `PYTHON` to that interpreter if it is outside PATH. The first launch installs n8n 2.48.7 in the user's temp directory. Use a private, unsynced temp directory on this machine.

Put the following settings in the backend's private environment or secret store. For a private file, set `DEMO_BACKEND_ENV` to its absolute path. The existing `backend/.env` is also supported. Process environment values take precedence.

| Setting | Presenter value |
| --- | --- |
| `BRANE_API_KEY` | Team key from the private access email, used as the hosted bearer |
| `BRANE_POLICY_SHA256` | SHA-256 of the team's reviewed, approved tenant policy. Compare against the reviewed export before the demo. The backend verifies the pin on every request. |
| `BRANE_BASE_URL` | `https://brane.ai-z.io/api/v1` (default and only approved origin) |
| `BRANE_MODEL` | `openrouter:openai/gpt-6-luna` (default and only approved model) |
| `BRANE_TIMEOUT_SECONDS` | Optional total gateway deadline, default 30 seconds |

On Windows run:

```powershell
$env:DEMO_BACKEND_ENV = "$env:LOCALAPPDATA\whistleblower.env"
.\n8n\demo.ps1 -Hold
```

On macOS or Linux run:

```sh
export DEMO_BACKEND_ENV="$HOME/.config/culo/whistleblower.env"
./n8n/demo.sh --hold
```

When injecting deployment secrets directly, omit the file setting. Both launchers run `n8n/demo.py`. It starts a fresh, loopback-only n8n instance, imports and activates the protected-case workflow, starts the register and serves the presenter from `app.demo:create_demo`. It generates the intake bearer, storage key, handler password and webhook credentials for this instance. Only the intake backend receives the BRANE credential among the services. `BRANE_TOKEN`, `BRANE_CHECK_URL` and `BRANE_CHAT_URL` belong to the separate Node loopback adapter.

Open the printed **Submit** URL (normally http://127.0.0.1:8000/demo), or follow **Submit a synthetic report** on the handler queue at http://127.0.0.1:8788/review. Use `handler` and the generated `HANDLER_PASSWORD` from the indicated private file. Default ports are 8000 for intake, 5689 for n8n, 5679 for its task broker and 8788 for review. Add `-Isolated` or `--isolated` to use fresh ports alongside a running demo. Press Enter in the launcher to stop this instance.

### Synthetic smoke test

Enter “Two invoice totals differ. The discrepancy appeared on Thursday. The ledger has both entries.” Click **Prepare case for review**. On success the form shows a grounded summary, request ID and a link to that case. Open it and check the reported fact, Thursday timeline, ledger evidence and **Human decision · pending**. A designated handler records the decision. For an unattended submission through this same form, omit the hold flag. `-Trace` or `--trace` also submits the form and prints the receipt while holding on a successful run.

To inspect a manual submission, run the following with the printed private config path and the request ID from the screen. The trace joins the backend audit, outbox and register, and writes a content-free JSON receipt to the private case directory. The source fingerprint identifies the actual launcher and backend even for an uncommitted checkout or archive.

```sh
python n8n/live-trace.py <private-demo.env> --request-id <uuid>
```

A refusal or local hold shows **Submission failed** with HTTP 422. Missing credentials or policy pin, unavailable catalog or protection check, timeout, or unverifiable route give 503. An unusable model answer or unconfirmed webhook gives 502. BRANE failures create no successful workflow delivery. A webhook failure after a validated completion may leave a pending outbox entry. After a timeout during completion, upstream execution is unknown. The trace distinguishes an attempted completion from a validated result.

For a failure smoke, start a separate isolated instance with `BRANE_API_KEY` empty, submit a fresh permitted report and verify 503, zero completion attempts, zero delivery attempts and an empty queue. Never change the shared tenant policy to simulate an outage. The recorded open-policy baseline failed protection tests. Use only permitted synthetic controls until the current policy and release behavior are independently verified.

### Explicit offline tests

`-Offline` or `--offline` selects the original fixed-report walkthrough on its disposable default ports. It uses simulated BRANE and a real local n8n workflow. Run `node --test n8n/register.test.mjs backend/intake.test.mjs` and, from `backend/`, `python -m pytest -q` for the contract and presenter regressions. Set `N8N_PACKAGE` to an installed n8n 2.48.7 package directory to include the default-launcher regression. It starts a real, isolated n8n instance and submits the presenter form without a team key. The Unix options `--python` and `--voice` also run the historical report suite or the closed voice harness against the governed backend on the default ports.

## Import into an existing local instance

1. Use a restricted project on self-hosted n8n 2.48.7. Bind to loopback. The HTTP Request nodes target fixed loopback register endpoints. History settings in the export disable manual, successful, failed and progress payload retention. Set the matching instance execution settings as in demo.ps1. Keep telemetry, request-body logging, proxy body logging and pinned data off.
2. Import **protected-case.json**. Create Header Auth credentials named **Protected intake** and **Local dispatcher**, each with header name `Authorization`. Set values to `Bearer <N8N_TOKEN>` and `Bearer <WORKER_TOKEN>` respectively. Assign the first to the webhook and commit nodes and the second to the dispatch node. Use different randomly generated secrets and a separate handler password. The export holds descriptive credential references only.
3. Create a project Data Table with string columns `case_id` and `received_at`. Restrict table access. Set TABLE_ID, N8N_ORIGIN and TABLE_API_KEY (row create/read) for the register. Table insertion records only the case reference and receipt. n8n project access can include administrators. Keep protected narrative and approval reasons in the separate restricted register. [n8n Data Tables](https://docs.n8n.io/data/data-tables/)
4. Set CASE_DIR to a private unsynced directory. Set HANDLER_REF to the designated synthetic handler and HANDLER_PASSWORD to its unique password. Place settings in a private environment file, then run `node --env-file=<private-file> n8n/service.mjs`. The service binds to 127.0.0.1:8788. SQLite creates its tables automatically. Keep n8n, the register and the identity store under separate service identities for any deployment. This demo runs as the local user.
5. Publish the workflow. Use the **production** POST path `/webhook/protected-case`, with the chosen n8n origin, in Person B’s N8N_WEBHOOK_URL. Node uses N8N_TOKEN and Python uses N8N_WEBHOOK_SECRET for the same bearer. The raw JSON body must be the case. Set `Idempotency-Key` to its exact ID. The Node sender permits loopback HTTP. The Python branch’s normal deployment config requires a verified HTTPS endpoint. Its local compatibility test forwards through a test transport.
6. Set DEMO_CLOCK=1 **only** for synthetic cases. This opt-in is saved when each case is first accepted. Previously accepted cases retain their original settings. Prepare a synthetic return route by exact case ID using SYNTHETIC_MAILBOX_CASES, or run `node --env-file=<private-file> n8n/service.mjs route <case-id>` after receipt. It explicitly binds a case-scoped test mailbox. With no route, the dispatcher records unreachable. The reporter token never resolves to a destination. The designated email channel is captured locally at an .invalid address. Neither adapter sends external messages.
7. The explicitly selected offline walkthrough uses the fixed synthetic report on disposable ports. The presenter form is available through the launch commands above. To inspect actual dispatches locally, use `node --env-file=<private-file> n8n/service.mjs inbox <case-id>`.

## Persistence, failure and permissions

The SQLite register's primary key is the opaque case ID. One immediate transaction commits its immutable protected fields, digest, receipt, task ID, designated actor and outbox intents. A new case returns 201, an identical replay returns 200, and reuse with different protected content returns 409. Acceptance completes before the scheduler runs. Storage errors fail the handoff. A lost response can be retried with the same payload and idempotency key.

The workflow’s scheduler drains durable work after acceptance. Each (case, event) has a unique key. A local inbox receipt and its sent state commit together. A known capture failure becomes failed and leaves other work runnable. The Data Table is a downstream index. Its asynchronous network write is durably claimed first. An ambiguous outcome stays uncertain even after restart. Stop the affected worker, inspect the table by case ID and verify the provider’s outcome. An authorised local operator can use `node --env-file=<private-file> n8n/service.mjs reconcile <case-id> table sent` for a confirmed row, or `… reconcile <case-id> table pending` after confirming absence and no in-flight write. For a failed local capture, fix the storage problem and reconcile the event to pending. No automatic resend occurs on uncertainty. The restricted history table records transitions.

Receipt times come from B. Seven days excludes the Amsterdam receipt day. Feedback is due three calendar months after acknowledgement dispatch, or from expiry of the initial seven days if no acknowledgement was sent. The operational target moves to the previous working day on weekends and listed Dutch holidays. The calendar covers 2026–27. Other years are flagged for verification. No statutory extension is applied. A late dispatch preserves missed flags and the original no-ack date. A human decision leaves the feedback timer open until separate feedback dispatch. [Dutch public holidays](https://www.government.nl/themes/work/working-hours/question-and-answer/work/public-holidays-in-the-netherlands)

The local form is the equivalent P6 approval surface. Authenticated requests must match the assigned actor, task, case, purpose and 15-minute ticket. A handler may leave an item pending and reopen a fresh form. Mutual exclusion is enforced in the register. Escalation records the choice locally. Handler authentication and self-attestation are demo controls. A conflicted handler must abstain. A deployed employer needs independent alternate assignment, access to lawful original evidence, correction and appeal procedures, identity management and a separately approved protected mailbox. Normal email carries a reference and protected-review route only. Real reporter feedback needs a protected return channel.

No AI node, model key, caller contact, identity map, raw audio or transcript is required. The schema validates release metadata and persisted field shapes. Semantic screening of free text is upstream. Only the known synthetic fixture should be exercised until the team verifies the live policy. A trusted sender reporting a false positive protection verdict cannot be detected reliably from JSON.

