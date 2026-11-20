"""Local intake grammar and release policy. Only ApprovedPackage goes to BRANE."""

import re
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field

from .models import Category, Extraction, Strict
from .policies import Screened
from .security import Stop

WORDS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
RELATIVE = ("last week", "last month", "yesterday")
NUMBER = r"(?:[1-9][0-9]{0,3}|" + "|".join(WORDS) + ")"
PERIOD = (
    r"(?: (?P<relative>last week|last month|yesterday)| in (?P<month>"
    + "|".join(MONTHS)
    + "))?"
)
COUNT = rf"(?P<number>{NUMBER}|a|an|the)"
FLAGS = re.IGNORECASE | re.ASCII

Period = Literal[
    "last week",
    "last month",
    "yesterday",
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]
Kind = Literal[
    "obstruction",
    "discrepancy",
    "missing_approval",
    "incident",
    "recurrence",
    "available",
    "topic",
]
Unit = Literal[
    "emergency exit",
    "fire exit",
    "walkway",
    "stairway",
    "invoice record",
    "incident",
    "approval",
    "photograph",
    "email",
    "document",
    "record",
    "witness account",
]
FactID = Annotated[str, Field(pattern=r"^F[0-9]{3}$")]
QuestionID = Literal["what", "when", "where", "who", "evidence"]


class SafeFact(Strict):
    fact_id: FactID
    kind: Kind
    category: Category
    unit: Unit | None = None
    count: int | None = Field(default=None, ge=1, le=10)
    material: Literal["boxes", "pallets", "equipment"] | None = None
    period: Period | None = None
    location: Literal["warehouse"] | None = None
    topic: (
        Literal[
            "invoicing",
            "safety",
            "harassment",
            "discrimination",
            "corruption",
            "fraud",
            "duplicate_invoicing",
            "other",
        ]
        | None
    ) = None
    # Only an explicit same-sentence "then" creates an edge.
    after: FactID | None = None


class ApprovedPackage(Strict):
    facts: list[SafeFact] = Field(min_length=1, max_length=8)
    missing: list[QuestionID]
    person_mentions: list[Annotated[str, Field(pattern=r"^PERSON_[0-9]{2,}$")]]


@dataclass(frozen=True)
class Observation:
    method: str
    start: int
    end: int
    values: dict


@dataclass
class FactReview:
    approved: ApprovedPackage
    provenance: list[dict]

    @property
    def withheld_policies(self):
        return sorted(
            {
                row["policy"]
                for row in self.provenance
                if row["classification"] == "LOCAL_ONLY"
                and row["policy"] in {"P1", "P3"}
            }
        )

    def private_extraction(self, extraction: Extraction):
        # A detail known to the local reviewer can be unavailable to the model.
        # Never use this object as input to BRANE or the webhook.
        fields = extraction.model_dump()
        for row in self.provenance:
            if row["method"] == "combined_context":
                fields["location"] = row["values"]["location"]
                fields["missing"] = [k for k in fields["missing"] if k != "where"]
            period = (
                row["values"].get("period")
                if row["method"] == "financial_detail"
                else None
            )
            if period:
                fields["approximate_time"] = period
                fields["missing"] = [k for k in fields["missing"] if k != "when"]
        return {**fields, "local_fact_provenance": self.provenance}


# Each pattern consumes a whole affirmative clause. Counts and time belong
# to the matched event, never to nearby words elsewhere in the report.
PATTERNS = {
    "obstruction": rf"{COUNT} (?P<location>warehouse )?(?P<unit>emergency exits?|fire exits?|walkways?|stairways?) (?:was|is|were|are) (?:blocked|obstructed)(?: (?:with|by) (?P<material>boxes|pallets|equipment))?{PERIOD}",
    "discrepancy": rf"{COUNT} (?P<unit>invoice records?) (?:showed|contained|had) discrepanc(?:ies|y){PERIOD}",
    "missing_approval": rf"{COUNT} (?P<unit>approvals?) (?:was|were|is|are) missing{PERIOD}",
    "incident": rf"{COUNT} (?P<unit>incidents?) (?:were reported|occurred){PERIOD}",
    "recurrence": rf"the incident (?:happened|occurred) (?P<number>{NUMBER}) times{PERIOD}",
    "available": rf"i (?:have|attached) {COUNT} (?P<unit>photographs?|photos?|emails?|documents?|witness accounts?)",
    "available_records": r"the (?P<unit>records|documents|photographs|emails|witness accounts) are available for review",
    "amount": r"the reported (?:(?P<qualifier>total|approximate) )?discrepancy was (?P<currency>EUR|GBP|USD) (?P<amount>(?:[1-9][0-9]{0,2}(?:,[0-9]{3})+|[0-9]{1,12})(?:\.[0-9]{2})?)",
}
GRAMMAR = {name: re.compile(pattern, FLAGS) for name, pattern in PATTERNS.items()}


def _parse_clause(text, start, end):
    clause = text[start:end]
    for method, pattern in GRAMMAR.items():
        match = pattern.fullmatch(clause)
        if match:
            values = {k: v.lower().strip() for k, v in match.groupdict().items() if v}
            token = values.pop("number", None)
            if token in WORDS:
                values["count"] = WORDS.index(token) + 1
            elif token and token.isdigit():
                values["count"] = int(token)
            elif token in ("a", "an"):
                values["count"] = 1
            if method == "amount":
                values["currency"] = values["currency"].upper()
                values["amount"] = values["amount"].replace(",", "")
            if unit := values.get("unit"):
                if token == "the" and not unit.endswith("s"):
                    values["count"] = 1
                values["unit"] = unit.removesuffix("s")
                if values["unit"] == "photo":
                    values["unit"] = "photograph"
                # Ambiguous number/noun agreement requires human interpretation.
                if (
                    token
                    and token != "the"
                    and (values["count"] == 1) == unit.endswith("s")
                ):
                    return None
            return Observation(method, start, end, values)
    return None


def _read(text):
    observations = []
    complete = True
    for sentence in re.finditer(r".+?(?:\.(?=\s|$)|\Z)", text, re.DOTALL):
        body = sentence[0].removesuffix(".")
        # A sequence can join two independently recognisable events.
        delimiter = re.search(r",?\s+then\s+", body, FLAGS)
        parts = (
            [(0, delimiter.start()), (delimiter.end(), len(body))]
            if delimiter
            else [(0, len(body))]
        )
        for index, (a, b) in enumerate(parts):
            value = body[a:b]
            start = sentence.start() + a + len(value) - len(value.lstrip())
            obs = _parse_clause(text, start, start + len(value.strip()))
            if obs is None:
                complete = False
                continue
            if index:
                obs.values["after_previous"] = True
            observations.append(obs)
    return observations, complete


def _topic_facts(screened, text):
    facts = []
    for category, _ in screened.observations:
        topic = category
        fraud_cue = (
            r"\b(?:reporting|report) suspected (?:invoice )?fraud\b"
            if screened.mappings
            else r"\bfraud\b"
        )
        if category == "fraud" and not re.search(fraud_cue, text, FLAGS):
            topic, category = "invoicing", "other"
        # This is a discussion topic, even if a later sentence disputes it.
        # No new attribution, amount, chronology or supplier reference is released.
        if (
            topic == "invoicing"
            and not screened.mappings
            and re.search(
                r"\b(?:duplicate invoices?|invoices? (?:from (?:one|a) [a-z]+ supplier )?"
                r"(?:were|have been) (?:booked|recorded|entered) twice)\b",
                text,
                FLAGS,
            )
        ):
            topic = "duplicate_invoicing"
        if any(f.topic == topic for f in facts):
            continue
        facts.append(
            SafeFact(
                fact_id=f"F{len(facts) + 1:03}",
                kind="topic",
                category=category,
                topic=topic,
            )
        )
    return facts


def extract_local_facts(text: str, screened: Screened) -> FactReview:
    observations, complete = _read(text)
    # Unknown context may contradict an event or identify its participants.
    # Never export rich details from a partially understood narrative, or
    # combine them with people, oversized inventories or competing timelines.
    detailed = (
        complete
        and not screened.mappings
        and 0 < len(observations) <= 4
        and all(o.values.get("count", 1) <= 10 for o in observations)
    )
    evidence_count = sum(o.method.startswith("available") for o in observations)
    events = [
        o.method not in {"available", "available_records", "amount"}
        for o in observations
    ]
    event_count = sum(events)
    linked_events = any(
        events[i - 1] and events[i] and observations[i].values.get("after_previous")
        for i in range(1, len(observations))
    )
    # Multiple independent numbers/places can fingerprint an incident. Only a
    # small event + evidence package, or two explicitly sequenced events, passes.
    detailed = (
        detailed
        and evidence_count <= 1
        and (
            event_count == 1
            or (event_count == 2 and linked_events and evidence_count == 0)
        )
    )
    if event_count > 1 and any(
        o.method in {"amount", "discrepancy"} for o in observations
    ):
        detailed = False

    provenance, facts = [], []
    previous = None
    for obs in observations:
        values = obs.values.copy()
        row = {
            "method": obs.method,
            "span": [obs.start, obs.end],
            "values": obs.values,
            "classification": "LOCAL_ONLY",
            "policy": "P3" if obs.method == "amount" else "local_grounding",
        }
        provenance.append(row)
        if not detailed or obs.method == "amount":
            previous = None
            continue
        kind = "available" if obs.method == "available_records" else obs.method
        after = previous if values.pop("after_previous", False) else None
        period = values.pop("month", None) or values.pop("relative", None)
        if values.get("location") and (period or evidence_count):
            provenance.append(
                {
                    **row,
                    "method": "combined_context",
                    "values": {"location": values.pop("location")},
                    "policy": "P1",
                }
            )
        if kind == "discrepancy":
            # No approval for exporting a financial fingerprint. Release only
            # the independent process observation; keep values and month local.
            withheld = {k: values.pop(k) for k in ("count",) if k in values}
            if period:
                withheld["period"] = period
            if withheld:
                provenance.append(
                    {
                        **row,
                        "method": "financial_detail",
                        "values": withheld,
                        "policy": "P3",
                    }
                )
            period = None
        category = "safety" if kind == "obstruction" else "other"
        fact = SafeFact(
            fact_id=f"F{len(facts) + 1:03}",
            kind=kind,
            category=category,
            period=period,
            after=after,
            **values,
        )
        facts.append(fact)
        previous = fact.fact_id
        row.update(classification="ALLOW", policy="P5")
        row["released"] = fact.model_dump(exclude_none=True)
        row["values"] = row["released"]
    if not facts:
        disputed_detail = observations and re.search(
            r"\b(?:not|never|no|hypothetically|unless|imagined)\b", text, FLAGS
        )
        disputed_topic = re.search(
            r"\b(?:no (?:evidence of )?|not (?:reporting |alleging )?|never alleged )"
            r"(?:fraud|harassment|corruption|discrimination|bribery|safety (?:issue|concern))\b"
            r"|^\s*(?:what if|suppose|hypothetically)\b",
            text,
            FLAGS,
        )
        if disputed_detail or disputed_topic:
            raise Stop(422, "ambiguous_report")
        facts = _topic_facts(screened, text)
        for f in facts:
            provenance.append(
                {
                    "method": "screened_topic",
                    "span": [0, len(text)],
                    "classification": "ALLOW",
                    "policy": "P5",
                    "released": f.model_dump(exclude_none=True),
                }
            )
    if not facts or all(f.kind == "available" for f in facts):
        raise Stop(422, "local_review_required")
    missing = [
        key
        for key, known in (
            ("when", any(f.period for f in facts)),
            ("where", any(f.location for f in facts)),
            ("who", bool(screened.mentions)),
            ("evidence", any(f.kind == "available" for f in facts)),
        )
        if not known
    ]
    return FactReview(
        ApprovedPackage(
            facts=facts, missing=missing, person_mentions=screened.mentions
        ),
        provenance,
    )
