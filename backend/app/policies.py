import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .models import Decision, Identity
from .security import Stop

RULES = json.loads(Path(__file__).with_name("policy.json").read_text())
QUESTIONS = {
    "what": "What happened?",
    # BRANE's detector tags "Approximately" as PERSON, which makes every preview
    # unclean (503 preview_not_clean). Keep question wording free of such false positives.
    "when": "When did this happen, roughly?",
    "where": "Where did this happen? A general setting is enough.",
    "who": "Who was involved? Roles are enough.",
    "evidence": "What evidence, if any, is available?",
    "confirm": "Would you like to submit this report for human review?",
}
UNKNOWN = "unknown"


# Fail at startup if a new action needs implementation.
for rule, permitted in {
    "P1": {"PROTECT", "BLOCK"},
    "P2": {"PROTECT", "BLOCK"},
    "P3": {"BLOCK", "LOCAL_ONLY"},
    "P4": {"BLOCK"},
    "P5": {"BLOCK"},
    "P6": {"HUMAN_ONLY"},
}.items():
    if RULES[rule] not in permitted:
        raise ValueError(f"Unsupported action for {rule}")


def decision(policy, count=None):
    return Decision(policy=policy, action=RULES[policy], count=count)


@dataclass
class Screened:
    fields: dict
    observations: list[tuple[str, str]]
    mentions: list[str]
    decisions: list[Decision]
    mappings: list[tuple[str, str, str]]


def screen(text: str, identities: list[Identity], *, voice=False) -> Screened:
    """Construct a new document exclusively from a closed vocabulary.

    Name recognition improves local indexing. It never authorizes a span of
    original narrative for export. Case-scoped aliases can be supplied in any script.
    """
    text = unicodedata.normalize("NFKC", text)
    lowered = " ".join(text.casefold().split())
    if any(re.search(pattern, lowered) for pattern in RULES["instruction_patterns"]):
        raise Stop(422, "instruction_quarantined", "P4")
    if any(term in lowered for term in RULES["restricted"]):
        raise Stop(422, "restricted_material", "P3")

    # Explicit identifiers take priority. Infer clear introductions and repeated
    # full names in subject position; omit unresolved details from model input.
    bindings = {}
    next_person = 1

    def bind(kind, aliases):
        nonlocal next_person
        present = [name for name in aliases if mention(name).search(text)]
        if not present:
            return
        existing = {
            bindings[n.casefold()][0] for n in present if n.casefold() in bindings
        }
        if len(existing) > 1 or any(
            t.startswith("PERSON") != (kind == "person") for t in existing
        ):
            raise Stop(422, "ambiguous_identity", "P2")
        token = next(iter(existing), None)
        if not token:
            token = "REPORTER_01" if kind == "reporter" else f"PERSON_{next_person:02}"
            next_person += kind == "person"
        for name in present:
            bindings[name.casefold()] = (token, name, kind)

    def mention(name):
        return re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", re.IGNORECASE)

    for entity in identities:
        bind(entity.kind, entity.aliases)
    for match in re.finditer(
        r"(?i)\bmy name is\s+([^,.;\n]{1,100}?)(?=\s+and\b|[,.;\n]|$)", text
    ):
        bind("reporter", [match[1].strip()])
    for match in re.finditer(r"(?i)\bmy email is\s+([^\s,;]+@[^\s,;]+)", text):
        bind("reporter", [match[1].rstrip(".")])
    name_word = r"[^\W\d_]+(?:[-’'][^\W\d_]+)*"
    full_name = rf"{name_word}(?:\s+(?:de|van|von|der|da|al)){{0,2}}\s+{name_word}"
    subjects = [
        rf"(?<!\w)({full_name})\s+(?:changed|approved|denied|signed|told)\b",
        rf"\b(?:I witnessed|I saw|I asked|my manager is)\s+({full_name})\b",
    ]
    for pattern in subjects:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            name = match[1]
            words = name.split()
            if (
                words[0][0].isupper()
                and words[-1][0].isupper()
                and name.casefold() not in bindings
            ):
                bind("person", [name])

    mentions = []
    counts = {"P1": 0, "P2": 0}
    mappings = []
    if bindings:
        pattern = "|".join(
            re.escape(n) for n in sorted(bindings, key=len, reverse=True)
        )
        for m in re.finditer(r"(?<!\w)(?:" + pattern + r")(?!\w)", text, re.IGNORECASE):
            binding = bindings.get(m[0].casefold())
            if binding is None:
                raise Stop(422, "ambiguous_identity", "P2")
            token, _, kind = binding
            if binding not in mappings:
                mappings.append(binding)
            counts["P1" if kind == "reporter" else "P2"] += 1
            if kind == "person":
                mentions.append(token)
        # Never classify words inside an identified name as evidence.
        text = re.sub(
            r"(?<!\w)(?:" + pattern + r")(?!\w)", " ", text, flags=re.IGNORECASE
        )
    topics = [
        (cat, summary)
        for cat, pattern, summary in RULES["topics"]
        if re.search(r"\b(?:" + pattern + r")\b", text, re.IGNORECASE)
    ]
    obstruction = re.fullmatch(
        r"(?:a |an |the )?(?:warehouse )?(emergency exit|fire exit|walkway|stairway) "
        r"(?:was|is) (blocked|obstructed)(?: (?:by|with) (boxes|pallets|equipment))?[.!]?",
        text.strip(),
        re.IGNORECASE,
    )
    if obstruction:
        place, condition, material = (
            v.lower() if v else None for v in obstruction.groups()
        )
        article = "an" if place == "emergency exit" else "a"
        description = f"{article} {place} {condition}"
        if material:
            description += f" by {material}"
        topics.insert(0, ("safety", f"The reporter describes {description}."))
    if not topics and not voice:
        raise Stop(422, "local_review_required", "P5")
    category, summary = (
        topics[0]
        if topics
        else ("other", "A workplace report was received for human review.")
    )
    location = (
        "warehouse"
        if re.search(r"\b(in|at|a) (the |a )?warehouse\b", text, re.IGNORECASE)
        else UNKNOWN
    )
    time_hint = next(
        (
            v
            for v in ("yesterday", "last week", "last month")
            if re.search(r"\b" + v + r"\b", text, re.IGNORECASE)
        ),
        UNKNOWN,
    )
    evidence = [
        label
        for pattern, label in [
            (r"\b(attached|have) (an? |the )?email\b", "email"),
            (r"\b(attached|have) (a |the )?photo\b", "photo"),
        ]
        if re.search(pattern, text, re.IGNORECASE)
    ]
    missing = [
        key
        for key, present in (
            ("what", topics),
            ("when", time_hint != UNKNOWN),
            ("where", location != UNKNOWN),
            ("who", mentions),
            ("evidence", evidence),
        )
        if not present
    ]
    fields = {
        "category": category,
        "summary": summary,
        "approximate_time": time_hint,
        "location": location,
        "persons": list(dict.fromkeys(mentions)),
        "evidence": evidence,
        "missing": missing,
        "follow_up": [QUESTIONS[k] for k in missing],
    }
    decisions = [decision(p, n) for p, n in counts.items() if n]
    for d in decisions:
        if d.action == "BLOCK":
            raise Stop(422, "identity_withheld", d.policy)
    observations = list(dict.fromkeys(topics)) or [(category, summary)]
    return Screened(fields, observations, mentions, decisions, mappings)
