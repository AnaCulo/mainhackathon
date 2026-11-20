"""Launch one disposable presenter instance from either platform's demo command."""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
LOCAL = "http://127.0.0.1"
http = build_opener(ProxyHandler({}))


def revision():
    # An archive or dirty checkout needs an identity for its actual code as well as Git HEAD.
    digest = hashlib.sha256()
    sources = [*ROOT.glob("backend/app/**/*.py"), ROOT / "backend/app/policy.json",
               *ROOT.glob("n8n/*.mjs"), *ROOT.glob("n8n/demo.*"), ROOT / "n8n/protected-case.json",
               ROOT / "n8n/live-trace.py"]
    for file in sorted(sources):
        digest.update(file.relative_to(ROOT).as_posix().encode() + b"\0" + hashlib.sha256(file.read_bytes()).digest())
    try:
        if not (ROOT / ".git").exists():
            raise FileNotFoundError
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        head = None
    return {"checkout_head": head, "presenter_source_sha256": digest.hexdigest()}


def start(stack, args, env, log, cwd):
    output = stack.enter_context(log.open("ab"))
    process = subprocess.Popen(args, cwd=cwd, env=env, stdout=output, stderr=output)

    def stop():
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    stack.callback(stop)
    return process


def wait_for(process, port, path, expected=200):
    from urllib.error import HTTPError, URLError

    for _ in range(120):
        if process.poll() is not None:
            raise SystemExit(f"Service on port {port} exited before readiness. Check its private log.")
        try:
            with http.open(f"{LOCAL}:{port}{path}", timeout=1) as response:
                if response.status == expected:
                    return
        except HTTPError as exc:
            if exc.code == expected:
                return
        except (URLError, TimeoutError):
            pass
        time.sleep(0.5)
    raise SystemExit(f"Service on port {port} did not become ready.")


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("hold", "offline", "trace", "python", "voice", "isolated"):
        parser.add_argument("--" + flag, action="store_true")
    parser.add_argument("--offline-python-backend")
    args = parser.parse_args()
    if args.offline_python_backend and not args.offline:
        parser.error('The historical Python compatibility test requires explicit offline mode.')
    if args.offline and (args.trace or args.python or args.voice):
        parser.error("Choose either a live run or an offline walkthrough.")
    if args.isolated and (args.offline or args.python or args.voice):
        parser.error("The legacy test harnesses use fixed ports. Use --isolated for presenter runs.")

    node = shutil.which("node")
    if not node or not subprocess.check_output([node, "--version"], text=True).startswith("v24."):
        raise SystemExit("Use Node 24 for this demo.")
    if not args.offline:
        import uvicorn  # noqa: F401 -- fail before provisioning if dependencies are missing
        from cryptography.fernet import Fernet
        from dotenv import dotenv_values

    n8n_port, register_port, intake_port, broker_port = 5689, 8788, 8000, 5679
    if args.isolated:
        with ExitStack() as sockets:
            listeners = [sockets.enter_context(socket.socket()) for _ in range(4)]
            for listener in listeners:
                listener.bind(("127.0.0.1", 0))
            n8n_port, register_port, intake_port, broker_port = [s.getsockname()[1] for s in listeners]
    ports = [n8n_port, register_port, broker_port] + ([] if args.offline else [intake_port])
    for port in ports:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise SystemExit(f"Demo port {port} is already in use.")

    # n8n, the register and npm need no access to the team credential.
    local_env = {k: v for k, v in os.environ.items() if not k.upper().startswith(
        ("BRANE_", "OPENAI_", "BACKEND_API_KEY", "STORAGE_KEY", "ELEVENLABS_BRIDGE_KEY"))}
    package = Path(os.getenv("N8N_PACKAGE", Path(tempfile.gettempdir()) / "culo-n8n-2-48-7"))
    cli = package / "node_modules/n8n/bin/n8n"
    if not cli.is_file():
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        subprocess.run([npm, "install", "--prefix", str(package), "n8n@2.48.7",
                        "--no-audit", "--no-fund"], env=local_env, check=True)

    runtime = Path(tempfile.mkdtemp(prefix="culo-runtime-"))
    print(f"Private service logs: {runtime}", flush=True)
    n8n_env = dict(local_env, N8N_USER_FOLDER=str(runtime), N8N_HOST="127.0.0.1",
                   N8N_LISTEN_ADDRESS="127.0.0.1", N8N_PORT=str(n8n_port), N8N_PROTOCOL="http",
                   N8N_RUNNERS_BROKER_PORT=str(broker_port),
                   N8N_SECURE_COOKIE="false", N8N_DIAGNOSTICS_ENABLED="false",
                   N8N_VERSION_NOTIFICATIONS_ENABLED="false", N8N_TEMPLATES_ENABLED="false",
                   N8N_LOG_LEVEL="error", EXECUTIONS_DATA_SAVE_ON_SUCCESS="none",
                   EXECUTIONS_DATA_SAVE_ON_ERROR="none", EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS="false",
                   EXECUTIONS_DATA_SAVE_ON_PROGRESS="false")
    with ExitStack() as stack:
        n8n = start(stack, [node, str(cli), "start"], n8n_env, runtime / "n8n.log", ROOT)
        wait_for(n8n, n8n_port, "/healthz/readiness")
        port_env = {"DEMO_N8N_PORT": str(n8n_port), "DEMO_REGISTER_PORT": str(register_port),
                    "DEMO_INTAKE_PORT": str(intake_port)}
        config = Path(subprocess.check_output([node, "n8n/setup-demo.mjs"], cwd=ROOT,
                                               env=local_env | port_env, text=True).strip())
        (config.parent / "revision.json").write_text(json.dumps(revision()), encoding="utf-8")
        demo = dict(line.split("=", 1) for line in config.read_text().splitlines())
        register = start(stack, [node, "n8n/service.mjs"], local_env | demo |
                         {"DEMO_INTAKE": "0" if args.offline else "1"}, runtime / "register.log", ROOT)
        wait_for(register, register_port, "/review", 401)
        if args.offline:
            print("Offline walkthrough with simulated BRANE.", flush=True)
            cmd = [node, "n8n/walkthrough.mjs"] + (["--hold"] if args.hold else [])
            subprocess.run(cmd, env=local_env | demo, cwd=ROOT, check=True)
            if args.hold:
                case = json.loads((config.parent / "walkthrough.json").read_text(encoding="utf-8"))
                print(f"Open the pending decision: {case['reviewUrl']}", flush=True)
            if args.offline_python_backend:
                subprocess.run([sys.executable, "n8n/verify-python.py", args.offline_python_backend,
                                str(config)], env=local_env, cwd=ROOT, check=True)
        else:
            private = Path(os.environ.get("DEMO_BACKEND_ENV", ROOT / "backend/.env"))
            if "DEMO_BACKEND_ENV" in os.environ and not private.is_file():
                raise SystemExit("DEMO_BACKEND_ENV must name the private backend environment file.")
            values = dotenv_values(private, interpolate=False) if private.is_file() else {}
            gateway = {k: os.environ.get(k, values.get(k, "")) for k in (
                "BRANE_API_KEY", "BRANE_POLICY_SHA256", "BRANE_BASE_URL", "BRANE_MODEL",
                "BRANE_TIMEOUT_SECONDS") if k in os.environ or values.get(k)}
            # New storage and caller credentials belong only to this disposable intake process.
            directory = config.parent
            backend = {"DATABASE_URL": "sqlite:///" + str(directory / "intake.sqlite"),
                       "STORAGE_KEY": Fernet.generate_key().decode(),
                       "BACKEND_API_KEY": secrets.token_urlsafe(32),
                       "ELEVENLABS_BRIDGE_KEY": secrets.token_urlsafe(32)}
            caller_config = directory / "backend.env"
            with open(caller_config, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as f:
                for key, value in backend.items():
                    print(f"{key}={value}", file=f)
            intake_env = local_env | backend | gateway | port_env | {
                "HANDLER_REF": demo["HANDLER_REF"], "HANDLER_PASSWORD": demo["HANDLER_PASSWORD"],
                "N8N_WEBHOOK_URL": demo["N8N_WEBHOOK_URL"], "N8N_WEBHOOK_SECRET": demo["N8N_TOKEN"]}
            service = start(stack, [sys.executable, "-m", "uvicorn", "app.demo:create_demo", "--factory",
                                    "--app-dir", str(ROOT / "backend"), "--host", "127.0.0.1",
                                    "--port", str(intake_port), "--no-access-log"], intake_env,
                            runtime / "backend.log", directory)
            wait_for(service, intake_port, "/health")
            print(f"Submit at {LOCAL}:{intake_port}/demo as handler. Private login in {config}", flush=True)
            if args.trace or not args.hold:
                subprocess.run([sys.executable, "n8n/live-trace.py", str(config)], cwd=ROOT,
                               env=local_env, check=True)
            if args.python:
                subprocess.run([sys.executable, "n8n/live-python.py", str(config), str(caller_config),
                                "data/synthetic_reports.json"], cwd=ROOT, env=local_env, check=True)
            if args.voice:
                subprocess.run([sys.executable, "voice/harness.py", str(config), str(caller_config),
                                "evidence"], cwd=ROOT, env=local_env, check=True)
        if args.hold:
            print(f"Handler queue: {LOCAL}:{register_port}/review. Private login in {config}", flush=True)
            input("Press Enter to stop this instance. ")


if __name__ == "__main__":
    run()
