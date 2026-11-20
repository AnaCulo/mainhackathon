"""Run the real Uvicorn server on loopback with synthetic in-process upstreams."""

import json
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path
from uuid import uuid4

import httpx
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import MODEL
from app.main import create_app
from tests.doubles import BACKEND, CONTROL, VOICE, Double


def main():
    with tempfile.TemporaryDirectory() as directory, socket.socket() as sock:
        double = Double(Path(directory))
        app = create_app(double.settings, httpx.MockTransport(double))
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(
            uvicorn.Config(app, log_level="warning", access_log=False)
        )
        thread = threading.Thread(
            target=server.run, kwargs={"sockets": [sock]}, daemon=True
        )
        thread.start()
        try:
            for _ in range(100):
                if server.started:
                    break
                time.sleep(0.05)
            with httpx.Client(
                base_url=f"http://127.0.0.1:{sock.getsockname()[1]}", trust_env=False
            ) as client:
                r = client.post("/reports", json={"text": CONTROL}, headers=BACKEND)
                r.raise_for_status()
                assert (
                    double.deliveries == [r.json()]
                    and client.get("/health").json()["ready"]
                )
                print("SIMULATED BRANE AND N8N / real HTTP and SQLite")
                print(json.dumps(r.json(), indent=2))
                sid = str(uuid4())
                turn = client.post(
                    "/v1/chat/completions",
                    json={
                        "model": MODEL,
                        "elevenlabs_extra_body": {"session_id": sid},
                        "messages": [{"role": "user", "content": CONTROL}],
                        "stream": True,
                    },
                    headers=VOICE,
                )
                turn.raise_for_status()
                assert turn.text.endswith("data: [DONE]\n\n")
                final = client.post(
                    f"/voice/sessions/{sid}/finalize",
                    json={
                        "confirmed": True,
                        "revision": int(turn.headers["x-session-revision"]),
                    },
                    headers=VOICE,
                )
                final.raise_for_status()
                assert len(double.deliveries) == 2
                print("Voice SSE, confirmed finalization and webhook contract passed.")
        finally:
            server.should_exit = True
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
