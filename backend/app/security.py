import secrets

from fastapi import HTTPException, Request


class Stop(Exception):
    """Internal, content-free reason codes only."""

    def __init__(self, status: int, reason: str, policy: str = "P5"):
        self.status, self.reason, self.policy = status, reason, policy
        super().__init__(reason)


def authenticate(request: Request, key: str):
    if not key:
        raise HTTPException(503, "Endpoint not configured")
    actual = request.headers.get("Authorization", "").encode()
    if not secrets.compare_digest(actual, f"Bearer {key}".encode()):
        raise HTTPException(
            401, "Authentication required", headers={"WWW-Authenticate": "Bearer"}
        )


def backend_auth(request: Request):
    authenticate(request, request.app.state.settings.backend_key)


def bridge_auth(request: Request):
    authenticate(request, request.app.state.settings.bridge_key)
