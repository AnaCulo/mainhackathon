import json
import re
from typing import Annotated

from pydantic import Field

from .fact_extraction import WORDS, ApprovedPackage, FactID, QuestionID, SafeFact
from .models import Category, Extraction, Strict
from .policies import QUESTIONS
from .security import Stop

REPORT_PROMPT = (
    "Prepare a concise draft for human review. All facts are reports, not verified findings. "
    "Choose the primary concern and rank one to three nonredundant facts. Lead with an event or topic. "
    "Include relevant supporting evidence when space permits. Interpret after only as explicit "
    "sequence, never causation. Use the first fact's category. Choose one or two useful questions, or an empty array if none are available, "
    "from question_ids. Prioritise evidence if event and timing are known but evidence is missing. "
    "Output exactly one JSON object with category, selected_fact_ids and follow_up_question_ids "
    "(the latter two are arrays of IDs). Do not include prose, findings or new values."
)
VOICE_PROMPT = (
    "You assist a workplace reporter. A human will assess the allegations. Return exactly "
    "one question from allowed_questions that best addresses the screened history. No other text or actions."
)


_CASE_TOKEN = re.compile(r"\b(PERSON|REPORTER)_(\d{2})\b")
_GATEWAY_TOKEN = re.compile(r"<(PERSON|REPORTER)_(\d{1,2})>")


def to_gateway(text):
    return _CASE_TOKEN.sub(lambda m: f"<{m[1]}_{int(m[2])}>", text)


def from_gateway(text):
    return _GATEWAY_TOKEN.sub(lambda m: f"{m[1]}_{int(m[2]):02}", text)


class Synthesis(Strict):
    category: Category
    selected_fact_ids: Annotated[list[FactID], Field(min_length=1, max_length=3)]
    follow_up_question_ids: Annotated[list[QuestionID], Field(max_length=2)]


def questions(package):
    # Apply the same invitation limits whether the private field exists or not.
    suppressed = set()
    if any(f.kind == "discrepancy" for f in package.facts):
        suppressed.add("when")
    if any(f.kind == "obstruction" for f in package.facts) and any(
        f.period or f.kind == "available" for f in package.facts
    ):
        suppressed.add("where")
    return [key for key in package.missing if key not in suppressed]


def _noun(fact):
    unit = fact.unit or "incident"
    if fact.count is None:
        return unit + "s"
    article = "an" if unit[0] in "aeiou" else "a"
    if fact.count == 1:
        return article + " " + unit
    return f"{WORDS[fact.count - 1]} {unit}s"


TOPICS = {
    "approval_process": "The report mentions a second sign-off requirement.",
    "duplicate_invoicing": "The report discusses whether invoices were recorded more than once.",
    "invoicing": "The report mentions a concern about invoicing or financial records.",
    "safety": "The report mentions a workplace safety concern.",
    "harassment": "The report mentions possible workplace harassment.",
    "discrimination": "The report mentions possible discrimination.",
    "corruption": "The report mentions a possible corruption concern.",
    "fraud": "The reporter raises a concern about possible fraud.",
    "other": "The reporter raises a workplace concern for review.",
}


def render(fact: SafeFact):
    if fact.kind == "purchase_without_signoff":
        return f"{fact.subject} allegedly approved a purchase without the required second sign-off."
    if fact.kind == "topic":
        return TOPICS[fact.topic]
    timing = ""
    if fact.period:
        timing = (
            " " + fact.period
            if fact.period in {"last week", "last month", "yesterday"}
            else " in " + fact.period.capitalize()
        )
    if fact.kind == "obstruction":
        detail = " by " + fact.material if fact.material else ""
        return f"The reporter describes {_noun(fact)} blocked{detail}{timing}."
    if fact.kind == "discrepancy":
        return "The reporter describes discrepancies in invoice records."
    if fact.kind == "available":
        return f"The reporter says {_noun(fact)} {'is' if fact.count == 1 else 'are'} available for review."
    if fact.kind == "missing_approval":
        return f"The reporter describes {_noun(fact)} as missing{timing}."
    if fact.kind == "recurrence":
        return f"The incident reportedly occurred {WORDS[fact.count - 1]} {'time' if fact.count == 1 else 'times'}{timing}."
    if fact.kind == "incident":
        return f"The reporter describes {_noun(fact)}{timing}."
    raise Stop(502, "ungrounded_model_output")


def unique_fields(pairs):
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise ValueError("duplicate field")
    return fields


def parse_case(content: str, package: ApprovedPackage):
    try:
        choice = Synthesis.model_validate(
            json.loads(content, object_pairs_hook=unique_fields)
        )
    except (ValueError, RecursionError):
        raise Stop(502, "invalid_model_output") from None
    by_id = {fact.fact_id: fact for fact in package.facts}
    ids, follow = choice.selected_fact_ids, choice.follow_up_question_ids
    if (
        len(ids) != len(set(ids))
        or not set(ids) <= by_id.keys()
        or len(follow) != len(set(follow))
        or not set(follow) <= set(questions(package))
        or bool(follow) != bool(questions(package))
    ):
        raise Stop(502, "ungrounded_model_output")
    selected = [by_id[key] for key in ids]
    if selected[0].category != choice.category or selected[0].kind == "available":
        raise Stop(502, "unsupported_primary_concern")
    sentences = []
    for index, fact in enumerate(selected):
        sentence = render(fact)
        if fact.after and fact.after in ids:
            if ids.index(fact.after) >= index:
                raise Stop(502, "unsupported_event_order")
            if fact.after == ids[index - 1]:
                sentence = "Subsequently, " + sentence[0].lower() + sentence[1:]
        sentences.append(sentence)
    times = list(dict.fromkeys(f.period for f in package.facts if f.period))
    detail = Extraction(
        category=choice.category,
        summary=" ".join(sentences),
        approximate_time=", ".join(times) or "unknown",
        location=next((f.location for f in package.facts if f.location), "unknown"),
        persons=list(dict.fromkeys(package.person_mentions)),
        evidence=[f.unit for f in package.facts if f.kind == "available"],
        missing=package.missing,
        follow_up=[QUESTIONS[key] for key in follow],
    )
    return detail, choice


def messages(system, data):
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": to_gateway(json.dumps(data, ensure_ascii=True, sort_keys=True)),
        },
    ]


def report_messages(package: ApprovedPackage):
    return messages(
        REPORT_PROMPT,
        {**package.model_dump(exclude_none=True), "question_ids": questions(package)},
    )
