"""Policy objects and the pure decision function.

A Policy names SETS, never prefixes. The indirection is what lets a published
range list be refreshed, or a second consumer be added, without a CIDR being
pasted into a second place.

`Policy.none(...)` is the explicit "this route takes no address check" policy,
and it REQUIRES a justification string. That requirement is the whole reason
it exists as a first-class policy rather than as an omission from the table:
an unlisted route and a deliberately-exempt route look identical in a table
that permits omissions, and only one of them has been thought about. Compare
the route that has to stay open because its callers egress from per-VM
ephemeral addresses and is authenticated some other way -- that is a decision
with a reason, and the reason should be reviewable in the diff.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .chain import ChainResolution
from .ranges import RangeResolver

# Reasons, stable because they are logged and asserted.
NOT_IN_SET = "not-in-set"
SET_UNKNOWN = "named-set-not-supplied"
SET_EMPTY = "named-set-is-empty"
NO_POLICY = "route-has-no-policy"
EXEMPT = "policy-exempt"
MATCHED = "matched"


class Decision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    UNEVALUABLE = "unevaluable"


class PolicyConfigError(ValueError):
    """A policy could not be constructed. Raised at import, never per request."""


@dataclass(frozen=True)
class Policy:
    """Which named sets may reach a route, and how failure is handled.

    log_only: evaluate and record, but never block. The staged-rollout switch.
              A shared control is a shared blast radius, so the first deploy of
              any policy runs here and the records are what promote it.
    """

    name: str
    sets: tuple[str, ...] = ()
    exempt: bool = False
    justification: str = ""
    log_only: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise PolicyConfigError("a policy must be named; the name appears in every record")
        if self.exempt:
            if self.sets:
                raise PolicyConfigError(
                    f"policy {self.name!r} is exempt AND names sets {self.sets!r}. "
                    "One of those is a mistake and guessing which would be worse than failing."
                )
            if not self.justification.strip():
                raise PolicyConfigError(
                    f"policy {self.name!r} is exempt from address checking but carries no "
                    "justification. An exemption without a stated reason is indistinguishable "
                    "from a route somebody forgot, which is the thing this table exists to prevent."
                )
        elif not self.sets:
            raise PolicyConfigError(
                f"policy {self.name!r} names no sets and is not exempt, so it can never allow "
                "anything. If the intent is 'no address check', use Policy.none() and say why."
            )

    @classmethod
    def none(cls, name: str, justification: str, *, log_only: bool = False) -> "Policy":
        return cls(name=name, sets=(), exempt=True, justification=justification, log_only=log_only)


@dataclass(frozen=True)
class Evaluation:
    decision: Decision
    reason: str
    policy: str
    matched_set: str | None = None


def evaluate(resolution: ChainResolution, policy: Policy, resolver: RangeResolver) -> Evaluation:
    """Decide, purely. No I/O, no logging, no transport, no clock.

    Three outcomes, and the third is load-bearing. UNEVALUABLE means the
    question could not be answered -- the chain did not yield an address, or a
    named set was not supplied, or it was supplied empty. Those have a
    different fix from "this caller is not on the list", and the enforcement
    edge is where the fail mode collapses them, with the reason preserved.
    """
    if policy.exempt:
        return Evaluation(Decision.ALLOW, EXEMPT, policy.name)

    if not resolution.resolved:
        return Evaluation(Decision.UNEVALUABLE, resolution.reason or "client-ip-unresolved", policy.name)

    for set_name in policy.sets:
        compiled = resolver.get(set_name)
        if compiled is None:
            return Evaluation(Decision.UNEVALUABLE, SET_UNKNOWN, policy.name, set_name)
        if compiled.is_empty:
            return Evaluation(Decision.UNEVALUABLE, SET_EMPTY, policy.name, set_name)

    assert resolution.client_ip is not None  # narrowed by `resolution.resolved`
    for set_name in policy.sets:
        compiled = resolver.get(set_name)
        assert compiled is not None  # established by the loop above
        if compiled.contains(resolution.client_ip):
            return Evaluation(Decision.ALLOW, MATCHED, policy.name, set_name)

    return Evaluation(Decision.DENY, NOT_IN_SET, policy.name)
