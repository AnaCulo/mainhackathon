"""Windows has no os.fchmod. Startup and transcription must not depend on it."""

import os
import stat
from types import SimpleNamespace

from cryptography.fernet import Fernet

from app import stt
from app.database import Database


def _no_fchmod(monkeypatch):
    monkeypatch.delattr(os, "fchmod", raising=False)
    calls = []
    real = os.chmod
    monkeypatch.setattr(os, "chmod", lambda p, m: (calls.append(m), real(p, m)))
    return calls


def test_database_starts_without_fchmod(tmp_path, monkeypatch):
    calls = _no_fchmod(monkeypatch)
    path = tmp_path / "cases.db"
    db = Database(path, Fernet.generate_key().decode())
    with db.connection() as con:
        assert con.execute("SELECT count(*) FROM cases").fetchone()[0] == 0
    assert calls == [stat.S_IREAD | stat.S_IWRITE]


def test_transcription_runs_without_fchmod(monkeypatch):
    calls = _no_fchmod(monkeypatch)
    seen = {}

    class Model:
        def transcribe(self, path, **kwargs):
            seen["audio"] = open(path, "rb").read()
            return [SimpleNamespace(text=" My supervisor shouts. ")], SimpleNamespace(duration=1.2)

    monkeypatch.setattr(stt, "_load", lambda: Model())
    result = stt.transcribe(b"RIFF-synthetic")
    assert result["text"] == "My supervisor shouts."
    assert seen["audio"] == b"RIFF-synthetic" and result["audio_deleted"]
    assert calls == [stat.S_IREAD | stat.S_IWRITE]


def test_posix_still_restricts_to_owner(tmp_path):
    if not hasattr(os, "fchmod"):
        return
    path = tmp_path / "cases.db"
    path.touch(mode=0o644)
    Database(path, Fernet.generate_key().decode())
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
