"""The structured record a decision emits.

WHY DENY LOGGING IS A CORE REQUIREMENT AND NOT AN ADAPTER DETAIL
----------------------------------------------------------------
A fail-closed filter fails QUIETLY. When it starts rejecting everything, the
symptom is that no requests arrive -- which is indistinguishable from a quiet
afternoon. There is no error, no exception, no failed request to find, because
from inside the process nothing happened. The record is therefore not
telemetry decoration; it is the only evidence that the control works at all,
and the only way a wrong chain index is diagnosable rather than inferred.

Hence two non-negotiables:

  THE CHAIN, NOT JUST THE VERDICT. The full forwarded-for chain and the index
  used go in every record. A misconfigured index is invisible from the verdict
  alone -- every record just says "denied" -- and visible at a glance from the
  chain.

  THE REASON, DISCRIMINATED. `not-in-set` means a caller is not permitted.
  `named-set-not-supplied` means we have no list. Those have different fixes
  and opposite implications, and a single "denied" counter conflates them.

SHADOW MODE IS A DISTINCT RECORD
--------------------------------
`enforced=False` says the request was allowed through while the policy would
have blocked it. Promoting a policy out of log_only is a decision made from
these records, so a shadow deny must never be mistakable for a real one in a
count.

ONE LINE OF JSON, WHICH IS ALSO THE INJECTION ANSWER
----------------------------------------------------
Every value here is attacker-influenced -- the chain is a request header and
the path is a request target. They are serialised with json.dumps, which
escapes newlines and quotes, so a caller cannot forge a second log line or
break out of the record. Do not reformat this into an f-string.
"""

from __future__ import annotations

import json
import logging
from typing import Any

LOGGER_NAME = "ipfilter"
EVENT = "ip_policy_decision"

# Chains are attacker-supplied and unbounded. Truncate for the record, but say
# that it was truncated and keep the real length -- a silently-shortened chain
# would make the index arithmetic in the record unverifiable.
MAX_CHAIN_ENTRIES = 16


def deny_record(
    *,
    route: str,
    method: str,
    policy: str,
    decision: str,
    reason: str,
    client_ip: str | None,
    chain: tuple[str, ...],
    chain_index: int | None,
    enforced: bool,
    matched_set: str | None = None,
    peer: str | None = None,
) -> dict[str, Any]:
    """Build the record. Pure; the caller decides where it goes."""
    record: dict[str, Any] = {
        "event": EVENT,
        "decision": decision,
        "reason": reason,
        "policy": policy,
        "route": route,
        "method": method,
        "client_ip": client_ip,
        "chain": list(chain[:MAX_CHAIN_ENTRIES]),
        "chain_length": len(chain),
        "chain_index": chain_index,
        "enforced": enforced,
    }
    if len(chain) > MAX_CHAIN_ENTRIES:
        record["chain_truncated"] = True
    if matched_set is not None:
        record["matched_set"] = matched_set
    if peer is not None:
        # The transport peer, which on a proxied platform is the frontend and
        # not the client. Recorded because "the peer is who we expected" is the
        # first thing to check when the chain looks wrong.
        record["peer"] = peer
    return record


def emit(record: dict[str, Any], *, logger: logging.Logger | None = None) -> None:
    """Log one record as a single JSON line.

    A real deny logs at WARNING; a shadow deny at INFO, so that turning on a
    policy does not light up an alert channel before it is enforcing. An allow
    is logged at DEBUG, which keeps the happy path off the bill while leaving
    it available when a filter is being commissioned.
    """
    log = logger or logging.getLogger(LOGGER_NAME)
    if record.get("decision") == "allow":
        level = logging.DEBUG
    elif record.get("enforced"):
        level = logging.WARNING
    else:
        level = logging.INFO
    log.log(level, json.dumps(record, sort_keys=True, default=str))
