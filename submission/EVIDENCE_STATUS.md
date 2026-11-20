# Evidence status

**STATUS: CURRENT LIVE EVIDENCE on synthetic-intake-6 (21 Nov 2026).** The backend stamps its policy version into every new run file, and the BRANE policy fingerprint is pinned (`e3226167…ca23`, policy-v2).

| Current evidence | What it shows |
| --- | --- |
| [backend_run_20261121-004849.json](../evidence/backend_run_20261121-004849.json) | All fixtures through the backend, hosted BRANE and the real model, final code. Cases: T1, T3, P3a, E2, E4, E5. Held locally: T2, T4, T5, P3b, E1, E3, E6. No protected value in any model-bound message. |
| [backend_run_20261121-002846.json](../evidence/backend_run_20261121-002846.json) | Earlier the same night, before realistic-report routing: E5 held at the BRANE preview because BRANE flagged "shift manager" as PERSON. |
| [realistic_reports_preview_20261121.json](../evidence/realistic_reports_preview_20261121.json) | Five non-fixture reports from a reviewer. Two reach a summary. BRANE's CRIMINAL_OFFENCE_ALLEGATION rule keeps an expense-fraud report local. Local rules hold a Dutch forgery report (P3) and a health euphemism (P3). Preview only, no model call. |
| Live adapter tests, 21 Nov | `RUN_LIVE_BRANE=1 pytest tests/test_live_brane.py`: 3/3 passed. |

**Not live.** The demo video (`pitch/Culo-demo.mp4`) was recorded on 20 Nov with the legacy Node adapter and a simulated gateway. It is identified as historical wherever it is shown. Timing for a manual baseline has not been measured.

**Known failures, disclosed.** These come from direct BRANE gate runs without our backend (`evidence/run_20261120-165852.json`, `docs/test-protocol.md`):
- **E2:** BRANE did not link a nickname to the same person (two placeholders for one witness). The backend binds aliases locally before sending.
- **E5:** BRANE replaced only part of a spoken phone number ("oh six one two three four[PHONE_REF_1] six seven eight"). The backend withholds spoken numbers locally. On 21 Nov E5 was held in one run because BRANE flagged the job title "shift manager" as PERSON. It produced a summary in the next run, so the detector is not deterministic.
- **T4:** The preview flagged the embedded instruction (route local), but the live completion routed the same text to the cloud with action allow. The backend quarantines instructions locally (P4) before any BRANE call.

Everything below is the historical catalogue from 20 Nov. Those files are labelled with the synthetic-intake-3 baseline and do not record which runtime version ran.

| Evidence file | Recorded path and version | Current for synthetic-intake-6? |
| --- | --- | --- |
| [backend_run_20261120-172943.json](../evidence/backend_run_20261120-172943.json) | synthetic-intake-3 catalogue, runtime version unstamped | Historical |
| [backend_run_20261120-175038.json](../evidence/backend_run_20261120-175038.json) | synthetic-intake-3 catalogue, runtime version unstamped | Historical |
| [backend_run_20261120-204543.json](../evidence/backend_run_20261120-204543.json) | synthetic-intake-3 catalogue, runtime version unstamped | Historical |
| [backend_run_20261121-002846.json](../evidence/backend_run_20261121-002846.json) | synthetic-intake-6 before routing change, live BRANE policy-v2 | Superseded |
| [realistic_reports_preview_20261121.json](../evidence/realistic_reports_preview_20261121.json) | synthetic-intake-6, live BRANE policy-v2, preview only | Current |
| [backend_run_20261121-004849.json](../evidence/backend_run_20261121-004849.json) | synthetic-intake-6, live BRANE policy-v2 | Current |
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
