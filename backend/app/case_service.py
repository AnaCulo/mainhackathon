from functools import partial

from . import agent
from .audit import record
from .fact_extraction import extract_local_facts
from .models import HOLD_REASONS, Brief, Case, Decision, HeldCase
from .n8n_client import deliver
from .policies import RULES, decision, screen
from .security import Stop


def brief_for(extraction):
    """Handler brief built only from validated extraction fields (closed vocabulary)."""
    facts = [p + "." for p in extraction.summary.removesuffix(".").split(". ")]
    timeline = (
        []
        if extraction.approximate_time == "unknown"
        else [f"Reported time: {extraction.approximate_time}."]
    )
    evidence = [f"{label.capitalize()} mentioned by reporter (unverified)." for label in extraction.evidence]
    return Brief(facts=facts, timeline=timeline, evidence=evidence)


def http_status(case):
    if isinstance(case, HeldCase):
        return 202 if case.status == "held_for_review" else HOLD_REASONS[case.hold_reason]
    return 200


def report_response(case):
    from fastapi.responses import JSONResponse

    if isinstance(case, HeldCase):
        return JSONResponse({**case.model_dump(), "message": "Received. A person will review your report."},
                            status_code=http_status(case))
    return case


async def submit(state, rid, key, text, identities, source, reporter_mode, *, voice_turn=None):
    data = {
        "text": text,
        "identities": [e.model_dump() for e in identities],
        "source": source,
        "reporter_mode": reporter_mode,
    }
    cid, received, cached = state.db.reserve(key, data, rid)
    audit = partial(record, state.db, rid, cid)
    audit("local", "intake_received", metadata={"matrix_version": RULES["version"]})
    if cached:
        audit("local", "idempotent_replay")
        await deliver(state.db, state.http, state.settings, cid)
        return (HeldCase if "hold_reason" in cached else Case).model_validate(cached)
    review = None
    try:
        screened = screen(text, identities, allow_incomplete=True)
        for d in screened.decisions:
            audit("local", d.action, policy=d.policy, count=d.count)
        review = extract_local_facts(text, screened)
        local_decisions = list(screened.decisions)
        for policy in review.withheld_policies:
            if RULES[policy] == "BLOCK":
                raise Stop(422, "restricted_material", policy)
            action = RULES[policy]
            audit(
                "local", action, policy=policy, metadata={"operation": "fact_release"}
            )
            local_decisions.append(Decision(policy=policy, action=action, count=None))
        content = await state.brane.complete(
            agent.report_messages(review.approved), rid, audit
        )
        extraction, choice = agent.parse_case(content, review.approved)
        audit("model", "schema_and_grounding_validated")
        case = Case(
            case_id=cid,
            category=extraction.category,
            summary=extraction.summary,
            persons=extraction.persons,
            received_at=received,
            brief=brief_for(extraction),
            decisions=[
                *local_decisions,
                Decision(policy="P5", action="ALLOW", count=None),
                decision("P6"),
            ],
        )
        audit("local", "HUMAN_ONLY", policy="P6")
        state.db.finish(
            case,
            rid,
            {**review.private_extraction(extraction), "synthesis": choice.model_dump()},
            screened.mappings,
        )
    except Stop as exc:
        if exc.status != 422 and exc.status < 500:
            raise
        audit(
            "local",
            "BLOCK",
            policy=exc.policy,
            success=False,
            metadata={"reason": exc.reason},
        )
        if exc.policy == "P3" and RULES["P3"] == "LOCAL_ONLY":
            audit("local", "LOCAL_ONLY", policy="P3")
        private_detail = (
            {"local_fact_provenance": review.provenance} if review else None
        )
        action = "LOCAL_ONLY" if exc.policy == "P3" and RULES["P3"] == "LOCAL_ONLY" else "BLOCK"
        held = HeldCase(case_id=cid, received_at=received, policy=exc.policy, hold_reason=exc.reason,
                        status="held_for_review" if exc.status == 422 else "held_unverified",
                        decisions=[Decision(policy=exc.policy, action=action, count=None), decision("P6")])
        state.db.hold(held, rid, private_detail, voice_turn)
        delivery = await deliver(state.db, state.http, state.settings, cid)
        audit("local", "receipt_delivery", policy=exc.policy, metadata={"state": delivery})
        return held
    audit("local", "case_created")
    await deliver(state.db, state.http, state.settings, cid)
    return case
