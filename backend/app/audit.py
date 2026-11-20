import json
from datetime import UTC, datetime


def now():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def record(
    db,
    request_id,
    case_id,
    source,
    action,
    *,
    policy="P5",
    count=None,
    route=None,
    success=True,
    metadata=None,
):
    with db.connection() as con:
        con.execute(
            """INSERT INTO audit_events
            (request_id,case_id,timestamp,source,policy_id,action,count,model_route,success,
             brane_status,metadata) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                request_id,
                case_id,
                now(),
                source,
                policy,
                action,
                count,
                route,
                success,
                action if source == "gateway" else None,
                json.dumps(metadata or {}),
            ),
        )
