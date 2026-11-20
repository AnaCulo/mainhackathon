# Evidence status

**STATUS: PENDING LIVE RUN on synthetic-intake-5**

The hosted BRANE key and reviewed policy fingerprint were unavailable for this build. The backend columns in both hand-in CSVs retain their historical observations. Local integration tests use simulated BRANE and webhook responses. A new live run must verify the E6 result, outbound content, completion headers, held-register delivery and human review link before replacing the historical evidence.

The inherited evidence set is catalogued under the historical synthetic-intake-3 baseline. Direct gateway runs bypassed FastAPI. Individual records identify the executed path. Where the file lacks a policy version, the catalogue label does not establish which code ran.

| Evidence file | Recorded path and version | Current for synthetic-intake-5? |
| --- | --- | --- |
| [backend_run_20261120-172943.json](../evidence/backend_run_20261120-172943.json) | synthetic-intake-3 catalogue, runtime version unstamped | Historical |
| [backend_run_20261120-175038.json](../evidence/backend_run_20261120-175038.json) | synthetic-intake-3 catalogue, runtime version unstamped | Historical |
| [backend_run_20261120-204543.json](../evidence/backend_run_20261120-204543.json) | synthetic-intake-3 catalogue, runtime version unstamped | Historical |
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
