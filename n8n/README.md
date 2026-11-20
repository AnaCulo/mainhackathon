# Protected case workflow

## Reproduce the demo

On Windows with Node 24 and npm, extract the working-agent ZIP or use this checkout. From its root run:

```powershell
.\n8n\demo.ps1 -Hold
```

The first run installs n8n 2.48.7 in the user's temp directory. It needs npm network access and free loopback ports 5689 and 8788. A fresh private n8n profile receives two random Header Auth credentials, the imported and published workflow and a Data Table. A second local service owns the transaction register and authorised form. The command runs the synthetic smoke and leaves its main case pending for a person. Open **http://127.0.0.1:8788/review** and select the case ID printed by the command. Log in as `handler` using HANDLER_PASSWORD in the indicated private demo.env. Keep the password off screen. Select an action, supply the reason and affirm no conflict. Leave feedback unapproved to see the two-minute reminder. Refresh the form after the next 15-second tick. Press Enter in the terminal to stop the two listeners. Local profiles, captures and credentials stay in the private temp directory for inspection.

```powershell
.\n8n\demo.ps1
node --test n8n/register.test.mjs backend/intake.test.mjs
```

The first command exercises and stops a fresh instance, including all three human choices via scripted form submissions. The second checks boundary cases. To verify the published Python variant separately, use CPython 3.13+ on Windows and install its requirements in a disposable environment and add `-PythonBackend <path-to-3c7dda9/backend> -PythonExecutable <path-to-python>` to the first command.

## Import into an existing local instance

1. Use a restricted project on self-hosted n8n 2.48.7. Bind to loopback. The HTTP Request nodes target fixed loopback register endpoints. History settings in the export disable manual, successful, failed and progress payload retention. Set the matching instance execution settings as in demo.ps1. Keep telemetry, request-body logging, proxy body logging and pinned data off.
2. Import **protected-case.json**. Create Header Auth credentials named **Protected intake** and **Local dispatcher**, each with header name `Authorization`. Set values to `Bearer <N8N_TOKEN>` and `Bearer <WORKER_TOKEN>` respectively. Assign the first to the webhook and commit nodes and the second to the dispatch node. Use different randomly generated secrets and a separate handler password. The export holds descriptive credential references only.
3. Create a project Data Table with string columns `case_id` and `received_at`. Restrict table access. Set TABLE_ID, N8N_ORIGIN and TABLE_API_KEY (row create/read) for the register. Table insertion records only the case reference and receipt. n8n project access can include administrators. Keep protected narrative and approval reasons in the separate restricted register. [n8n Data Tables](https://docs.n8n.io/data/data-tables/)
4. Set CASE_DIR to a private unsynced directory. Set HANDLER_REF to the designated synthetic handler and HANDLER_PASSWORD to its unique password. Place settings in a private environment file, then run `node --env-file=<private-file> n8n/service.mjs`. The service binds to 127.0.0.1:8788. SQLite creates its tables automatically. Keep n8n, the register and the identity store under separate service identities for any deployment. This demo runs as the local user.
5. Publish the workflow. Use the **production** POST path `/webhook/protected-case`, with the chosen n8n origin, in Person B’s N8N_WEBHOOK_URL. Node uses N8N_TOKEN and Python uses N8N_WEBHOOK_SECRET for the same bearer. The raw JSON body must be the case. Set `Idempotency-Key` to its exact ID. The Node sender permits loopback HTTP. The Python branch’s normal deployment config requires a verified HTTPS endpoint. Its local compatibility test forwards through a test transport.
6. Set DEMO_CLOCK=1 **only** for synthetic cases. This opt-in is saved when each case is first accepted. Previously accepted cases retain their original settings. Prepare a synthetic return route by exact case ID using SYNTHETIC_MAILBOX_CASES, or run `node --env-file=<private-file> n8n/service.mjs route <case-id>` after receipt. It explicitly binds a case-scoped test mailbox. With no route, the dispatcher records unreachable. The reporter token never resolves to a destination. The designated email channel is captured locally at an .invalid address. Neither adapter sends external messages.
7. With the private demo config loaded, `node --env-file=<private-file> n8n/walkthrough.mjs --hold` runs the same synthetic entry points on the disposable ports. To inspect actual dispatches locally, use `node --env-file=<private-file> n8n/service.mjs inbox <case-id>`.

## Persistence, failure and permissions

The SQLite register's primary key is the opaque case ID. One immediate transaction commits its immutable protected fields, digest, receipt, task ID, designated actor and outbox intents. A new case returns 201, an identical replay returns 200, and reuse with different protected content returns 409. Acceptance completes before the scheduler runs. Storage errors fail the handoff. A lost response can be retried with the same payload and idempotency key.

The workflow’s scheduler drains durable work after acceptance. Each (case, event) has a unique key. A local inbox receipt and its sent state commit together. A known capture failure becomes failed and leaves other work runnable. The Data Table is a downstream index. Its asynchronous network write is durably claimed first. An ambiguous outcome stays uncertain even after restart. Stop the affected worker, inspect the table by case ID and verify the provider’s outcome. An authorised local operator can use `node --env-file=<private-file> n8n/service.mjs reconcile <case-id> table sent` for a confirmed row, or `… reconcile <case-id> table pending` after confirming absence and no in-flight write. For a failed local capture, fix the storage problem and reconcile the event to pending. No automatic resend occurs on uncertainty. The restricted history table records transitions.

Receipt times come from B. Seven days excludes the Amsterdam receipt day. Feedback is due three calendar months after acknowledgement dispatch, or from expiry of the initial seven days if no acknowledgement was sent. The operational target moves to the previous working day on weekends and listed Dutch holidays. The calendar covers 2026–27. Other years are flagged for verification. No statutory extension is applied. A late dispatch preserves missed flags and the original no-ack date. A human decision leaves the feedback timer open until separate feedback dispatch. [Dutch public holidays](https://www.government.nl/themes/work/working-hours/question-and-answer/work/public-holidays-in-the-netherlands)

The local form is the equivalent P6 approval surface. Authenticated requests must match the assigned actor, task, case, purpose and 15-minute ticket. A handler may leave an item pending and reopen a fresh form. Mutual exclusion is enforced in the register. Escalation records the choice locally. Handler authentication and self-attestation are demo controls. A conflicted handler must abstain. A deployed employer needs independent alternate assignment, access to lawful original evidence, correction and appeal procedures, identity management and a separately approved protected mailbox. Normal email carries a reference and protected-review route only. Real reporter feedback needs a protected return channel.

No AI node, model key, caller contact, identity map, raw audio or transcript is required. The schema validates release metadata and persisted field shapes. Semantic screening of free text is upstream. Only the known synthetic fixture should be exercised until the team verifies the live policy. A trusted sender reporting a false positive protection verdict cannot be detected reliably from JSON.

