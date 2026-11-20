"""Adapter for the hosted API documented in the repository's BRANE.md."""

from contextvars import ContextVar

import asyncio
import hashlib
import json
import re

import httpx

from .config import HOSTED, MODEL
from .security import Stop


outage_request = ContextVar('outage_request', default=False)


def policy_digest(document):
    return hashlib.sha256(
        json.dumps(
            document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


# Allowed keys in a streamed delta. OpenRouter sometimes streams the model's internal reasoning
# ("reasoning", "reasoning_details"; ~1 in 3 live voice turns, 20 Nov). It is discarded: only
# "content" is ever used, and that is still validated against the allowed questions.
DELTA_KEYS = {"role", "content", "reasoning", "reasoning_details"}


class BraneClient:
    def __init__(self, settings, http: httpx.AsyncClient, state=None):
        self.state = state
        self.s, self.http = settings, http
        self.available = None

    @property
    def configured(self):
        return bool(
            self.s.api_key
            and re.fullmatch("[0-9a-f]{64}", self.s.policy_digest)
            and self.s.base == HOSTED
            and self.s.model == MODEL
        )

    async def _json(self, method, path, headers, body=None):
        response = await self.http.request(
            method,
            HOSTED + path,
            headers=headers,
            json=body,
            timeout=self.s.timeout,
            follow_redirects=False,
        )
        self._check_status(response)
        return response.json()

    @staticmethod
    def _check_status(response):
        if response.status_code == 422:
            raise Stop(422, "gateway_refused")
        if response.status_code in (401, 403):
            raise Stop(503, "gateway_authentication_failed")
        if response.status_code != 200:
            raise Stop(503, "gateway_http_error")

    async def _preflight(self, messages, headers, audit):
        catalog = await self._json("GET", "/models", headers)
        models = catalog.get("data") if isinstance(catalog, dict) else None
        if not isinstance(models, list) or not any(
            isinstance(entry, dict) and entry.get("id") == MODEL for entry in models
        ):
            raise Stop(503, "approved_model_unavailable")
        policy = await self._json("GET", "/policy", headers)
        summary = policy.get("summary", {}) if isinstance(policy, dict) else {}
        required = (
            "allow",
            "placeholder",
            "local",
            "refuse",
            "activeSemanticCategories",
        )
        if (
            not isinstance(summary, dict)
            or not all(
                type(summary.get(k)) is int and summary[k] >= 0 for k in required
            )
            or summary["activeSemanticCategories"] == 0
            or summary["refuse"] + summary["local"] == 0
            or policy_digest(policy) != self.s.policy_digest
        ):
            raise Stop(503, "unapproved_tenant_policy")
        audit(
            "gateway",
            "policy_verified",
            metadata={"policy_sha256": self.s.policy_digest},
        )
        # System prompts are server-owned constants. Previewed alone, BRANE's prompt guard
        # flags them as instructions (voice prompt, 20 Nov), so each caller-derived message
        # is previewed alone and the system prompt only inside the combined preview below.
        prompts = [m["content"] for m in messages if m["role"] != "system"]
        combined_check = len(messages) > 1 or any(m["role"] == "system" for m in messages)
        if combined_check:
            prompts.append("\n\n".join(m["content"] for m in messages))
        for prompt in prompts:
            preview = await self._json(
                "POST",
                "/policy/test",
                headers,
                {"prompt": prompt, "executeCompletion": False},
            )
            route = preview["decision"]["route"]
            if route in {"local", "refuse"}:
                audit("gateway", "preview_" + route, route=route, success=False)
                raise Stop(422, "preview_withheld")
            if not (
                preview["decision"]["route"] == "cloud"
                and preview["outgoingCloudPayloadPreview"] == prompt
                and preview["detectedCategories"] == []
                and preview["matchedSemanticCategories"] == []
                and preview["promptInjection"]["detected"] is False
            ):
                raise Stop(503, "preview_not_clean")
        audit(
            "gateway",
            "preview_clean",
            route="cloud",
            metadata={"messages_checked": len(messages), "combined_checked": combined_check},
        )
        # What actually leaves for BRANE: already-protected, closed-vocabulary text only
        # (caller-derived messages; the server-owned system prompt is a constant).
        audit(
            "gateway",
            "outbound_messages",
            route="cloud",
            metadata={"messages": [m["content"] for m in messages if m["role"] != "system"]},
        )

    @staticmethod
    def _verify_headers(h, audit):
        names = [
            "X-Brane-Routed-To",
            "X-Brane-Action",
            "X-Brane-Redacted",
            "X-Brane-Pii-Detected",
            "X-Brane-Model-Resolved",
            "X-Brane-Lane",
        ]
        expected = ["cloud", "allow", "false", "false", MODEL, "governed"]
        if [h.get(k) for k in names] != expected:
            # Preserve enumerated observations even when a response cannot be released.
            metadata = {
                key: h[key]
                for key, values in (
                    ("X-Brane-Routed-To", {"cloud", "local"}),
                    ("X-Brane-Action", {"allow", "placeholder", "local", "refuse"}),
                    ("X-Brane-Redacted", {"true", "false"}),
                )
                if h.get(key) in values
            }
            audit(
                "gateway",
                "headers_rejected",
                success=False,
                metadata=metadata,
                route=metadata.get("X-Brane-Routed-To"),
            )
            raise Stop(503, "unverified_completion_headers")
        metadata = {k: h[k] for k in names}
        # Record a vendor request ID only when actually present and identifier-shaped.
        vendor_id = h.get("X-Request-ID", "")
        if re.fullmatch(r"[A-Za-z0-9._-]{1,128}", vendor_id):
            metadata["upstream_request_id"] = vendor_id
        audit("gateway", "ALLOW", route="cloud", metadata=metadata)

    @staticmethod
    async def _stream_content(response):
        if (
            response.headers.get("content-type", "").split(";")[0]
            != "text/event-stream"
        ):
            raise Stop(502, "invalid_gateway_stream")
        parts, total, stopped = [], 0, False
        async for line in response.aiter_lines():
            if not line or line.startswith(":"):
                continue
            if not line.startswith("data:"):
                raise Stop(502, "invalid_gateway_stream")
            payload = line[5:].strip()
            if payload == "[DONE]" and stopped:
                return "".join(parts)
            if payload == "[DONE]":
                raise Stop(502, "invalid_gateway_stream")
            (choice,) = json.loads(payload)["choices"]
            delta = choice["delta"]
            if stopped:
                # OpenRouter sends a trailing usage chunk after the stop chunk (20 Nov live
                # voice turn). Accept it only if it carries no content and no other finish.
                if delta.get("content") or choice.get("finish_reason") not in (None, "stop") \
                        or set(delta) - DELTA_KEYS:
                    raise Stop(502, "invalid_gateway_stream")
                continue
            if choice.get("index") != 0 or set(delta) - DELTA_KEYS:
                raise Stop(502, "invalid_gateway_stream")
            value = delta.get("content") or ""
            total += len(value)
            if not isinstance(value, str) or total > 32768:
                raise Stop(502, "invalid_gateway_stream")
            parts.append(value)
            if choice.get("finish_reason") not in (None, "stop"):
                raise Stop(502, "incomplete_gateway_stream")
            stopped = choice.get("finish_reason") == "stop"
        raise Stop(503, "incomplete_gateway_stream")

    async def complete(self, messages, request_id, audit, *, stream=False):
        if (self.s.environment == "development" and outage_request.get() and
                self.state is not None and self.state.gateway_kill):
            raise Stop(503, "gateway_unverifiable")
        if not self.configured:
            raise Stop(503, "gateway_not_configured")
        headers = {
            "Authorization": "Bearer " + self.s.api_key,
            "X-Request-ID": request_id,
            "User-Agent": "hotline-intake/1.0",
        }
        try:
            async with asyncio.timeout(self.s.timeout):
                await self._preflight(messages, headers, audit)
                audit("transport", "completion_attempted")
                async with self.http.stream(
                    "POST",
                    HOSTED + "/chat/completions",
                    headers=headers,
                    json={"model": MODEL, "messages": messages, "stream": stream},
                    follow_redirects=False,
                    timeout=self.s.timeout,
                ) as response:
                    self._check_status(response)
                    self._verify_headers(response.headers, audit)
                    if stream:
                        result = await self._stream_content(response)
                    else:
                        raw = bytearray()
                        async for part in response.aiter_bytes():
                            raw.extend(part)
                            if len(raw) > 65536:
                                raise Stop(502, "invalid_gateway_response")
                        try:
                            (choice,) = json.loads(raw)["choices"]
                            message = choice["message"]
                            if message.get("refusal"):
                                raise Stop(422, "gateway_refused")
                            if choice["finish_reason"] != "stop" or message.get("tool_calls") or message.get("function_call"):
                                raise Stop(502, "incomplete_completion")
                            result = message["content"]
                        except (KeyError, TypeError, AttributeError, ValueError, RecursionError):
                            raise Stop(502, "invalid_gateway_response") from None
                    if not isinstance(result, str) or not result:
                        raise Stop(502, "invalid_gateway_response")
                    self.available = True
                    return result
        except Stop as exc:
            self.available = False
            if exc.reason == "gateway_refused":
                audit("gateway", "REFUSE", success=False)
            raise
        except (httpx.TimeoutException, TimeoutError):
            self.available = False
            raise Stop(503, "gateway_timeout") from None
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            IndexError,
            AttributeError,
            TypeError,
            RecursionError,
        ):
            self.available = False
            raise Stop(503, "gateway_unverifiable") from None
