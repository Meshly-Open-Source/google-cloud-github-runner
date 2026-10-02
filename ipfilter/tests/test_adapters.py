"""Both adapters, and the parity test that stops them drifting apart.

No web framework is imported here. The adapters are plain WSGI/ASGI callables,
so they are exercised with hand-built environs and scopes — which also proves
they do not secretly depend on Flask or Starlette being installed.
"""

import asyncio

import pytest

from ipfilter import asgi as asgi_mod
from ipfilter import wsgi as wsgi_mod
from ipfilter.enforcement import FilterConfig
from ipfilter.policy import Policy
from ipfilter.ranges import RangeResolver
from ipfilter.registry import RouteEntry, RoutePolicyRegistry

RESOLVER = RangeResolver.from_mapping({"permitted": ["203.0.113.0/24"]})
REGISTRY = RoutePolicyRegistry(
    (
        RouteEntry("/webhook", False, Policy(name="webhook", sets=("permitted",))),
        RouteEntry("/preempted", False, Policy.none("preempted", "ephemeral per-VM egress")),
    )
)
CONFIG = FilterConfig(registry=REGISTRY, resolver=RESOLVER, chain_index=-1)

APP_BODY = b"reached the application\n"


# --- WSGI --------------------------------------------------------------------

def wsgi_app(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [APP_BODY]


def wsgi_environ(path="/webhook", header="203.0.113.7", method="POST"):
    environ = {"PATH_INFO": path, "REQUEST_METHOD": method, "REMOTE_ADDR": "198.51.100.1"}
    if header is not None:
        environ["HTTP_X_FORWARDED_FOR"] = header
    return environ


def call_wsgi(middleware, environ):
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = headers

    body = b"".join(middleware(environ, start_response))
    return captured["status"], dict(captured["headers"]), body


def test_wsgi_passes_a_permitted_caller_to_the_application():
    middleware = wsgi_mod.IpPolicyMiddleware(wsgi_app, CONFIG)
    status, _, body = call_wsgi(middleware, wsgi_environ())
    assert status == "200 OK"
    assert body == APP_BODY


def test_wsgi_blocks_an_unpermitted_caller_before_the_application_runs():
    reached = []

    def tripwire(environ, start_response):
        reached.append(True)
        return wsgi_app(environ, start_response)

    middleware = wsgi_mod.IpPolicyMiddleware(tripwire, CONFIG)
    status, _, body = call_wsgi(middleware, wsgi_environ(header="198.51.100.9"))
    assert status == "403 Forbidden"
    assert reached == [], "the application must not be reached; the filter runs before routing"
    assert body != APP_BODY


def test_wsgi_blocks_a_request_with_no_forwarded_header_under_fail_closed():
    middleware = wsgi_mod.IpPolicyMiddleware(wsgi_app, CONFIG)
    status, _, _ = call_wsgi(middleware, wsgi_environ(header=None))
    assert status == "403 Forbidden"


def test_wsgi_distinguishes_an_absent_header_from_an_empty_one():
    middleware = wsgi_mod.IpPolicyMiddleware(wsgi_app, CONFIG)
    records = []
    middleware_logged = wsgi_mod.IpPolicyMiddleware(wsgi_app, CONFIG)
    assert middleware is not middleware_logged  # two instances share no state
    absent = call_wsgi(middleware, wsgi_environ(header=None))
    empty = call_wsgi(middleware, wsgi_environ(header=""))
    assert absent[0] == empty[0] == "403 Forbidden"
    assert records == []


def test_the_block_response_does_not_echo_the_address_chain_or_policy():
    # Telling a caller WHY it was blocked turns the filter into an oracle for
    # probing the policy.
    middleware = wsgi_mod.IpPolicyMiddleware(wsgi_app, CONFIG)
    _, _, body = call_wsgi(middleware, wsgi_environ(header="198.51.100.9"))
    text = body.decode()
    assert "198.51.100.9" not in text
    assert "webhook" not in text
    assert "not-in-set" not in text


def test_the_block_response_sets_an_accurate_content_length():
    middleware = wsgi_mod.IpPolicyMiddleware(wsgi_app, CONFIG)
    _, headers, body = call_wsgi(middleware, wsgi_environ(header="198.51.100.9"))
    assert int(headers["Content-Length"]) == len(body)


def test_wsgi_covers_a_path_the_application_would_have_404ed():
    # Wrapping wsgi_app rather than adding a Flask before_request is what puts
    # the filter outside routing, so unknown paths are filtered too.
    middleware = wsgi_mod.IpPolicyMiddleware(wsgi_app, CONFIG)
    status, _, _ = call_wsgi(middleware, wsgi_environ(path="/not-a-route"))
    assert status == "403 Forbidden"


def test_wsgi_allows_an_exempt_route_with_an_unlistable_address():
    middleware = wsgi_mod.IpPolicyMiddleware(wsgi_app, CONFIG)
    status, _, body = call_wsgi(middleware, wsgi_environ(path="/preempted", header="136.111.117.105"))
    assert status == "200 OK"
    assert body == APP_BODY


def test_wsgi_handles_a_missing_path_info_without_crashing():
    middleware = wsgi_mod.IpPolicyMiddleware(wsgi_app, CONFIG)
    status, _, _ = call_wsgi(middleware, {"REQUEST_METHOD": "GET"})
    assert status == "403 Forbidden"


def test_wsgi_reads_a_configured_non_default_header_name():
    config = FilterConfig(registry=REGISTRY, resolver=RESOLVER, chain_index=-1,
                          forwarded_for_header="X-Envoy-External-Address")
    middleware = wsgi_mod.IpPolicyMiddleware(wsgi_app, config)
    environ = wsgi_environ(header=None)
    environ["HTTP_X_ENVOY_EXTERNAL_ADDRESS"] = "203.0.113.7"
    status, _, _ = call_wsgi(middleware, environ)
    assert status == "200 OK"


# --- route introspection -----------------------------------------------------

class FakeRule:
    def __init__(self, rule):
        self.rule = rule


class FakeUrlMap:
    def __init__(self, rules):
        self._rules = rules

    def iter_rules(self):
        return iter(self._rules)


class FakeFlask:
    def __init__(self, rules):
        self.url_map = FakeUrlMap([FakeRule(rule) for rule in rules])


def test_flask_route_paths_reads_the_live_url_map():
    app = FakeFlask(["/webhook", "/setup/secrets", "/webhook"])
    assert wsgi_mod.flask_route_paths(app) == ["/setup/secrets", "/webhook"]


def test_flask_route_paths_refuses_the_wrong_object_rather_than_returning_empty():
    # Returning [] here would make the coverage assertion vacuous, which is the
    # exact shape of a guard that passes having checked nothing.
    with pytest.raises(TypeError):
        wsgi_mod.flask_route_paths(object())


class FakeRoute:
    def __init__(self, path):
        self.path = path


class FakeStarlette:
    def __init__(self, paths):
        self.routes = [FakeRoute(path) for path in paths]


def test_asgi_route_paths_reads_the_live_router():
    assert asgi_mod.asgi_route_paths(FakeStarlette(["/b", "/a"])) == ["/a", "/b"]


def test_asgi_route_paths_falls_back_to_the_router_attribute():
    class WithRouter:
        def __init__(self):
            self.router = FakeStarlette(["/a"])

    assert asgi_mod.asgi_route_paths(WithRouter()) == ["/a"]


def test_asgi_route_paths_refuses_the_wrong_object():
    with pytest.raises(TypeError):
        asgi_mod.asgi_route_paths(object())


# --- ASGI --------------------------------------------------------------------

def asgi_scope(path="/webhook", header="203.0.113.7", method="POST", scope_type="http"):
    headers = []
    if header is not None:
        headers.append((b"x-forwarded-for", header.encode()))
    return {"type": scope_type, "path": path, "method": method,
            "headers": headers, "client": ("198.51.100.1", 443)}


def call_asgi(middleware, scope):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(middleware(scope, receive, send))
    start = next((m for m in sent if m["type"] == "http.response.start"), None)
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return (start or {}).get("status"), dict((start or {}).get("headers", [])), body


def make_asgi_app(reached):
    async def app(scope, receive, send):
        reached.append(scope["path"])
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": APP_BODY})

    return app


def test_asgi_passes_a_permitted_caller_to_the_application():
    reached = []
    middleware = asgi_mod.IpPolicyMiddleware(make_asgi_app(reached), CONFIG)
    status, _, body = call_asgi(middleware, asgi_scope())
    assert status == 200
    assert body == APP_BODY
    assert reached == ["/webhook"]


def test_asgi_blocks_an_unpermitted_caller_before_the_application_runs():
    reached = []
    middleware = asgi_mod.IpPolicyMiddleware(make_asgi_app(reached), CONFIG)
    status, _, body = call_asgi(middleware, asgi_scope(header="198.51.100.9"))
    assert status == 403
    assert reached == []
    assert body != APP_BODY


def test_asgi_block_response_does_not_echo_the_address():
    middleware = asgi_mod.IpPolicyMiddleware(make_asgi_app([]), CONFIG)
    _, _, body = call_asgi(middleware, asgi_scope(header="198.51.100.9"))
    assert b"198.51.100.9" not in body


def test_asgi_block_response_sets_an_accurate_content_length():
    middleware = asgi_mod.IpPolicyMiddleware(make_asgi_app([]), CONFIG)
    _, headers, body = call_asgi(middleware, asgi_scope(header="198.51.100.9"))
    assert int(headers[b"content-length"]) == len(body)


def test_asgi_passes_lifespan_through_or_the_application_never_starts():
    reached = []

    async def lifespan_app(scope, receive, send):
        reached.append(scope["type"])

    middleware = asgi_mod.IpPolicyMiddleware(lifespan_app, CONFIG)
    asyncio.run(middleware({"type": "lifespan"}, None, None))
    assert reached == ["lifespan"]


def test_asgi_passes_websockets_through_rather_than_half_rejecting_them():
    # A 403 HTTP body is not a valid websocket rejection, and a half-correct
    # rejection is worse than declining to handle the protocol.
    reached = []

    async def ws_app(scope, receive, send):
        reached.append(scope["type"])

    middleware = asgi_mod.IpPolicyMiddleware(ws_app, CONFIG)
    asyncio.run(middleware({"type": "websocket", "path": "/ws"}, None, None))
    assert reached == ["websocket"]


def test_asgi_reads_the_first_value_of_a_repeated_header():
    middleware = asgi_mod.IpPolicyMiddleware(make_asgi_app([]), CONFIG)
    scope = asgi_scope(header=None)
    scope["headers"] = [(b"x-forwarded-for", b"203.0.113.7"), (b"x-forwarded-for", b"198.51.100.9")]
    status, _, _ = call_asgi(middleware, scope)
    assert status == 200


def test_asgi_handles_a_scope_with_no_client():
    middleware = asgi_mod.IpPolicyMiddleware(make_asgi_app([]), CONFIG)
    scope = asgi_scope()
    scope["client"] = None
    status, _, _ = call_asgi(middleware, scope)
    assert status == 200


# --- parity ------------------------------------------------------------------

PARITY_CASES = [
    ("/webhook", "203.0.113.7", True),
    ("/webhook", "198.51.100.9", False),
    ("/webhook", None, False),
    ("/webhook", "", False),
    ("/webhook", "1.1.1.1, 203.0.113.7", True),
    ("/webhook", "203.0.113.7, 1.1.1.1", False),
    ("/webhook", "[2001:db8::1]:443", False),
    ("/webhook", "not-an-ip", False),
    ("/webhook", "203.0.113.0", True),
    ("/webhook", "203.0.113.255", True),
    ("/webhook", "203.0.114.0", False),
    ("/preempted", None, True),
    ("/preempted", "136.111.117.105", True),
    ("/not-a-route", "203.0.113.7", False),
]


@pytest.mark.parametrize("path,header,expect_allowed", PARITY_CASES)
def test_wsgi_and_asgi_reach_the_same_verdict(path, header, expect_allowed):
    """Two adapters that each implement the decision will eventually disagree.

    This is why everything that decides anything lives in enforcement.py and
    the adapters only translate transport. The test is here to notice if that
    ever stops being true -- the disagreement would otherwise be found in
    production, on whichever stack gets less traffic.
    """
    wsgi_status, _, wsgi_body = call_wsgi(
        wsgi_mod.IpPolicyMiddleware(wsgi_app, CONFIG), wsgi_environ(path=path, header=header)
    )
    asgi_status, _, asgi_body = call_asgi(
        asgi_mod.IpPolicyMiddleware(make_asgi_app([]), CONFIG), asgi_scope(path=path, header=header)
    )
    wsgi_allowed = wsgi_status.startswith("200")
    asgi_allowed = asgi_status == 200
    assert wsgi_allowed == asgi_allowed == expect_allowed
    assert (wsgi_body == APP_BODY) == (asgi_body == APP_BODY)
