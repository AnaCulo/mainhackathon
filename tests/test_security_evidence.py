"""Offline checks for the verdicts handed to the judges."""

import json
from unittest.mock import patch

import pytest

import run_security_tests as runner


CASE = {
    "channel": "text", "report": "A fictional report.", "allowed_outcomes": ["cloud_clean"],
    "must_not_egress": ["SYNTHETIC-CONTACT"], "must_keep": [],
}


@pytest.mark.parametrize(("status", "preview"), [
    (503, {}),
    (200, {"decision": {"route": "cloud"}, "outgoingCloudPayloadPreview": None}),
    (200, {"decision": {"route": "cloud"}, "outgoingCloudPayloadPreview": "SYNTHETIC-CONTACT"}),
    (200, {"decision": {"route": "local"}, "outgoingCloudPayloadPreview": "unexpected text"}),
])
def test_bad_preview_never_runs_a_completion(status, preview):
    with patch.object(runner, "call", return_value=(status, {}, preview)) as call:
        result = runner.run_case(CASE, "https://gateway.invalid", "demo-model")
    assert call.call_count == 1
    assert result["verdict"] == "FAIL" and result["chat_status"] is None


@pytest.mark.parametrize(("status", "headers", "verdict"), [
    (200, {"X-Brane-Routed-To": "cloud"}, "FAIL"),
    (500, {"X-Brane-Routed-To": "cloud", "X-Brane-Redacted": "false"}, "FAIL"),
    (200, {"X-Brane-Routed-To": "cloud", "X-Brane-Redacted": "false",
           "X-Brane-Model-Resolved": "demo-model", "X-Brane-Lane": "governed"}, "PASS"),
])
def test_cloud_pass_requires_inspectable_preview_and_governed_completion(status, headers, verdict):
    preview = {"decision": {"route": "cloud"}, "outgoingCloudPayloadPreview": runner.build_prompt(CASE)}
    answer = {"choices": [{"message": {"content": "Synthetic draft."}}]}
    with patch.object(runner, "call", side_effect=[(200, {}, preview), (status, headers, answer)]):
        assert runner.run_case(CASE, "https://gateway.invalid", "demo-model")["verdict"] == verdict


def test_split_aliases_stop_before_completion():
    case = {**CASE, "same_person_mentions": 3, "allowed_outcomes": ["cloud_protected"]}
    preview = {"decision": {"route": "cloud"},
               "outgoingCloudPayloadPreview": "PERSON_REF_1 met PERSON_REF_2. PERSON_REF_2 spoke."}
    with patch.object(runner, "call", return_value=(200, {}, preview)) as call:
        result = runner.run_case(case, "https://gateway.invalid", "demo-model")
    assert call.call_count == 1 and result["verdict"] == "FAIL"


def test_outage_probe_uses_no_credential(monkeypatch):
    monkeypatch.delenv("BRANE_UNAVAILABLE_URL", raising=False)
    with patch.object(runner, "call", side_effect=OSError) as call:
        assert runner.run_unavailable_check("demo-model")["verdict"] == "PASS"
    assert call.call_args.kwargs["authenticated"] is False


@pytest.mark.parametrize("case_id", ["T3", "E2", "E5"])
def test_reviewed_unsafe_historical_preview_stops_before_completion(case_id):
    current = json.loads(runner.DATA.read_text(encoding="utf-8"))["cases"]
    case = next(row for row in current if row["id"] == case_id)
    archive = runner.OUT_DIR / "run_20261120-165852.json"
    prior = next(row for row in json.loads(archive.read_text(encoding="utf-8"))["results"]
                 if row["case"]["id"] == case_id)
    preview = {"decision": {"route": prior["preview_route"]},
               "outgoingCloudPayloadPreview": prior["outgoing_cloud_payload"]}
    with patch.object(runner, "call", return_value=(200, {}, preview)) as call:
        result = runner.run_case(case, "https://gateway.invalid", "demo-model")
    assert result["verdict"] == "FAIL" and call.call_count == 1
