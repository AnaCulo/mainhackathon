# Group Čulo whistleblower intake demo

Submit a synthetic report and follow its case link to the human review form. The Python backend screens the account locally. BRANE governs the model request. A published n8n workflow registers the protected brief, tracks deadlines and leaves the decision with a human handler.

## Run the presenter

Use the current checkout with Node 24, npm, Python 3.13 and the backend requirements installed. Configure the private BRANE credential and approved policy fingerprint as described in the [presenter setup guide](n8n/README.md).

On Windows, run `.\n8n\demo.ps1 -Hold`. On macOS or Linux, run `./n8n/demo.sh --hold`. Open the printed intake URL, submit a fresh synthetic report and follow the link to its case. The recorded pitch and submission archives reflect earlier builds.

## Inspect the workflow and evidence

| What to inspect | Where to find it |
| --- | --- |
| Text intake and optional local clarification | The [backend guide](backend/README.md) covers governed submission. The [API examples](docs/backend-api.md) show how to request follow-up questions before submitting. |
| Data protection and human review | Compare the [policy matrix](docs/policy-matrix.md), [BRANE release checks](docs/brane-integration.md) and [security test protocol](docs/test-protocol.md). |
| Voice integration | The [voice guide](voice/README.md) documents the team's end-to-end ElevenLabs call with generated caller audio. |
| Judging evidence | The [submission index](submission/BuilderBase.md) links the hand-in CSVs and demo materials. The [business case](docs/business-case.md) describes the timed exercise. [Recorded runs](evidence/) identify the build and services used. |
