from functools import partial

from . import agent
from .audit import record
from .models import Case, Decision
from .n8n_client import deliver
from .policies import RULES, decision, screen
from .security import Stop


async def submit(state, rid, key, text, identities, source, reporter_mode):
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
        return Case.model_validate(cached)
    try:
        screened = screen(text, identities)
        for d in screened.decisions:
            audit("local", d.action, policy=d.policy, count=d.count)
        content = await state.brane.complete(
            agent.report_messages(screened), rid, audit
        )
        extraction = agent.parse_case(content, screened)
        audit("model", "schema_and_grounding_validated")
        case = Case(
            case_id=cid,
            category=extraction.category,
            summary=extraction.summary,
            persons=extraction.persons,
            received_at=received,
            decisions=[
                *screened.decisions,
                Decision(policy="P5", action="ALLOW", count=None),
                decision("P6"),
            ],
        )
        audit("local", "HUMAN_ONLY", policy="P6")
        state.db.finish(case, rid, extraction.model_dump(), screened.mappings)
    except Stop as exc:
        audit(
            "local",
            "BLOCK",
            policy=exc.policy,
            success=False,
            metadata={"reason": exc.reason},
        )
        if exc.policy == "P3" and RULES["P3"] == "LOCAL_ONLY":
            audit("local", "LOCAL_ONLY", policy="P3")
        state.db.hold(cid, rid, exc.reason)
        raise
    audit("local", "case_created")
    await deliver(state.db, state.http, state.settings, cid)
    return case
