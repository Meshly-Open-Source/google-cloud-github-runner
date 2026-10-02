"""ASGI adapter. Same decision, different transport.

As with the WSGI adapter: no policy logic here. The pair exists because the
two consumers are different stacks, not because the rules differ, and the only
way to keep the rules identical is for both to be a thin translation over
enforcement.enforce().

INSTALLATION, FOR A STARLETTE/FASTAPI APPLICATION
-------------------------------------------------
    from ipfilter.asgi import IpPolicyMiddleware, asgi_route_paths

    REGISTRY.assert_routes_covered(asgi_route_paths(app))
    app.add_middleware(IpPolicyMiddleware, config=config)

Add it OUTERMOST of the middleware stack you want it in front of. Starlette
applies middleware in reverse registration order, so this should be registered
LAST if it must see the request before anything else -- including before any
middleware that rewrites forwarded headers. A proxy-headers middleware that
normalises X-Forwarded-For and runs first would hand this a chain that is no
longer the chain the configured index was measured against.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from .enforcement import DEFAULT_BODY, FilterConfig, enforce

Receive = Callable[[], Awaitable[dict]]
Send = Callable[[dict], Awaitable[None]]


def asgi_route_paths(app: Any) -> list[str]:
    """Every path the application routes, read from the live router.

    Mounted sub-applications are returned by their mount path only; their
    children are not enumerated, which is correct for a prefix policy and
    worth knowing if you intended an exact one.
    """
    routes = getattr(app, "routes", None)
    if routes is None:
        router = getattr(app, "router", None)
        routes = getattr(router, "routes", None)
    if routes is None:
        raise TypeError(
            f"{app!r} exposes no .routes or .router.routes; this expects a Starlette-style "
            "application. The wrong object here would make the coverage assertion vacuous."
        )
    paths = {getattr(route, "path", None) for route in routes}
    return sorted(path for path in paths if isinstance(path, str))


def _header(scope: dict, name: str) -> str | None:
    """First value of a header from an ASGI scope, or None if absent.

    ASGI header names are lowercase bytes. A repeated header is returned as
    repeated entries rather than being joined, so the FIRST is taken --
    matching what a WSGI server does when it folds duplicates, so the two
    adapters see the same value for the same request.
    """
    wanted = name.lower().encode("latin-1")
    for key, value in scope.get("headers", []) or []:
        if key == wanted:
            return value.decode("latin-1")
    return None


def _peer(scope: dict) -> str | None:
    client = scope.get("client")
    if not client:
        return None
    return str(client[0])


class IpPolicyMiddleware:
    """Blocks requests whose client address no policy permits."""

    def __init__(
        self,
        app: Callable[[dict, Receive, Send], Awaitable[None]],
        config: FilterConfig,
        *,
        logger: logging.Logger | None = None,
        body: bytes = DEFAULT_BODY,
    ):
        self._app = app
        self._config = config
        self._logger = logger
        self._body = body

    async def __call__(self, scope: dict, receive: Receive, send: Send) -> None:
        # Only HTTP is filtered. `lifespan` must pass through or the
        # application never starts; `websocket` passes through because a
        # rejection there needs a websocket-shaped close rather than a 403
        # body, and a half-correct rejection is worse than declining to
        # handle the protocol. If a consumer ever serves a websocket that
        # needs this policy, that is a deliberate addition here, with its own
        # tests -- not an oversight to be papered over with the HTTP path.
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        outcome = enforce(
            self._config,
            path=scope.get("path", "") or "/",
            method=scope.get("method", "") or "GET",
            header_value=_header(scope, self._config.forwarded_for_header),
            peer=_peer(scope),
            logger=self._logger,
        )
        if outcome.allowed:
            await self._app(scope, receive, send)
            return

        # Constant body, for the same reason as the WSGI adapter: the response
        # must not tell a caller why it was blocked.
        await send(
            {
                "type": "http.response.start",
                "status": outcome.status,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", str(len(self._body)).encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": self._body})
