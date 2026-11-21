# Start here: run the whistleblower hotline in 10 minutes

An anonymous intake website for workplace reports. The reporter types (or speaks) on this machine. Names and contact details are protected locally, BRANE checks every model request, and a human handler decides in a separate queue. **Use only made-up names and events.**

## What you need

| | |
|---|---|
| Python | **3.13** ([python.org](https://www.python.org/downloads/)) |
| Node.js | **24** (`node --version` must show `v24.…`) |
| Internet | Only on the first run: npm installs n8n (about 1 minute), and the local speech model downloads once (about 480 MB) |
| Free ports | 8000, 8788, 5689, 5679 |
| BRANE team key | Optional. Without it everything runs, but every report is held for a person ("BRANE not configured"), which is the fail-closed behaviour |

## macOS or Linux

Open a terminal in the unzipped folder (the one containing this file):

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env      # then, in that file, set BRANE_API_KEY to the team key
PYTHON=.venv/bin/python ./n8n/demo.sh --hold
```

## Windows (PowerShell)

Open PowerShell in the unzipped folder:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env   # then, in that file, set BRANE_API_KEY to the team key
$env:PYTHON = (Resolve-Path .venv\Scripts\python.exe)
powershell -ExecutionPolicy Bypass -File n8n\demo.ps1 -Hold
```

`-ExecutionPolicy Bypass` applies to this one run only. Windows blocks downloaded scripts by default.

## When it is running

The launcher prints `Speech-to-text ready`, then `Submit at http://127.0.0.1:8000/` and `Handler queue: http://127.0.0.1:8788/review`. Leave the terminal open. Press Enter in it to stop everything.

1. **Reporter:** open http://127.0.0.1:8000/. Click an example such as "Name protected", press Send, then **Submit for human review**. The "Behind the scenes" panel shows exactly what left the machine.
2. **Security tests:** in the **Red team** panel, click T1, T2, T3, T4 and T5 (check failure). Each shows what the reporter wrote next to what was sent.
3. **Handler:** open the case link, or http://127.0.0.1:8788/review. Sign in with the `HANDLER_REF` user (`handler`) and the `HANDLER_PASSWORD` from the `demo.env` file whose path the launcher printed. Record a decision.

A message takes about 5–25 seconds, mostly waiting for BRANE's checks.

## Without a BRANE key: run the tests

```bash
cd backend
../.venv/bin/python -m pytest -q        # Windows: ..\.venv\Scripts\python.exe -m pytest -q
```

About 290 tests run offline in a few seconds, with BRANE simulated. They cover protection, the five security tests, the handler flow and Windows compatibility.

## If something goes wrong

| You see | Do this |
|---|---|
| `This demo needs Node 24` | Install Node 24 as the message says, then open a new terminal |
| `Python package missing (...)` | Run the `pip install` line it prints. If you used a virtual environment, set `PYTHON` to its python |
| `Demo port 8000 is already in use` | Stop the other program or demo, or add `--isolated` (`-Isolated` on Windows) to use free ports |
| `BRANE is not configured on this machine` | In `backend/.env`, set `BRANE_API_KEY` to the team key. Keep `BRANE_POLICY_SHA256` as given |
| Page says "Speech-to-text unavailable" | The hint under the Talk button names the fix. On Windows this may be the [Microsoft Visual C++ Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe). Typing always works |
| `running scripts is disabled on this system` (Windows) | Use the `powershell -ExecutionPolicy Bypass -File ...` line above |

More detail: [README.md](README.md) (overview), [n8n/README.md](n8n/README.md) (presenter setup), [docs/test-protocol.md](docs/test-protocol.md) (security tests), [submission/EVIDENCE_STATUS.md](submission/EVIDENCE_STATUS.md) (live evidence).
