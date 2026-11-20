from starlette.responses import JSONResponse

from .locality import is_local


class RequestLimit:
    """Bound JSON intake before decoding, including requests without Content-Length."""

    # Push-to-talk audio (16 kHz mono WAV; the page stops at 60 s, about 1.9 MB) is larger than any JSON
    # body; it is only accepted by the loopback-only /ui/stt route, which re-checks the size.
    PATH_LIMITS = {"/ui/stt": 2560 * 1024}

    def __init__(self, app, limit=160 * 1024):
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        limit = self.limit
        if scope.get("path") in self.PATH_LIMITS and is_local(scope):  # never widened off loopback
            limit = self.PATH_LIMITS[scope["path"]]
        body = bytearray()
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            body.extend(event.get("body", b""))
            if len(body) > limit:
                return await JSONResponse({"error": "request_too_large"}, 413)(
                    scope, receive, send
                )
            if not event.get("more_body"):
                break
        pending = True

        async def bounded_receive():
            nonlocal pending
            if pending:
                pending = False
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
