"""The route -> policy table: a Python module as data, validated at import.

WHY A TABLE IN CODE RATHER THAN A CONFIG FILE
---------------------------------------------
Because the policy is reviewed like code and the DATA is not the policy. The
split matters:

  policy  which routes, which named sets, fail mode, log_only -- lives here,
          in a table, in the diff, validated at import.
  data    the actual prefixes -- lives wherever the operator refreshes them
          (a published object, an environment override, a baked constant) and
          reaches this package as named sets through a RangeResolver.

Putting prefixes in the table would collapse that split and make a range
refresh a code deploy. Putting the table in a config file would mean a
malformed policy is discovered at first evaluation rather than at start.

AN UNLISTED ROUTE IS A STARTUP FAILURE
--------------------------------------
This is the one rule to not soften. A table that covers the routes it knows
about and lets the rest through is an INCLUSION LIST, and an inclusion list
fails open on exactly the thing it was built to catch: the route added next
week by someone who never read this file. Every route gets an entry, including
the ones that take no check -- those get `Policy.none(...)` with a written
reason.

`assert_routes_covered` is how that is enforced, and note WHAT it is given:
the route set read out of the running application object at startup (Flask's
url_map, Starlette's app.routes), not a grep over source. A grep cannot see a
route registered by a loop, a blueprint registered conditionally, or a path
assembled from a prefix variable -- and those are the routes most likely to be
missed by a human too. Assert on the resolved artifact.
"""

from __future__ import annotations

from dataclasses import dataclass

from .policy import Policy, PolicyConfigError


class UnpolicedRouteError(RuntimeError):
    """A route the application serves has no policy. Raised at startup, fatal."""


@dataclass(frozen=True)
class RouteEntry:
    """One row. `is_prefix` matches the path and everything beneath it.

    Prefix matching exists because blueprint-mounted trees (`/setup/...`) are
    naturally one policy, and enumerating their members would rot. An exact
    entry always wins over a prefix entry, so a single member of a tree can be
    given a different policy without restructuring the table.
    """

    path: str
    is_prefix: bool
    policy: Policy

    def __post_init__(self) -> None:
        if not self.path.startswith("/"):
            raise PolicyConfigError(f"route {self.path!r} must start with '/'")
        if self.is_prefix and not self.path.endswith("/"):
            raise PolicyConfigError(
                f"prefix route {self.path!r} must end with '/' so that '/setupfoo' cannot be "
                "matched by a policy written for '/setup/'."
            )


class RoutePolicyRegistry:
    """Precomputed lookup over the table. Built once, immutable thereafter."""

    def __init__(self, entries: tuple[RouteEntry, ...]):
        if not entries:
            raise PolicyConfigError(
                "the route policy table is empty. An empty table makes every coverage "
                "assertion vacuous, which prints clean and checks nothing."
            )
        exact: dict[str, Policy] = {}
        prefixes: list[tuple[str, Policy]] = []
        seen: set[tuple[str, bool]] = set()
        for entry in entries:
            key = (entry.path, entry.is_prefix)
            if key in seen:
                raise PolicyConfigError(
                    f"route {entry.path!r} appears twice in the table. Two policies for one "
                    "route means the effective one depends on ordering nobody reviewed."
                )
            seen.add(key)
            if entry.is_prefix:
                prefixes.append((entry.path, entry.policy))
            else:
                exact[entry.path] = entry.policy
        self._exact = exact
        # Longest prefix first, so the more specific mount wins deterministically.
        self._prefixes = tuple(sorted(prefixes, key=lambda item: len(item[0]), reverse=True))
        self._entries = entries

    @property
    def entries(self) -> tuple[RouteEntry, ...]:
        return self._entries

    def policy_for(self, path: str) -> Policy | None:
        """The policy governing `path`, or None if the table does not cover it.

        None is not "allowed". The caller treats an uncovered path as a denial
        with reason `route-has-no-policy`; the startup assertion is what makes
        that case mean "someone probed a path we do not serve" rather than
        "a real route is unprotected".
        """
        exact = self._exact.get(path)
        if exact is not None:
            return exact
        for prefix, policy in self._prefixes:
            if path.startswith(prefix):
                return policy
        return None

    def uncovered(self, route_paths: list[str]) -> tuple[str, ...]:
        return tuple(sorted({path for path in route_paths if self.policy_for(path) is None}))

    def assert_routes_covered(self, route_paths: list[str]) -> None:
        """Fail start-up if the application serves a route the table omits.

        An empty `route_paths` is itself a finding: it is what an introspection
        helper returns when it has been pointed at the wrong object, and
        "every one of zero routes is covered" is the vacuous pass this whole
        module is arranged to avoid.
        """
        if not route_paths:
            raise UnpolicedRouteError(
                "coverage was asserted against ZERO routes. That is not a pass -- it is what "
                "introspecting the wrong object returns. Pass the route set read from the "
                "running application."
            )
        missing = self.uncovered(route_paths)
        if missing:
            raise UnpolicedRouteError(
                "these routes have no entry in the IP policy table: "
                + ", ".join(missing)
                + ".\nEvery route needs an explicit decision, including 'no address check' -- "
                "use Policy.none(name, justification) and say why in the justification. "
                "A route allowed by omission is the inclusion-list failure this assertion exists "
                "to prevent."
            )
