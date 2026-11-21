# Evidence status

**STATUS: CURRENT LIVE EVIDENCE on synthetic-intake-6 (21 Nov 2026).** The backend stamps its policy version into every new run file, and the BRANE policy fingerprint is pinned (`e3226167…ca23`, policy-v2).

| Current evidence | What it shows |
| --- | --- |
| [backend_run_20261121-005741.json](../evidence/backend_run_20261121-005741.json) | All 13 fixtures through the backend at `30be7eb` (the submitted code), hosted BRANE and the real model. Cases: T1, T3, P3a, E2, E4, E5. Held locally: T2, T2b, T4, P3b, E1, E3, E6. A scripted scan of every model-bound message against each fixture's protected values found none. |
| [backend_outage_20261121-010046.json](../evidence/backend_outage_20261121-010046.json) | T5, check failure, on the same backend: 503, held for a person with a receipt, zero completion attempts, no outbound message. |
| [run_20261121-010001.json](../evidence/run_20261121-010001.json) and [.csv](../evidence/run_20261121-010001.csv) | Direct BRANE gate without our backend, same policy. Every completion it sent carried no protected value. It withheld six cases whose BRANE preview was not safe (see below). The file's label reads "policy-v1" because of a stale `TEAM_BUILD` value; its category counts (allow 3, placeholder 13, local 7, refuse 2, semantic 6) and policy timestamp are policy-v2's. |
| [backend_run_20261121-004849.json](../evidence/backend_run_20261121-004849.json) | The run before the final commit, same results. |
| [backend_run_20261121-002846.json](../evidence/backend_run_20261121-002846.json) | Earlier the same night, before realistic-report routing: E5 held at the BRANE preview because BRANE flagged "shift manager" as PERSON. |
| [realistic_reports_preview_20261121.json](../evidence/realistic_reports_preview_20261121.json) | Five non-fixture reports from a reviewer. Two reach a summary. BRANE's CRIMINAL_OFFENCE_ALLEGATION rule keeps an expense-fraud report local. Local rules hold a Dutch forgery report (P3) and a health euphemism (P3). Preview only, no model call. |
| Live adapter tests, 21 Nov | `RUN_LIVE_BRANE=1 pytest tests/test_live_brane.py`: 3/3 passed. |

**Not live.** The demo video (`pitch/Culo-demo.mp4`) was recorded on 20 Nov with the legacy Node adapter and a simulated gateway. It is identified as historical wherever it is shown. Timing for a manual baseline has not been measured.

**Test IDs.** T1–T5 follow the brief's five security tests; T5 is check failure. The health case is T2b, stored as fixture `T5` in `data/` and the run files ([mapping](../docs/test-protocol.md#test-ids-follow-the-briefs-five-security-tests)).

**Known failures, disclosed.** These come from the direct BRANE gate without our backend ([run_20261121-010001.json](../evidence/run_20261121-010001.json), [test protocol](../docs/test-protocol.md)). No protected value reached the model in any of them (the runner withholds a completion when the preview is unsafe), and the backend passed every one of these fixtures:
- **T2 and E4:** BRANE's CRIMINAL_OFFENCE_ALLEGATION rule, which kept both local on 20 Nov, did not match on 21 Nov. For T2 the preview proposed the cloud with placeholders; for E4 it detected nothing and the controller's name would have left in clear. The backend's local P3 and name checks run first.
- **T3 and E2:** The runner could not verify one consistent BRANE placeholder per person, and BRANE did not link a nickname to the full name. The backend binds every mention and alias locally.
- **E5:** BRANE's preview left spoken phone digits in clear. The backend withholds spoken numbers. In one 21 Nov run BRANE flagged the job title "shift manager" as PERSON and held E5; in the next it did not, so the detector is not deterministic.
- **P3a:** BRANE restored the real name in its answer. The backend never uses restored values.
- **T4:** On 20 Nov the live completion routed the embedded instruction to the cloud while the preview refused it. On 21 Nov the live call was refused (422). The backend quarantines instructions locally (P4) before any BRANE call either way.

The catalogue below covers every evidence file. The 20 Nov files are labelled with the synthetic-intake-3 baseline and do not record which runtime version ran.

| Evidence file | Recorded path and version | Current for synthetic-intake-6? |
| --- | --- | --- |
| [backend_run_20261120-172943.json](../evidence/backend_run_20261120-172943.json) | synthetic-intake-3 catalogue, runtime version unstamped | Historical |
| [backend_run_20261120-175038.json](../evidence/backend_run_20261120-175038.json) | synthetic-intake-3 catalogue, runtime version unstamped | Historical |
| [backend_run_20261120-204543.json](../evidence/backend_run_20261120-204543.json) | synthetic-intake-3 catalogue, runtime version unstamped | Historical |
| [backend_run_20261121-002846.json](../evidence/backend_run_20261121-002846.json) | synthetic-intake-6 before routing change, live BRANE policy-v2 | Superseded |
| [realistic_reports_preview_20261121.json](../evidence/realistic_reports_preview_20261121.json) | synthetic-intake-6, live BRANE policy-v2, preview only | Current |
| [backend_run_20261121-004849.json](../evidence/backend_run_20261121-004849.json) | synthetic-intake-6, live BRANE policy-v2 | Superseded by 005741 |
| [backend_run_20261121-005741.json](../evidence/backend_run_20261121-005741.json) | synthetic-intake-6 at `30be7eb`, live BRANE policy-v2 | Current |
| [backend_outage_20261121-010046.json](../evidence/backend_outage_20261121-010046.json) | synthetic-intake-6 at `30be7eb`, gateway unavailable | Current |
| [run_20261121-010001.json](../evidence/run_20261121-010001.json) / [.csv](../evidence/run_20261121-010001.csv) | Direct BRANE gate, policy-v2 | Current |
| [elevenlabs_call_20261120-195233.json](../evidence/elevenlabs_call_20261120-195233.json) | synthetic-intake-3 catalogue, runtime version unstamped | Historical |
| [elevenlabs_call_20261120-195233_agent.wav](../evidence/elevenlabs_call_20261120-195233_agent.wav) | synthetic-intake-3 catalogue, runtime version unstamped | Historical |
| [elevenlabs_call_20261120-200549.json](../evidence/elevenlabs_call_20261120-200549.json) | synthetic-intake-3 catalogue, runtime version unstamped | Historical |
| [elevenlabs_call_20261120-200549_agent.wav](../evidence/elevenlabs_call_20261120-200549_agent.wav) | synthetic-intake-3 catalogue, runtime version unstamped | Historical |
| [live_trace_20261120-172546.json](../evidence/live_trace_20261120-172546.json) | synthetic-intake-3 | Historical |
| [live_trace_20261120-172635.json](../evidence/live_trace_20261120-172635.json) | synthetic-intake-3 | Historical |
| [live_trace_20261120-173954.json](../evidence/live_trace_20261120-173954.json) | synthetic-intake-3 | Historical |
| [live_trace_20261120-174739.json](../evidence/live_trace_20261120-174739.json) | synthetic-intake-3 | Historical |
| [presenter_20261120.json](../evidence/presenter_20261120.json) | synthetic-intake-3 catalogue, runtime version unstamped | Historical |
| [run_20261120-162747.csv](../evidence/run_20261120-162747.csv) | Direct BRANE baseline, no backend version | Historical |
| [run_20261120-162747.json](../evidence/run_20261120-162747.json) | Direct BRANE baseline, no backend version | Historical |
| [run_20261120-165852.csv](../evidence/run_20261120-165852.csv) | Direct BRANE baseline, no backend version | Historical |
| [run_20261120-165852.json](../evidence/run_20261120-165852.json) | Direct BRANE baseline, no backend version | Historical |
| [voice_harness_20261120-174756.json](../evidence/voice_harness_20261120-174756.json) | synthetic-intake-3 catalogue, runtime version unstamped | Historical |
