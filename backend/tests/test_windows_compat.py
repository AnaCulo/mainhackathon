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


# Windows decodes text with the ANSI code page (cp1252) unless told otherwise, which
# mangles or rejects UTF-8 such as the non-ASCII terms in policy.json, and a user folder
# like "Čulo" in a path that Node prints. Every text read, write and decoded subprocess
# output in the project's Python must name UTF-8.
def _text_io_without_encoding(tree):
    import ast

    def mode(call, index):
        args = [a for a in call.args[index:index + 1]] + [k.value for k in call.keywords if k.arg == "mode"]
        return next((a.value for a in args if isinstance(a, ast.Constant) and isinstance(a.value, str)), None)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kwargs = {k.arg for k in node.keywords}
        if "encoding" in kwargs:
            continue
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else None
        if name in {"read_text", "write_text"}:
            yield node
        elif name == "open" and isinstance(f, ast.Name):
            if "b" not in (mode(node, 1) or "r"):
                yield node
        elif name in {"open", "fdopen"} and isinstance(f, ast.Attribute):
            owner = f.value.id if isinstance(f.value, ast.Name) else None
            m = mode(node, 1 if name == "fdopen" else 0)
            if owner not in {"os", "tarfile", "wave", "zipfile", "webbrowser"} and m is not None and "b" not in m:
                yield node
        elif name in {"run", "check_output", "Popen", "call", "check_call"} and any(
                k.arg in {"text", "universal_newlines"} and isinstance(k.value, ast.Constant) and k.value.value is True
                for k in node.keywords):
            yield node


def test_python_text_io_names_utf8():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    files = [p for d in ("backend/app", "backend/scripts", "backend/tests", "n8n", "tests", "voice", "scripts", "brane")
             for p in (root / d).rglob("*.py")]
    found = [f"{p.relative_to(root)}:{n.lineno}"
             for p in files for n in _text_io_without_encoding(ast.parse(p.read_text(encoding="utf-8")))]
    assert len(files) > 40 and found == []
