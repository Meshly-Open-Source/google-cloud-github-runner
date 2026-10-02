"""The single decision path. Both adapters call this and do nothing else.

WHY THIS MODULE EXISTS SEPARATELY FROM THE ADAPTERS
---------------------------------------------------
Because two adapters that each implement "evaluate, decide the fail mode, log,
and choose a status" will eventually disagree, and the disagreement will be
discovered in production on whichever stack gets less traffic. Everything that
is a DECISION lives here. The adapters are allowed exactly one job: pull the
path, method, header and peer out of their transport, and turn an Outcome into
a response. If an adapter ever grows an `if`, that `if` belongs in this file.

WHERE THE THIRD DECISION COLLAPSES
----------------------------------
The core returns ALLOW / DENY / UNEVALUABLE. Here, and only here,
UNEVALUABLE collapses according to `fail_closed`:

  fail_closed=True   unevaluable -> blocked. The default, and the right one
                     for a perimeter control: "I could not tell" must not read
                     as "allow".
  fail_closed=False  unevaluable -> allowed, recorded. For commissioning a
                     policy on a route whose chain shape is not yet measured.

The reason survives the collapse into the record, so the two causes of a block
never become one number.

ORDERING, AND THE HAZARD IT CREATES
-----------------------------------
A middleware installed at the transport level runs BEFORE the application's
own routing, and therefore before any in-handler authentication the
application performs -- a signature check inside a view function, for example.
That ordering is what makes this defence in depth rather than a replacement.

It is also the hazard, and it should be stated where someone enabling this
will read it: a bug here blocks a legitimate caller BEFORE the control it is
backstopping gets a chance to validate them, which makes this layer strictly
more load-bearing than the one it supports. That asymmetry is why `log_only`
exists, why it is the right setting for a first deploy, and why an alarm for
"no traffic accepted recently" belongs in place before enforcement rather than
after.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .chain import derive_client_ip
from .events import deny_record, emit
from .policy import NO_POLICY, Decision, evaluate
from .ranges import RangeResolver
from .registry import RoutePolicyRegistry

DEFAULT_STATUS = 403
DEFAULT_BODY = b"forbidden\n"


@dataclass(frozen=True)
class FilterConfig:
    """Everything the decision needs, assembled once at startup.

    `chain_index` has no default here either -- see chain.py. A consumer that
    has not measured its proxy chain should not be able to construct this
    object by accident.
    """

    registry: RoutePolicyRegistry
    resolver: RangeResolver
    chain_index: int
    forwarded_for_header: str = "X-Forwarded-For"
    fail_closed: bool = True
    log_only: bool = False
    status: int = DEFAULT_STATUS


@dataclass(frozen=True)
class Outcome:
    """Allow or block, plus the record that was emitted.

    `record` is returned rather than only logged so that a test can assert on
    the record's content, and so a consumer can additionally route it to a
    metric. A control whose evidence is only reachable by scraping its own log
    output is a control that is hard to test, and an untested fail-closed
    filter is an outage waiting for a deploy.
    """

    allowed: bool
    decision: Decision
    reason: str
    status: int
    record: dict


def enforce(
    config: FilterConfig,
    *,
    path: str,
    method: str,
    header_value: str | None,
    peer: str | None = None,
    logger: logging.Logger | None = None,
) -> Outcome:
    policy = config.registry.policy_for(path)
    resolution = derive_client_ip(header_value, chain_index=config.chain_index)

    if policy is None:
        # The startup coverage assertion means every route the application
        # SERVES has a policy, so reaching here is a request for a path that
        # is not a route: a probe, or a typo. Blocked, under the same fail mode
        # as everything else, and recorded with its own reason so it never
        # becomes indistinguishable from a real policy denial.
        decision, reason, matched_set, policy_name = Decision.UNEVALUABLE, NO_POLICY, None, "<none>"
    else:
        evaluation = evaluate(resolution, policy, config.resolver)
        decision, reason, matched_set, policy_name = (
            evaluation.decision,
            evaluation.reason,
            evaluation.matched_set,
            evaluation.policy,
        )

    if decision is Decision.ALLOW:
        would_block = False
    elif decision is Decision.DENY:
        would_block = True
    else:
        would_block = config.fail_closed

    policy_log_only = policy.log_only if policy is not None else False
    shadow = config.log_only or policy_log_only
    enforced = would_block and not shadow

    record = deny_record(
        route=path,
        method=method,
        policy=policy_name,
        decision=decision.value,
        reason=reason,
        client_ip=str(resolution.client_ip) if resolution.client_ip is not None else None,
        chain=resolution.chain,
        chain_index=resolution.index_used,
        enforced=enforced,
        matched_set=matched_set,
        peer=peer,
    )
    # Always emitted, with the LEVEL carrying the distinction: an allow goes to
    # DEBUG and so costs nothing at a normal log level, while remaining
    # available when a policy is being commissioned. Deciding here whether a
    # record is "worth" emitting would put a second, invisible filter in front
    # of the evidence, and the evidence is the point.
    emit(record, logger=logger)

    return Outcome(
        allowed=not enforced,
        decision=decision,
        reason=reason,
        status=config.status,
        record=record,
    )
