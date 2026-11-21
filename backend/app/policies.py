import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .models import Decision, Identity
from .security import Stop

RULES = json.loads(Path(__file__).with_name("policy.json").read_text(encoding="utf-8"))
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
RESTRICTED = tuple(re.compile(r"\b(?:" + term + r")\b") for term in RULES["restricted"])
INSTRUCTIONS = tuple(re.compile(pattern) for pattern in RULES["instruction_patterns"])
INSTRUCTION_CUE = re.compile(r"\b(?:ignore|disregard|override|system prompt|developer mode)\b")
SPELLED = re.compile(r"\b[a-z](?:[^\w\s]+[a-z]){2,}\b")
IDENTIFIERS = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b|\+?\d[\d\s().-]{7,}\d|\b[A-Z]{2,5}-\d{3,}\b")

UNKNOWN = "unknown"
# Capitalised words that are also first names; never treated as a person's alias.
COMMON_WORDS = frozenset(
    "may june april august will mark bill grace hope rose faith joy art dawn summer jack frank "
    "victor sunny rich page miles ray lane".split())


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
    specific: list[tuple[str, str]]
    mentions: list[str]
    decisions: list[Decision]
    mappings: list[tuple[str, str, str]]
    # Normalised report with every bound alias replaced by its case token
    # (PERSON_01 / REPORTER_01). Still a local document until the narrative
    # path redacts it further and BRANE previews it.
    protected: str = ""


def specific_observations(text):
    """Release fixed descriptions only when a complete statement supports them."""
    found = []
    approval = re.compile(
        r"\x00(PERSON_\d+)\x00(?:, (?:my|our|the) (?:team lead|manager|head of procurement),)? "
        r"(?:(?:allegedly )?approved (?:a|the) purchase(?: of \d+ (?:laptops|items|units))?"
        r"|has been approving (purchase orders)(?: (?:above|over) [\d,.]+ euros)?) "
        r"without (?:the )?required second sign-off", re.IGNORECASE
    )
    wording = {
        "i saw ": "The reporter says they observed",
        "i was told ": "The reporter says they were told about",
        "i suspect ": "The reporter suspects",
    }
    for part in re.split(r"(?<=[.!?])\s+|\n+", text):
        sentence = part.strip().rstrip(".!")
        if match := approval.fullmatch(sentence):
            actor = match[1]
            item = "purchase orders" if match[2] else "a purchase"
            found.append(("other", f"{actor} allegedly approved {item} without the required second sign-off."))
            continue
        # Capture how the reporter knows this. Render only enumerated output,
        # including when the reporter expresses doubt or attributes it to others.
        statement = sentence.casefold()
        prefix = next((p for p in wording if statement.startswith(p)), "")
        statement = statement.removeprefix(prefix)
        if prefix:
            statement = statement.removeprefix("that ")
        if re.fullmatch(r"(?:two |the )?invoice totals (?:differ|differed)", statement):
            intro = wording.get(prefix, "The report describes")
            found.append(("fraud", f"{intro} a discrepancy between invoice totals."))
        if re.fullmatch(
            r"(?:since \w+, )?(?:(?:a|the|the same) )?(?:supplier )?invoices?"
            r"(?: from (?:one|the same|a) (?:\w+ ){0,2}supplier)? "
            r"(?:was|were|has been|have been) (?:entered|booked|recorded) twice"
            r"(?:: the same invoice number appears in the ledger once .+ and again .+)?",
            statement,
        ):
            intro = wording.get(prefix, "The report describes")
            found.append(("fraud", f"{intro} duplicate recording of an invoice."))
        obstruction = re.fullmatch(
            r"(?:a |an |the )?(?:warehouse )?(emergency exit|fire exit|walkway|stairway) "
            r"(?:was|is) (blocked|obstructed)(?: (?:by|with) (boxes|pallets|equipment))?",
            statement,
        )
        if obstruction:
            place, condition, material = obstruction.groups()
            article = "an" if place == "emergency exit" else "a"
            description = f"{article} {place} {condition}"
            if material:
                description += f" by {material}"
            intro = wording.get(prefix, "The reporter describes")
            found.append(("safety", f"{intro} {description}."))
    return found


def screen(text: str, identities: list[Identity], *, allow_incomplete=False, audit=None) -> Screened:
    """Screen a report locally and tokenise the identities it declares or names.

    The result feeds two outbound paths: closed-vocabulary facts (fact_extraction) when the
    grammar recognises the report, otherwise a locally redacted copy (narrative.protect).
    Both are previewed by BRANE and held for a person unless the preview is clean.

    Name recognition improves local indexing. It never authorizes a span of
    original narrative for export. Case-scoped aliases can be supplied in any script.
    """
    text = unicodedata.normalize("NFKC", text).replace("\x00", " ")
    lowered = " ".join(text.casefold().split())
    instruction_text = SPELLED.sub(lambda m: re.sub(r"[^\w]", "", m[0]), lowered)
    instruction = any(p.search(instruction_text) for p in INSTRUCTIONS)
    restricted = any(p.search(lowered) for p in RESTRICTED)
    offence = any(re.search(p, lowered) for p in RULES["offence_patterns"])
    identifying = any(re.search(p, lowered) for p in RULES["identifying_context"])
    instruction_like = bool(INSTRUCTION_CUE.search(instruction_text))
    if audit and (instruction_like or instruction):
        audit("local", "instruction_signal", policy="P4", count=1, metadata={"instruction_like": True})

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
        r"(?i)\b(?:my name is|mijn naam is|ik heet)\s+([^,.;\n]{1,100}?)(?=\s+and\b|[,.;\n]|$)", text
    ):
        bind("reporter", [match[1].strip()])
    for match in re.finditer(r"(?i)\bmy email is\s+([^\s,;]+@[^\s,;]+)", text):
        bind("reporter", [match[1].rstrip(".")])
    name_word = r"[^\W\d_]+(?:[-’'][^\W\d_]+)*"
    full_name = rf"{name_word}(?:\s+(?:de|van|von|der|da|al)){{0,2}}\s+{name_word}"
    verbs = r"(?:allegedly\s+|has been\s+)?(?:changed|approved|approving|denied|signed|told)"
    subjects = [
        rf"(?<!\w)({full_name})\s+{verbs}\b",
        # Apposition: "Ivo Laan, my team lead, allegedly approved ..."
        rf"(?<!\w)({full_name}),\s+(?:my|the|our|a)\s+[^,.;\n]{{1,60}},\s+{verbs}\b",
        rf"\b(?:I witnessed|I saw|I asked|my manager is)\s+({full_name})\b",
    ]
    subjects.append(rf"\b(?:my|our) (?:team lead|manager),\s+({full_name}),")
    for pattern in subjects:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            name = match[1]
            words = name.split()
            if (
                words[0][0].isupper()
                and words[-1][0].isupper()
                and words[0].rstrip(".") not in {"Mr", "Ms", "Dr", "Mrs"}
                and name.casefold() not in bindings
            ):
                bind("person", [name])

    if re.search(r"\b(?:fraud|bribery|theft|corruption)\b", lowered) and (
        any(kind == "person" for _, _, kind in bindings.values())
        or re.search(
            r"\b(?:director|manager|supervisor|colleague|committing|accused|relative)\b",
            lowered,
        )
    ):
        offence = True

    # Resolve short aliases against full names first. Shared surnames are ambiguous.
    surnames = {}
    for token, name, kind in list(bindings.values()):
        if kind != "person" or len(name.split()) < 2:
            continue
        surname = name.split()[-1]
        for short in {surname, surname.split("-")[0]}:
            if len(short) < 3 or not short[0].isupper():
                continue
            if short in surnames and surnames[short][0] != token:
                raise Stop(422, "ambiguous_identity", "P2")
            surnames[short] = (token, name, kind)
    # "Sven Proef-Naam ... everyone calls him Sven": a bare first name is the same person.
    # A first name two people share, or one that is an ordinary word, is left alone.
    firsts = {}
    for token, name, kind in list(bindings.values()):
        words = name.split()
        first = words[0] if len(words) >= 2 else None
        if (not first or len(first) < 3 or not first[0].isupper() or first in surnames
                or first.casefold() in COMMON_WORDS):
            continue
        firsts[first] = None if first in firsts and firsts[first][0] != token else (token, name, kind)
    surnames.update({f: b for f, b in firsts.items() if b})
    short_aliases = {}
    for short, binding in surnames.items():
        # Exclude lower-case email addresses and hyphenated continuations.
        for alias in re.finditer(r"(?<![\w@.-])(?:(?:Mr|Ms|Mrs|Dr)\.?\s+|[A-Z]\.\s+)?"
                                 + re.escape(short) + r"(?![\w@-])", text):
            short_aliases[alias[0]] = binding

    mentions = []
    counts = {"P1": 0, "P2": 0}
    mappings = []
    id_spans = [m.span() for m in IDENTIFIERS.finditer(text)]
    covered = []
    if bindings:
        variants = [(n, "(?i:" + re.escape(n) + ")") for n in bindings]
        variants.extend((n, re.escape(n)) for n in short_aliases)
        alternatives = "|".join(expr for _, expr in sorted(variants, key=lambda item: -len(item[0])))
        pattern = re.compile(r"(?<![\w@.-])(?:" + alternatives + r")(?![\w@-])")

        def resolve(match):
            return bindings.get(match[0].casefold()) or short_aliases[match[0]]

        for m in pattern.finditer(text):
            covered.append(m.span())
            binding = resolve(m)
            token, _, kind = binding
            if binding not in mappings:
                mappings.append(binding)
            counts["P1" if kind == "reporter" else "P2"] += 1
            if kind == "person":
                mentions.append(token)
        # Never classify words inside an identified name as evidence.
        text = pattern.sub(lambda m: "\x00" + resolve(m)[0] + "\x00", text)
    counts["P1"] += sum(not any(a <= start and end <= b for a, b in covered)
                        for start, end in id_spans)
    decisions = [decision(p, n) for p, n in counts.items() if n]
    if audit:
        for d in decisions:
            audit("local", d.action, policy=d.policy, count=d.count,
                  metadata={"distinct_tokens": len(set(mentions))} if d.policy == "P2" else {})
    if instruction:
        raise Stop(422, "instruction_quarantined", "P4")
    if restricted or offence:
        raise Stop(422, "restricted_material", "P3")
    if identifying:
        raise Stop(422, "identifying_context", "P1")
    topics = [
        (cat, summary)
        for cat, pattern, summary in RULES["topics"]
        if re.search(r"\b(?:" + pattern + r")\b", text, re.IGNORECASE)
    ]
    specific = specific_observations(text)
    described = {category for category, _ in specific}
    topics = specific + [item for item in topics if item[0] not in described]
    if not topics and not allow_incomplete:
        raise Stop(422, "local_review_required", next((d.policy for d in decisions), "P5"))
    category, summary = (
        topics[0]
        if topics
        else ("other", "A workplace report was received for human review.")
    )
    # A denied or hypothetical detail cannot fill an intake gap. Restrict
    # certainty to the sentence in which the detail appears.
    details = [
        part for part in re.split(r"[.!?\n]+", text)
        if not re.search(
            r"\b(?:no|not|never|without|unsure|uncertain|maybe|possibly|if|might|could|or)\b|n['’]t\b",
            part, re.IGNORECASE
        )
    ]
    detail_text = "\n".join(details)
    location = (
        "warehouse"
        if re.search(r"\b(in|at|a) (the |a )?warehouse\b", detail_text, re.IGNORECASE)
        else UNKNOWN
    )
    times = set(re.findall(r"\b(?:yesterday|last week|last month)\b", detail_text.casefold()))
    weekdays = r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    for part in details:
        # Also accept a short answer to the voice question, e.g. "Monday."
        for day in re.findall(rf"(?:\b(?:on|last|this) |^\s*)({weekdays})\b", part.casefold()):
            times.add(day.capitalize())
    time_hint = times.pop() if len(times) == 1 else UNKNOWN
    evidence = [
        label
        for pattern, label in [
            (r"\b((attached|have) (an? |the )?|forwarded )email\b", "email"),
            (r"\b(attached|have) (a |the )?photo\b", "photo"),
            (r"\bledger\b", "ledger entries"),
            (r"\bpurchase orders?\b", "purchase orders"),
            (r"\binspection log\b", "inspection log"),
        ]
        if re.search(pattern, detail_text, re.IGNORECASE)
    ]
    missing = [
        key
        for key, present in (
            ("what", topics),
            ("when", time_hint != UNKNOWN),
            ("where", location != UNKNOWN),
            ("who", mentions or re.search(
                r"\b(?:my|our|the|a) (?:team lead|shift lead|supervisor|manager|colleague|witness)\b",
                detail_text, re.IGNORECASE
            )),
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
    for d in decisions:
        if d.action == "BLOCK":
            raise Stop(422, "identity_withheld", d.policy)
    observations = list(dict.fromkeys(topics))
    protected = text.replace("\x00", "")
    return Screened(fields, observations, specific, mentions, decisions, mappings, protected)
