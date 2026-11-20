"""Build flat hand-in archives from immutable Git blobs and verify their manifest."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "submission"
MANIFEST = "submission/MANIFEST.json"
ARCHIVES = ("working-agent.zip", "BuilderBase-package.zip")
SECRET = re.compile(
    rb"brn_" rb"live_|sk-[A-Za-z0-9]{20,}|Bearer [A-Za-z0-9_-]{24,}|"
    rb"xi-api-key: [A-Za-z0-9]|API_KEY" rb"""=(?!(?:""|'')(?=[\s,);]|$))[^\s]+""", re.IGNORECASE
)


def excluded(name):
    path = PurePosixPath(name)
    return (name == MANIFEST or any(part.startswith(".env") and part != ".env.example"
                                    for part in path.parts)
            or set(path.parts).intersection({"node_modules", "__pycache__"})
            or path.name.lower().endswith((".db", ".sqlite", ".sqlite3", ".zip", ".pyc",
                                           ".sqlite-wal", ".sqlite-shm", ".db-wal", ".db-shm")))


def git(*args, env=None):
    return subprocess.check_output(["git", *args], cwd=ROOT, env=env)


def build():
    head = git("rev-parse", "HEAD").decode().strip()
    with tempfile.TemporaryDirectory(dir=DEST) as folder:
        stage = Path(folder)
        env = {**os.environ, "GIT_INDEX_FILE": str(stage / "index")}
        git("read-tree", head, env=env)
        entries = git("ls-files", "--stage", "-z", env=env).split(b"\0")
        files = {}
        created = datetime.now(timezone.utc)
        with zipfile.ZipFile(stage / ARCHIVES[0], "w", zipfile.ZIP_DEFLATED) as archive:
            for entry in filter(None, entries):
                meta, encoded = entry.split(b"\t", 1)
                name = encoded.decode()
                if excluded(name):
                    continue
                mode, oid, _ = meta.decode().split()
                if mode not in {"100644", "100755"}:
                    raise SystemExit(f"Unsupported Git entry at {name}")
                data = git("cat-file", "blob", oid)
                if SECRET.search(data):
                    raise SystemExit(f"Secret scan rejected {name}. No archive published.")
                info = zipfile.ZipInfo(name, created.timetuple()[:6])
                info.create_system = 3
                info.external_attr = int(mode, 8) << 16
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
                files[name] = hashlib.sha256(data).hexdigest()
            policy = json.loads(archive.read("backend/app/policy.json"))["version"]
            manifest = json.dumps({"git_head": head, "policy_version": policy,
                                   "timestamp": created.isoformat(), "files": files},
                                  ensure_ascii=False, indent=2).encode() + b"\n"
            archive.writestr(MANIFEST, manifest)
        with zipfile.ZipFile(stage / ARCHIVES[0]) as archive:
            if set(archive.namelist()) != files.keys() | {MANIFEST} or archive.testzip():
                raise SystemExit("Archive verification failed")
            for name, digest in files.items():
                if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                    raise SystemExit(f"Manifest mismatch at {name}")
        # Each hand-in slot receives a standalone, directly extractable repository.
        shutil.copyfile(stage / ARCHIVES[0], stage / ARCHIVES[1])
        (stage / "MANIFEST.json").write_bytes(manifest)
        for name in (*ARCHIVES, "MANIFEST.json"):
            os.replace(stage / name, DEST / name)
        print(f"Secret scan passed. Verified {len(files)} files at {head} ({policy}).")


if __name__ == "__main__":
    build()
