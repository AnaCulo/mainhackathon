"""Create private credentials for a fresh local synthetic demo."""

import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

template = Path(__file__).resolve().parents[1] / ".env.example"
values = {
    "STORAGE_KEY": Fernet.generate_key().decode(),
    "BACKEND_API_KEY": secrets.token_urlsafe(32),
    "ELEVENLABS_BRIDGE_KEY": secrets.token_urlsafe(32),
}
try:
    fd = os.open(".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit(
        ".env already exists. Keep the existing storage key for its database."
    )
with os.fdopen(fd, "w") as f:
    for line in template.read_text().splitlines():
        key, _, value = line.partition("=")
        print(f"{key}={values.get(key, value)}", file=f)
print(
    "Created .env for synthetic intake. Set the BRANE team key and reviewed policy digest."
)
