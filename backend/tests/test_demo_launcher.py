"""Run the presenter's platform command with real n8n and no hosted credential."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.skipif(not os.environ.get("N8N_PACKAGE"), reason="set N8N_PACKAGE to installed n8n 2.48.7")
def test_default_launcher_fails_closed_at_the_presenter_form(tmp_path):
    assert (Path(os.environ["N8N_PACKAGE"]) / "node_modules/n8n/bin/n8n").is_file()
    root = Path(__file__).resolve().parents[2]
    private = tmp_path / "empty-settings"
    private.touch()
    env = {**os.environ, "DEMO_BACKEND_ENV": str(private), "BRANE_API_KEY": "", "STT_WARMUP": "0",
           "BRANE_POLICY_SHA256": "", "PYTHON": sys.executable}
    if os.name == "nt":
        launcher = [shutil.which("pwsh") or "powershell.exe", "-NoProfile", "-File",
                    str(root / "n8n/demo.ps1"), "-Isolated"]
    else:
        launcher = ["bash", str(root / "n8n/demo.sh"), "--isolated"]
    result = subprocess.run(launcher, cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", timeout=180)
    assert result.returncode != 0
    # The default command must submit the form. A fixture-only walkthrough, or a
    # startup error before the UI was reached, cannot generate this correlated receipt.
    receipt, _ = json.JSONDecoder().raw_decode(result.stdout[result.stdout.index("{"):])
    assert receipt["form_http_status"] == 503 and receipt["reason"] == "gateway_not_configured"
    assert receipt["completion_attempts"] == receipt["validated_model_results"] == 0
    assert receipt["n8n_delivery_attempts"] == 1 and receipt["registered"]
