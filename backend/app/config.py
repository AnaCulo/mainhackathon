import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

HOSTED = "https://brane.ai-z.io/api/v1"
MODEL = "openrouter:openai/gpt-6-luna"


@dataclass(frozen=True)
class Settings:
    db: Path
    storage_key: str
    backend_key: str
    bridge_key: str
    base: str
    api_key: str
    model: str
    timeout: float
    policy_digest: str
    webhook: str
    webhook_key: str
    environment: str

    @classmethod
    def load(cls):
        load_dotenv(Path(".env"), override=False)
        get = os.environ.get
        url = get("DATABASE_URL", "sqlite:///./whistleblower.db")
        if not url.startswith("sqlite:///") or not url[10:]:
            raise ValueError("A file-backed SQLite database is required")
        settings = cls(
            Path(url[10:]).resolve(),
            get("STORAGE_KEY", ""),
            get("BACKEND_API_KEY", ""),
            get("ELEVENLABS_BRIDGE_KEY", ""),
            get("BRANE_BASE_URL", HOSTED).rstrip("/"),
            get("BRANE_API_KEY", ""),
            get("BRANE_MODEL", MODEL),
            float(get("BRANE_TIMEOUT_SECONDS", "30")),
            get("BRANE_POLICY_SHA256", ""),
            get("N8N_WEBHOOK_URL", ""),
            get("N8N_WEBHOOK_SECRET", ""),
            get("APP_ENV", "development"),
        )
        if (
            settings.base != HOSTED
            or settings.model != MODEL
            or not 1 <= settings.timeout <= 120
        ):
            raise ValueError("Unsupported gateway, model or timeout")
        if settings.backend_key and settings.backend_key == settings.bridge_key:
            raise ValueError("Use distinct intake and voice credentials")
        if settings.webhook:
            parts = urlsplit(settings.webhook)
            if not (
                parts.scheme == "https"
                and parts.hostname
                and not parts.username
                and not parts.password
                and not parts.fragment
                and settings.webhook_key
            ):
                raise ValueError("Use an authenticated HTTPS webhook")
        return settings
