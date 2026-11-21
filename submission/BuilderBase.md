# BuilderBase hand-in · Group Čulo

**Entry title** — A confidential reporting channel with human follow-up  
**Track** — AI-Z Secure Enterprise AI Challenge  
**Team** — Group Čulo  
**Status** — Friday rough package prepared. BuilderBase upload and confirmation pending.

## Submission text

A worker who spots a discrepancy needs a safe way to report it and a person who will follow up. Čulo prepares a protected case for an independent handler at a Dutch employer. The handler sees the reported facts, timeline and evidence, chooses whether to investigate, close or escalate, and separately approves feedback. The workflow records actual acknowledgement and delivery results and tracks both statutory clocks.

Our synthetic demonstration follows a single ledger discrepancy from text intake, through the hosted BRANE gateway with our policy-v2 and the approved cloud model, to a published n8n webhook, durable register, local reporter mailbox, designated handler email capture and human approval form. The current backend exports allowlisted fact descriptors and question IDs, with case-scoped person tokens. BRANE previewed them with zero detections and returned cloud, allow, not redacted. In four live runs the handler could open a brief with fact, timeline, evidence and a pending decision after 6.2–7.6 seconds. Earlier fixture-only runs took 86–179 ms. Eight concurrent first deliveries created one case. The protected return route and email delivery were local captures.

The team’s open-policy baseline exposed failures on protected details, repeated identifiers, embedded instructions and special-category data. The submission preserves those observations next to the live policy-v2 results:
- the bypass attempt is refused before any model runs
- health data stays local
- five mentions of one person become one token
- an ordinary purchasing breach reaches the cloud as PERSON_01, while a forgery allegation stays local

On the current build, a local hold returns 202. Automation failures retain 5xx. Both register content-free held receipts. Current live evidence for this build is listed in [Evidence status](EVIDENCE_STATUS.md), including the failures we disclose. Older files record earlier builds. A closed voice harness ran the same path live through the voice bridge contract, and an end-to-end ElevenLabs call with generated caller audio passed through ElevenLabs speech recognition, our backend and live BRANE, then filed a case for the handler. ElevenLabs refuses Custom LLM with zero retention, so the published agent keeps transcripts for at most one day. That is why live caller audio stays blocked: the call used generated audio only, and the retention is a product gap that blocks live use ([legal summary](../docs/legal-summary.md)). Final team review and the manual timing comparison are pending.

## Assets to attach

| Item | Hand-in copy | Status |
|---|---|---|
| Working agent and source | [Working agent ZIP](working-agent.zip) | The live Python backend (`backend/app`, used for every live BRANE result), the historical recording adapter in `legacy/node-adapter/`, workflow export, BRANE policy-as-code, setup, tests, legal and voice materials. Start the presenter with `n8n/demo.sh --hold` or `.\n8n\demo.ps1 -Hold` and open http://127.0.0.1:8000/. The private configuration and smoke test are in n8n/README.md. |
| Business case | [Dutch employer business case](../docs/business-case.md) | Sourced pricing and market bands, buyer economics, live and fixture timings, and the manual exercise (`tests/manual_benchmark.py`). |
| Editable pitch | [PowerPoint deck](../pitch/Culo-pitch.pptx) | Six rendered slides and speaker notes. |
| Demo video | [Playable MP4](../pitch/Culo-demo.mp4) | Approximately 2:45, synthetic narration, actual review captures. **Recorded on the fixture gateway, before the live run.** The demo script marks the segments to re-record. |
| Demo script | [Role-by-role narration and shots](../pitch/demo-script.md) | Rehearsal timing and live cues for A, B, C and D. |
| Policy matrix | [Populated CSV](MAIN_Policy_Matrix_Template.csv) | 22 data/decision rows derived from A’s matrix. Enforcement, product gaps and evidence come from the live policy-v2 runs, including D’s observed P6. A’s final sign-off pending. |
| Security evidence | [Populated test CSV](MAIN_Five_Tests_Template.csv) | 13 rows (T1–T5 as numbered in the brief, T2b health data, E1–E5, P3a/P3b), observed live on policy-v2 through the backend, with the direct BRANE gate run alongside. C and A must approve the final evidence. |
| Workflow results | [D’s verification record](../n8n/verification.md) | Separates published workflow, backend doubles and live baseline. |

The working-agent archive includes the presenter launchers and their source. Supply the reviewed archive with the hand-in. If the platform requires a hosted source or video link, D must publish the reviewed assets under the team’s authorised project and check access from the jury’s perspective. The hand-in CSVs are under submission/. The blank starter files in docs/reference/ are unsuitable for upload.

## Remaining handoffs · Europe/Amsterdam

- **Friday 20 Nov, 18:00 integration target.** Local published-workflow test completed ahead of target. B and C must verify the real deployed gateway, no-bypass path and failed-check evidence. A must verify the data destinations and the legal treatment of held reports.
- **Friday night.** D opens the team’s authenticated BuilderBase project and uploads this rough package. Save the confirmation ID or receipt and the CET time. No receipt has been observed.
- **Saturday 21 Nov, 08:00–09:30.** C runs the configured mandatory and edge fixtures. T5 is the brief’s check-failure test; the health case is row T2b. A reviews P3a/P3b and signs the matrix. B confirms the deployed agent reference, durable receipt and public demonstration route. D incorporates the observed manual timing, checks hand-in copies, and records the team’s final live cut if available. D’s local MP4 is ready as the rough cut.
- **Before Saturday 21 Nov, 10:30 CET.** D replaces the rough assets in the correct team entry, verifies the submitted files and runtime, and records BuilderBase’s confirmation and timestamp.
- **Saturday 21 Nov, 11:00 CET.** All four teammates attend Sint Janskerk check-in.

Rough receipt: pending. Final receipt: pending. No authenticated team submission URL or signed-in BuilderBase project was supplied. Never paste service credentials into the submission.

