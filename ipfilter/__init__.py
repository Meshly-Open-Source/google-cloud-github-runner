"""Framework-agnostic IP-policy filtering: a policy core plus WSGI/ASGI adapters.

WHY THIS PACKAGE IS VENDOR-NEUTRAL
----------------------------------
This directory is an ADDITION to a fork of Cyclenerd/google-cloud-github-runner
(see ../README.md). Everything else the fork adds is named for its owner; this
is not, deliberately. It is intended to be offered upstream, and the shape of
the offer should be "add exactly this directory" — no renames, no imports to
unpick, no references to the organisation that wrote it. So:

  * nothing here imports from the application it currently protects,
  * nothing here imports a web framework,
  * and there are NO CIDRs in this package at all.

That last one is the load-bearing rule. A library that ships a default range
set makes one consumer's upstream into a silent default for every future
consumer, which is precisely the invisible-default failure that a fail-closed
control cannot survive. A consumer supplies its own named sets. A policy that
names a set the consumer did not supply is UNEVALUABLE, and under fail-closed
that denies. "I could not tell" never reads as "allow".

LAYOUT
------
  ranges.py       CIDR text -> compiled (network_int, netmask_int) tables,
                  separate per address family.
  chain.py        X-Forwarded-For -> a client address, or a stated reason why
                  not.
  policy.py       Policy objects and the pure decision function.
  registry.py     The route -> policy table, validated at import, plus the
                  startup assertion that every route a consumer actually
                  serves has an entry.
  enforcement.py  The single decision path both adapters call. Transport
                  translation is the ONLY thing the adapters are allowed to
                  do; the two must never be able to disagree.
  events.py       The structured record every deny emits.
  wsgi.py         WSGI adapter (this fork's app is Flask).
  asgi.py         ASGI adapter (for a Starlette/FastAPI consumer).

THREE DECISIONS, NOT TWO
------------------------
The core answers ALLOW, DENY, or UNEVALUABLE. Collapsing the third into DENY
inside the core would throw away the only thing that distinguishes "this
caller is not on the list" from "I do not have a list" — and those two have
completely different fixes. The collapse happens at the enforcement edge,
where it is a configured fail mode, and the record says which one it was.
"""

from .chain import ChainResolution, derive_client_ip, normalise_ip_token
from .enforcement import Outcome, enforce
from .events import deny_record
from .policy import Decision, Evaluation, Policy, evaluate
from .ranges import CompiledRanges, RangeResolver, compile_ranges
from .registry import RouteEntry, RoutePolicyRegistry, UnpolicedRouteError

__all__ = [
    "ChainResolution",
    "CompiledRanges",
    "Decision",
    "Evaluation",
    "Outcome",
    "Policy",
    "RangeResolver",
    "RouteEntry",
    "RoutePolicyRegistry",
    "UnpolicedRouteError",
    "compile_ranges",
    "deny_record",
    "derive_client_ip",
    "enforce",
    "evaluate",
    "normalise_ip_token",
]
