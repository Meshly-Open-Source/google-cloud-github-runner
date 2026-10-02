"""WSGI adapter. Translates a WSGI environ into an enforce() call and back.

This file deliberately contains no policy logic. Everything that decides
anything is in enforcement.py, so that this adapter and the ASGI one cannot
drift apart. If you are about to add a condition here, it belongs there.

INSTALLATION, FOR A FLASK APPLICATION
-------------------------------------
    from ipfilter.wsgi import IpPolicyMiddleware, flask_route_paths

    app = create_app()
    config = FilterConfig(registry=REGISTRY, resolver=RESOLVER, chain_index=...)
    REGISTRY.assert_routes_covered(flask_route_paths(app))   # fatal if a route is unpoliced
    app.wsgi_app = IpPolicyMiddleware(app.wsgi_app, config)

Wrapping `app.wsgi_app` rather than replacing `app` keeps the Flask object
intact for anything that introspects it, and puts the filter outside Flask's
routing -- which is the point, because it then also covers paths Flask would
have 404'd.

The coverage assertion runs BEFORE the wrap, and it raises. A process that
cannot establish which routes it is protecting must not start serving; the
alternative is a filter that is live and has a hole in it.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Iterable

from .enforcement import DEFAULT_BODY, FilterConfig, enforce

StartResponse = Callable[[str, list[tuple[str, str]]], Any]

STATUS_LINES = {
    403: "403 Forbidden",
    404: "404 Not Found",
}


def flask_route_paths(app: Any) -> list[str]:
    """Every path Flask will route, read from the built url_map.

    Read from the live object, not from source. A grep cannot see a blueprint
    registered conditionally, a route added in a loop, or a url_prefix
    assembled from a variable -- and those are exactly the routes a human
    misses too.

    Flask's converter syntax (`/jobs/<int:job_id>`) is returned as-is. The
    policy table matches those with a prefix entry; an exact entry containing
    a converter would never match a real request path, which is worth knowing
    before writing one.
    """
    rules = getattr(getattr(app, "url_map", None), "iter_rules", None)
    if rules is None:
        raise TypeError(
            f"{app!r} has no url_map.iter_rules; this expects a Flask application object. "
            "Passing the wrong object here would make the coverage assertion vacuous."
        )
    return sorted({rule.rule for rule in rules()})


class IpPolicyMiddleware:
    """Blocks requests whose client address no policy permits."""

    def __init__(
        self,
        wsgi_app: Callable[[dict, StartResponse], Iterable[bytes]],
        config: FilterConfig,
        *,
        logger: logging.Logger | None = None,
        body: bytes = DEFAULT_BODY,
    ):
        self._app = wsgi_app
        self._config = config
        self._logger = logger
        self._body = body

    def __call__(self, environ: dict, start_response: StartResponse) -> Iterable[bytes]:
        header_name = "HTTP_" + self._config.forwarded_for_header.upper().replace("-", "_")
        # `in` rather than `.get(...) or None`: an absent header and an empty
        # one are different conditions with different reasons, and the record
        # distinguishes them.
        header_value = environ[header_name] if header_name in environ else None

        outcome = enforce(
            self._config,
            path=environ.get("PATH_INFO", "") or "/",
            method=environ.get("REQUEST_METHOD", "") or "GET",
            header_value=header_value,
            peer=environ.get("REMOTE_ADDR"),
            logger=self._logger,
        )
        if outcome.allowed:
            return self._app(environ, start_response)

        status = STATUS_LINES.get(outcome.status, f"{outcome.status} Forbidden")
        # The body is a constant. It does not echo the address, the chain, the
        # policy name or the reason: telling a caller which of those got them
        # blocked turns the filter into an oracle for probing the policy. The
        # diagnosis lives in the log record, where the operator is.
        start_response(
            status,
            [
                ("Content-Type", "text/plain; charset=utf-8"),
                ("Content-Length", str(len(self._body))),
            ],
        )
        return [self._body]
