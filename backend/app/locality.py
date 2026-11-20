"""One definition of "this request comes from the demo page on this machine".

The primary controls are the loopback client address and a strictly parsed local Host header
(tunnels such as Cloudflare or Tailscale Funnel arrive with their own public Host). The proxy
header list is defence in depth on top of that.

Used by the outer ASGI guard (before routing and body parsing), by the request-size limit (the
only place a larger body is allowed) and by the routes' own dependency as a second layer.
"""
import re

from starlette.responses import JSONResponse

LOOPBACK_CLIENTS = {"127.0.0.1", "::1"}
# Any header a tunnel, CDN or reverse proxy adds. Prefixes cover cf-*, x-forwarded-*, etc.
PROXY_HEADERS = {"forwarded", "via", "x-real-ip", "true-client-ip", "cdn-loop", "x-original-host",
                 "x-client-ip", "client-ip", "x-cluster-client-ip", "fastly-client-ip", "x-original-forwarded-for"}
PROXY_PREFIXES = ("cf-", "x-forwarded-", "x-envoy-", "x-amzn-", "fly-", "ngrok-", "tailscale-",
                  "x-tailscale-", "x-vercel-", "x-azure-", "x-appengine-")
LOCAL_HOST_RE = re.compile(r"(?:\[::1\]|127\.0\.0\.1|localhost)(?::(\d{1,5}))?", re.IGNORECASE)
SAME_ORIGIN_FETCH = {"same-origin", "none"}


def _headers(scope):
    return [(k.decode("latin-1").lower(), v.decode("latin-1")) for k, v in scope.get("headers", ())]


def proxied(headers):
    return any(k in PROXY_HEADERS or k.startswith(PROXY_PREFIXES) for k, _ in headers)


def local_host(host):
    """Strict: exactly a loopback name plus an optional valid port. Rejects lists, junk ports."""
    m = LOCAL_HOST_RE.fullmatch((host or "").strip())
    return bool(m) and (m[1] is None or 0 < int(m[1]) < 65536)


def is_ui_path(path):
    return path == "/" or path == "/ui" or path.startswith("/ui/")


def is_local(scope):
    """Development mode, loopback client, local Host header and no proxy/tunnel headers."""
    app = scope.get("app")
    settings = getattr(getattr(app, "state", None), "settings", None)
    if getattr(settings, "environment", None) != "development":
        return False
    client = (scope.get("client") or ("",))[0]
    headers = _headers(scope)
    hosts = [v for k, v in headers if k == "host"]
    return (
        client in LOOPBACK_CLIENTS
        and len(hosts) == 1
        and local_host(hosts[0])
        and not proxied(headers)
    )


def same_origin(scope):
    """Reject requests a browser marks as coming from another site (CSRF defence)."""
    headers = _headers(scope)
    fetch_site = next((v.lower() for k, v in headers if k == "sec-fetch-site"), None)
    if fetch_site is not None and fetch_site not in SAME_ORIGIN_FETCH:
        return False
    origin = next((v for k, v in headers if k == "origin"), None)
    if origin is None:
        return True  # curl / same-origin GET; the content-type rules still apply
    host = next((v for k, v in headers if k == "host"), "")
    return origin.lower() in {"http://" + host.lower(), "https://" + host.lower()}


class LocalGuard:
    """Outermost middleware: the page and /ui/* do not exist off loopback (404 for any method,
    any body, before routing or JSON decoding); state-changing /ui calls must be same-origin."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and is_ui_path(scope.get("path", "")):
            if not is_local(scope):
                return await JSONResponse({"detail": "Not Found"}, 404)(scope, receive, send)
            if scope.get("method") not in {"GET", "HEAD"} and not same_origin(scope):
                return await JSONResponse({"error": "cross_origin"}, 403)(scope, receive, send)
        return await self.app(scope, receive, send)
