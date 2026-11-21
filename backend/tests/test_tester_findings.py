"""Regressions from the simulated judge test on 21 Nov (judge-style inputs, not fixtures)."""
import json
from uuid import uuid4

from app import narrative
from app.config import MODEL
from app.policies import screen
from app.routes.ui import NEEDS_DETAIL, readiness

from .doubles import VOICE

REPEATED = (
    "Sven Proef-Naam, the site manager, ignored the broken scaffolding report on Monday. "
    "Sven Proef-Naam signed it off anyway.\n"
    "Later Sven Proef-Naam told the crew to keep working. Everyone calls him Sven. "
    "You can reach Sven at sven.proef@example.test.\n"
    "The photos are on the site tablet. Sven Proef-Naam deleted one of them."
)


def test_repeated_full_name_and_first_name_are_one_person():
    s = screen(REPEATED, [], allow_incomplete=True)
    assert set(s.mentions) == {"PERSON_01"} and "Sven" not in s.protected
    out = narrative.protect(s.protected, s.mentions).outbound
    assert "another staff member" not in out.lower() and "Sven" not in out and "Proef" not in out
    assert out.startswith("The site manager ignored") and "Later that person told the crew" in out


def test_ordinary_word_first_name_is_not_an_alias():
    s = screen("Mark Jansen-Test told us to skip checks. I will mark the report as urgent.",
               [], allow_incomplete=True)
    assert s.protected.endswith("I will mark the report as urgent.")


def test_identifier_heavy_report_goes_to_a_person_not_back_for_detail():
    text = ("The supplier at Kerkstraat 12, 3511 AB Utrecht is paid to account "
            "NL91ABNA0417164300 although no goods arrive.")
    assert readiness([text]) not in NEEDS_DETAIL


def test_first_detailed_message_is_not_asked_what_happened_again(setup):
    client, double, _db = setup
    text = ("Since March the purchasing team splits large orders into several small ones "
            "so each stays under the approval limit.")
    r = client.post("/v1/chat/completions", headers=VOICE, json={
        "model": MODEL, "stream": True, "elevenlabs_extra_body": {"session_id": str(uuid4())},
        "messages": [{"role": "user", "content": text}]})
    assert r.status_code == 200, r.text
    sent = [json.loads(b["messages"][1]["content"]) for _, b, _ in double.gateway_requests
            if b and b.get("messages")]
    assert sent and all("what" not in m.get("open_questions", []) for m in sent)


def test_transcript_drops_replacement_characters(monkeypatch):
    from types import SimpleNamespace
    from app import stt

    class Model:
        def transcribe(self, path, **kwargs):
            return [SimpleNamespace(text=" Call me back on 06-123-45678�")], SimpleNamespace(duration=2.0)

    monkeypatch.setattr(stt, "_load", lambda: Model())
    assert stt.transcribe(b"RIFF-synthetic")["text"] == "Call me back on 06-123-45678"


# Review on 21 Nov: names the local redaction let through to BRANE's preview.
import pytest  # noqa: E402

from app.security import Stop  # noqa: E402

NAME_CASES = [
    ("Mr. Okafor in procurement keeps approving his own expense claims since March.", ["Okafor"]),
    ("Mrs. Jansen from finance deletes the duplicate invoices every Friday.", ["Jansen"]),
    ("Dr. Patel in the lab told staff to skip the chemical inventory last month.", ["Patel"]),
    ("Prof. Müller in the research group altered the test results before the audit.", ["Müller"]),
    ("Miss O'Brien from payroll pays herself overtime nobody approved.", ["Brien"]),
    ("The safety report was hidden, said Mr. Okafor from procurement.", ["Okafor", "another staff member"]),
    ("mr okafor in procurement approves his own claims.", ["okafor"]),
    ("Mohammed al-Rashid told us to skip the safety checks on the loading dock last week.", ["Mohammed", "Rashid"]),
    ("Ahmed bin Salim approved the duplicate payments to the supplier in May.", ["Ahmed", "Salim"]),
    ("Ali ibn Hassan signed the delivery notes without checking them.", ["Ali", "Hassan"]),
    ("Fatima el-Amrani, the shift lead, told staff to skip the forklift inspection.", ["Fatima", "Amrani"]),
    ("Mr. van der Berg told the drivers to drive longer than allowed.", ["Berg", " van "]),
    ("Dr. Anna Kowalczyk-Nowak told nurses to skip the hand hygiene checks.", ["Anna", "Kowalczyk", "that person"]),
    ("Our CFO Sanne keeps moving money between project budgets without approval.", ["Sanne", "staff member"]),
]


@pytest.mark.parametrize("text,forbidden", NAME_CASES)
def test_titles_particles_and_role_names_are_redacted_locally(text, forbidden):
    s = screen(text, [], allow_incomplete=True)
    out = narrative.protect(s.protected or text, s.mentions).outbound
    assert not [f for f in forbidden if f.lower() in f" {out.lower()} "], out


@pytest.mark.parametrize("text", [
    "Nurses at the St. Mary's ward were told to skip hand hygiene checks.",
    "Our team in the U.S. office hides the incident reports from auditors.",
    "I put the shredded files in the bin on Monday after the manager asked.",
])
def test_lookalikes_are_left_alone(text):
    s = screen(text, [], allow_incomplete=True)
    assert narrative.protect(s.protected or text, s.mentions).outbound == text
