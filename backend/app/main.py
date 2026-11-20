import logging
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .brane_client import BraneClient
from .config import Settings
from .database import Database
from .request_limit import RequestLimit
from .routes import chat, reports, ui
from .security import Stop


def create_app(settings=None, transport=None):
    @asynccontextmanager
    async def lifespan(app):
        s = settings or Settings.load()
        app.state.settings = s
        if not s.storage_key:
            raise RuntimeError("Configure STORAGE_KEY before starting the backend")
        app.state.db = Database(s.db, s.storage_key)
        # A secret webhook URL must never appear in HTTP client request logs.
        for name in ("httpx", "httpcore"):
            logging.getLogger(name).setLevel(logging.WARNING)
        async with httpx.AsyncClient(
            transport=transport, trust_env=False, follow_redirects=False
        ) as client:
            app.state.http = client
            app.state.brane = BraneClient(s, client)
            yield

    app = FastAPI(title="Synthetic whistleblower intake", lifespan=lifespan)

    app.add_middleware(RequestLimit)

    @app.middleware("http")
    async def correlate(request: Request, call_next):
        request.state.rid = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.rid
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(Stop)
    async def stopped(request, exc):
        return JSONResponse(
            {"error": exc.reason, "request_id": request.state.rid},
            status_code=exc.status,
        )

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        # Field locations and error types only, never input values: enough to see which
        # unexpected field a client (e.g. the ElevenLabs Custom LLM caller) sent.
        shape = sorted({(".".join(str(p) for p in e.get("loc", ())), e.get("type")) for e in exc.errors()})
        logging.getLogger("uvicorn.error").warning(
            "invalid_request %s %s %s", request.state.rid, request.url.path, shape[:20]
        )
        return JSONResponse(
            {"error": "invalid_request", "request_id": request.state.rid},
            status_code=422,
        )

    @app.get("/health")
    async def health():
        client = app.state.brane
        ready = client.configured and client.available is True
        return {
            "backend": "up",
            "ready": ready,
            "brane_configured": client.configured,
            "brane_last_check": (
                "unknown"
                if client.available is None
                else "available"
                if client.available
                else "unavailable"
            ),
        }

    app.include_router(reports.router)
    app.include_router(chat.router)
    app.include_router(ui.router)
    return app


app = create_app()
