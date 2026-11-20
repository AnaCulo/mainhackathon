import hashlib
import hmac
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from uuid import uuid4

from cryptography.fernet import Fernet

from .audit import now
from .security import Stop


class Database:
    def __init__(self, path, key):
        self.path, self.key = path, key.encode()
        self.box = Fernet(self.key)
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        os.fchmod(fd, 0o600)
        os.close(fd)
        with self.connection() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY, idem TEXT UNIQUE, fingerprint TEXT, owner TEXT,
                lease REAL, received_at TEXT, created_at TEXT, updated_at TEXT,
                status TEXT, brane_status TEXT, category TEXT, protected_summary TEXT,
                evidence BLOB, extraction BLOB, payload TEXT);
            CREATE TABLE IF NOT EXISTS identity_mappings (
                case_id TEXT REFERENCES cases, pseudonym TEXT, original_identity BLOB, identity_type TEXT);
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id INTEGER PRIMARY KEY, request_id TEXT, case_id TEXT, timestamp TEXT,
                source TEXT, policy_id TEXT, action TEXT, count INTEGER, brane_status TEXT,
                model_route TEXT, success INTEGER, metadata TEXT);
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, turns BLOB, revision INTEGER, frozen INTEGER DEFAULT 0,
                asked TEXT, case_id TEXT REFERENCES cases);
            CREATE TABLE IF NOT EXISTS outbox (
                case_id TEXT PRIMARY KEY REFERENCES cases, state TEXT, owner TEXT, lease REAL,
                attempts INTEGER DEFAULT 0, updated_at TEXT);
            CREATE TABLE IF NOT EXISTS database_identity (singleton INTEGER PRIMARY KEY, marker BLOB);
            """)
            con.execute(
                "INSERT OR IGNORE INTO database_identity VALUES(1,?)",
                (self.seal("intake"),),
            )
            self.unseal(
                con.execute(
                    "SELECT marker FROM database_identity WHERE singleton=1"
                ).fetchone()[0]
            )

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.path, timeout=5)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA foreign_keys=ON")
            with con:
                yield con
        finally:
            con.close()

    def seal(self, value):
        return self.box.encrypt(json.dumps(value, ensure_ascii=False).encode())

    def unseal(self, value):
        return json.loads(self.box.decrypt(value))

    def digest(self, value):
        return hmac.new(self.key, value.encode(), hashlib.sha256).hexdigest()

    def reserve(self, key, data, owner):
        fingerprint = self.digest(json.dumps(data, sort_keys=True))
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute(
                "SELECT * FROM cases WHERE idem=?", (self.digest(key),)
            ).fetchone()
            if row:
                if row["fingerprint"] != fingerprint:
                    raise Stop(409, "idempotency_conflict")
                if row["payload"]:
                    return (
                        row["case_id"],
                        row["received_at"],
                        json.loads(row["payload"]),
                    )
                if row["owner"] and row["lease"] > time.time():
                    raise Stop(409, "request_in_progress")
                cid, received = row["case_id"], row["received_at"]
            else:
                cid, received = "WB-" + uuid4().hex, now()
                con.execute(
                    """INSERT INTO cases(case_id,idem,fingerprint,received_at,created_at,evidence)
                    VALUES(?,?,?,?,?,?)""",
                    (
                        cid,
                        self.digest(key),
                        fingerprint,
                        received,
                        received,
                        self.seal(data),
                    ),
                )
            con.execute(
                """UPDATE cases SET owner=?,lease=?,updated_at=?,status='processing',
                brane_status='pending' WHERE case_id=?""",
                (owner, time.time() + 300, now(), cid),
            )
            return cid, received, None

    def hold(self, cid, owner, reason, private_detail=None):
        with self.connection() as con:
            con.execute(
                """UPDATE cases SET owner=NULL,status='held_for_review',brane_status=?,
                updated_at=?,extraction=? WHERE case_id=? AND owner=?""",
                (
                    reason,
                    now(),
                    self.seal(private_detail) if private_detail else None,
                    cid,
                    owner,
                ),
            )

    def finish(self, case, owner, extraction, mappings):
        with self.connection() as con:
            changed = con.execute(
                """UPDATE cases SET owner=NULL,status='awaiting_human_review',
                brane_status='ok',category=?,protected_summary=?,updated_at=?,extraction=?,payload=?
                WHERE case_id=? AND owner=?""",
                (
                    case.category,
                    case.summary,
                    now(),
                    self.seal(extraction),
                    case.model_dump_json(),
                    case.case_id,
                    owner,
                ),
            ).rowcount
            if not changed:
                raise Stop(409, "lease_expired")
            for token, name, kind in mappings:
                con.execute(
                    "INSERT INTO identity_mappings VALUES(?,?,?,?)",
                    (case.case_id, token, self.seal(name), kind),
                )
            con.execute(
                "INSERT INTO outbox(case_id,state,updated_at) VALUES(?,'pending',?)",
                (case.case_id, now()),
            )

    def session(self, session_id):
        with self.connection() as con:
            row = con.execute(
                "SELECT * FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
        return (
            (
                self.unseal(row["turns"]),
                row["revision"],
                row["frozen"],
                json.loads(row["asked"]),
            )
            if row
            else ([], 0, 0, [])
        )

    def save_turn(self, sid, old_revision, turns, asked, *, frozen=0):
        with self.connection() as con:
            saved = con.execute(
                """INSERT INTO sessions(id,revision,turns,asked,frozen) VALUES(?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET turns=excluded.turns,revision=excluded.revision,
                asked=excluded.asked,frozen=excluded.frozen WHERE sessions.revision=? AND sessions.frozen=0""",
                (
                    sid,
                    old_revision + 1,
                    self.seal(turns),
                    json.dumps(asked),
                    frozen,
                    old_revision,
                ),
            ).rowcount
            if not saved:
                raise Stop(409, "stale_history")

    def freeze(self, sid, revision):
        with self.connection() as con:
            if not con.execute(
                "UPDATE sessions SET frozen=1 WHERE id=? AND revision=? AND frozen != 2",
                (sid, revision),
            ).rowcount:
                raise Stop(409, "unknown_or_stale_session")
            return self.unseal(
                con.execute("SELECT turns FROM sessions WHERE id=?", (sid,)).fetchone()[
                    0
                ]
            )
