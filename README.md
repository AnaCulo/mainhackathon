# Group Čulo whistleblower intake demo

Submit a synthetic report and follow its case link to the human review form. The Python backend screens the account locally. BRANE governs the model request. A published n8n workflow registers the protected brief, tracks deadlines and leaves the decision with a human handler.

## Run the presenter

Use the current checkout with Node 24, npm, Python 3.13 and the backend requirements installed. Configure the private BRANE credential and approved policy fingerprint as described in the [presenter setup guide](n8n/README.md).

Run `./n8n/demo.sh --hold` on macOS or Linux, or `.\n8n\demo.ps1 -Hold` on Windows.

1. Open [reporter intake](http://127.0.0.1:8000/) to submit a synthetic report or use the Red team buttons. The behind-the-scenes panel shows the local decisions and governed model requests.
2. Open the [handler queue](http://127.0.0.1:8788/review) with the presenter’s designated handler login. Select the case to inspect its acknowledgement, deadlines and pending human decision.

Python FastAPI in `backend/app` serves this demo. The [legacy Node adapter](legacy/node-adapter/) reproduces the historical recording.

## Inspect the workflow and evidence

| What to inspect | Where to find it |
| --- | --- |
| Text intake and optional local clarification | The [backend guide](backend/README.md) covers governed submission. The [API examples](docs/backend-api.md) show how to request follow-up questions before submitting. |
| Data protection and human review | Compare the [policy matrix](docs/policy-matrix.md), [BRANE release checks](docs/brane-integration.md) and [security test protocol](docs/test-protocol.md). |
| Voice integration | The [voice guide](voice/README.md) documents the team's end-to-end ElevenLabs call with generated caller audio. |
| Judging evidence | The [submission index](submission/BuilderBase.md) links the hand-in CSVs and demo materials. The [business case](docs/business-case.md) describes the timed exercise. [Recorded runs](evidence/) identify the build and services used. |
