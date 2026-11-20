"""In-process BRANE and n8n simulations. Nothing here records live enforcement."""

import json
from pathlib import Path

import httpx
from cryptography.fernet import Fernet

from app.brane_client import policy_digest
from app.config import HOSTED, MODEL, Settings

POLICY = {
    "summary": {
        "allow": 2,
        "placeholder": 15,
        "refuse": 8,
        "local": 0,
        "activeSemanticCategories": 3,
    },
    "testOnly": True,
}
BACKEND = {"Authorization": "Bearer test-intake"}
VOICE = {"Authorization": "Bearer test-bridge"}
CONTROL = "A warehouse emergency exit was blocked with boxes."


class Double:
    def __init__(self, directory: Path):
        self.settings = Settings(
            directory / "test.db",
            Fernet.generate_key().decode(),
            "test-intake",
            "test-bridge",
            HOSTED,
            "test-tenant",
            MODEL,
            3,
            policy_digest(POLICY),
            "https://workflow.invalid/synthetic",
            "test-workflow",
            "test",
        )
        self.requests, self.deliveries = [], []
        self.fault = None
        self.answer = None

    def __call__(self, req):
        assert req.url.host in {"brane.ai-z.io", "workflow.invalid"}
        body = json.loads(req.content) if req.content else None
        self.requests.append((str(req.url), body, req.headers))
        if req.url.host == "workflow.invalid":
            self.deliveries.append(body)
            assert req.headers["authorization"] == "Bearer test-workflow"
            assert req.headers["idempotency-key"] == body["case_id"]
            return httpx.Response(500 if self.fault == "webhook" else 204)
        assert req.headers["authorization"] == "Bearer test-tenant"
        if self.fault == "timeout":
            raise httpx.ReadTimeout("synthetic failure")
        if req.url.path.endswith("/models"):
            assert req.method == "GET"
            return httpx.Response(200, json={"data": [
                {"id": "auto" if self.fault == "model_missing" else MODEL}
            ]})
        if req.url.path.endswith("/policy"):
            return httpx.Response(200, json={} if self.fault == "drift" else POLICY)
        if req.url.path.endswith("/policy/test"):
            assert body["executeCompletion"] is False
            if self.fault == "refusal":
                return httpx.Response(422)
            return httpx.Response(
                200,
                json={
                    "decision": {"route": "cloud"},
                    "detectedCategories": [{"label": "PERSON", "sampleText": "#P01"}]
                    if self.fault == "combined" and "\n\n{" in body["prompt"]
                    else [],
                    "matchedSemanticCategories": [],
                    "promptInjection": {"detected": False},
                    "outgoingCloudPayloadPreview": None
                    if self.fault == "preview"
                    else body["prompt"],
                },
            )
        assert req.url.path.endswith("/chat/completions") and body["model"] == MODEL
        headers = {
            "X-Brane-Routed-To": "cloud",
            "X-Brane-Action": "allow",
            "X-Brane-Redacted": "false",
            "X-Brane-Pii-Detected": "false",
            "X-Brane-Model-Resolved": MODEL,
            "X-Brane-Lane": "governed",
        }
        if self.fault == "headers":
            del headers["X-Brane-Lane"]
        data = json.loads(body["messages"][1]["content"])
        if body["stream"]:
            answer = self.answer or data["allowed_questions"][0]
            parts = [(answer[:7], None), (answer[7:], None), ("", "stop")]
            reasoning = {"reasoning": "internal", "reasoning_details": [{"type": "x"}]} \
                if self.fault == "reasoning" else {}
            lines = [
                "data: "
                + json.dumps(
                    {
                        "choices": [
                            {"index": 0, "delta": {"content": v, **reasoning}, "finish_reason": f}
                        ]
                    }
                )
                for v, f in parts
            ]
            if self.fault in {"trailing_usage", "trailing_content"}:
                # OpenRouter's trailing chunk after stop (empty delta), or a hostile variant.
                extra = "late text" if self.fault == "trailing_content" else ""
                lines.append("data: " + json.dumps({"choices": [{"index": 0, "delta": {
                    "role": "assistant", "content": extra}, "finish_reason": "stop"}],
                    "usage": {"total_tokens": 1}}))
            if self.fault != "truncated":
                lines.append("data: [DONE]")
            return httpx.Response(
                200,
                headers={**headers, "content-type": "text/event-stream"},
                text="\n\n".join(lines) + "\n\n",
            )
        facts = sorted(data["facts"], key=lambda f: f["kind"] == "available")[:3]
        questions = sorted(data["question_ids"], key=lambda k: k != "evidence")[:2]
        content = (
            self.answer
            if self.answer is not None
            else json.dumps(
                {
                    "category": facts[0]["category"],
                    "selected_fact_ids": [f["fact_id"] for f in facts],
                    "follow_up_question_ids": questions,
                }
            )
        )
        return httpx.Response(
            200,
            headers=headers,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": content}}]
            },
        )
