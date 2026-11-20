import os
import secrets
import stat

from fastapi import HTTPException, Request


class Stop(Exception):
    """Internal, content-free reason codes only."""

    def __init__(self, status: int, reason: str, policy: str = "P5"):
        self.status, self.reason, self.policy = status, reason, policy
        super().__init__(reason)


def owner_only(fd: int, path) -> None:
    """Restrict a just-opened file to its owner (0600).

    POSIX tightens the open descriptor. Windows has no os.fchmod and no POSIX
    mode bits: os.chmod only toggles read-only there, and access is governed by
    the ACL inherited from the user's profile folder, which already excludes
    other standard users.
    """
    if hasattr(os, "fchmod"):
        os.fchmod(fd, 0o600)
    else:
        os.chmod(path, stat.S_IREAD | stat.S_IWRITE)


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
