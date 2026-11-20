"""Exercise the optional 3c7dda9 backend through /reports, with its gateway double and a real n8n webhook."""
import json
import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

import httpx
from dotenv import dotenv_values
from fastapi.testclient import TestClient

checkout, config = sys.argv[1:3]
sys.path.insert(0, str(Path(checkout).resolve()))
from app.main import create_app
from tests.doubles import BACKEND, CONTROL, Double

env = dotenv_values(config)
url = env["N8N_WEBHOOK_URL"]
assert url == "http://127.0.0.1:5689/webhook/protected-case"
with tempfile.TemporaryDirectory() as directory, httpx.Client(trust_env=False) as local:
    double = Double(Path(directory))
    calls = []
    def transport(request):
        if request.url.host == "workflow.invalid":
            result = local.post(url, content=request.content, headers={
                name: request.headers[name] for name in ("Content-Type", "Authorization", "Idempotency-Key")
            })
            calls.append(result.status_code)
            return httpx.Response(result.status_code)
        return double(request)
    settings = replace(double.settings, webhook_key=env["N8N_TOKEN"])
    with TestClient(create_app(settings, httpx.MockTransport(transport))) as client:
        response = client.post("/reports", json={"text": CONTROL}, headers=BACKEND)
        assert response.status_code == 200 and calls == [201], (response.status_code, calls)
        case = response.json()
        view = local.get("http://127.0.0.1:8788/review/" + case["case_id"],
                         auth=(env["HANDLER_REF"], env["HANDLER_PASSWORD"]))
        assert view.status_code == 200 and case["summary"] in view.text
        double.fault = "timeout"
        assert client.post("/reports", json={"text": CONTROL}, headers=BACKEND).status_code == 503
        assert calls == [201]
        print("Python /reports + branch gateway double + published webhook: 201, handler read 200, unavailable 503, zero additional handoffs.")

