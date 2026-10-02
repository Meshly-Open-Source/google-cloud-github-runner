"""Derive a client address from an X-Forwarded-For chain, or say why you cannot.

THE INDEX IS CONFIGURATION, NOT PHYSICS
---------------------------------------
There is no universally correct element of an X-Forwarded-For chain. The
trustworthy position depends on how many proxies sit in front of the process
and whether each of them appends or rewrites. Taking element 0 is the classic
error — a caller can send any prefix it likes and a fronting proxy that
APPENDS leaves that forgery to the left of the real value, so element 0 is
attacker-controlled on every append-style platform.

So `chain_index` is a REQUIRED argument. There is no default anywhere in this
module, which is deliberate and slightly inconvenient: a default would be a
number that is correct for exactly one deployment topology and silently wrong
for the rest, and "silently wrong" here means a fail-closed filter denying
every legitimate caller.

MEASURE IT BEFORE YOU ENFORCE WITH IT
-------------------------------------
Pick the index from an observed chain on the deployment in question, not from
a diagram. The failure is asymmetric: too-far-left trusts a forgeable value
(a security hole that tests clean), too-far-right or out-of-range denies
everyone (an outage that looks like silence). `ChainResolution.chain` is
returned in full on every decision, and the deny record logs it, precisely so
a wrong index is visible in the logs instead of being inferred months later.

OUT OF RANGE IS NOT A FALLBACK
------------------------------
When the chain is shorter than the configured index, this returns no address
and the reason `chain-shorter-than-index`. It does NOT quietly fall back to
the peer address or to another element. A fallback would mask exactly the
misconfiguration that matters most, and would make the filter evaluate against
an address the operator never intended to trust.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field

from .ranges import IpAddress

# Reasons. Stable strings: they are logged, alerted on, and asserted in tests.
NO_HEADER = "no-forwarded-for-header"
EMPTY_HEADER = "forwarded-for-header-empty"
CHAIN_TOO_SHORT = "chain-shorter-than-index"
UNPARSEABLE = "forwarded-for-entry-unparseable"


@dataclass(frozen=True)
class ChainResolution:
    """What the chain yielded, and — when it yielded nothing — why.

    `chain` is the raw tokens exactly as received, so a log record shows what
    arrived rather than what we made of it. `index_used` is the configured
    index echoed back; a record carrying both the chain and the index is
    self-diagnosing.
    """

    client_ip: IpAddress | None
    chain: tuple[str, ...] = field(default_factory=tuple)
    index_used: int | None = None
    reason: str | None = None

    @property
    def resolved(self) -> bool:
        return self.client_ip is not None


def normalise_ip_token(token: str) -> str | None:
    """Strip the decorations a forwarded-for entry arrives wearing.

    Three real shapes, and one trap:

      "203.0.113.7"            bare v4
      "203.0.113.7:51234"      v4 with a port
      "[2001:db8::1]:443"      v6 bracketed, with a port
      "2001:db8::1"            bare v6 -- FULL OF COLONS, and splitting it on
                               the last colon mangles it into nonsense that
                               then fails to parse and denies the caller.

    So the port is stripped only where it is unambiguous: inside brackets, or
    when the token contains exactly one colon (which a v6 address never does).
    """
    text = (token or "").strip()
    if not text:
        return None
    if text.startswith("["):
        closing = text.find("]")
        if closing == -1:
            return None
        return text[1:closing] or None
    if text.count(":") == 1:
        return text.split(":", 1)[0] or None
    return text


def parse_ip(token: str) -> IpAddress | None:
    normalised = normalise_ip_token(token)
    if normalised is None:
        return None
    try:
        return ipaddress.ip_address(normalised)
    except ValueError:
        return None


def split_chain(header_value: str | None) -> tuple[str, ...]:
    if not header_value:
        return ()
    return tuple(part.strip() for part in header_value.split(",") if part.strip())


def derive_client_ip(header_value: str | None, *, chain_index: int) -> ChainResolution:
    """Resolve the client address at `chain_index` of the forwarded-for chain.

    `chain_index` is a Python index, so negatives count from the right, which
    is how proxy-append topologies are naturally described ("the last entry our
    own frontend added", "the one before it").
    """
    chain = split_chain(header_value)
    if header_value is None:
        return ChainResolution(None, chain, chain_index, NO_HEADER)
    if not chain:
        return ChainResolution(None, chain, chain_index, EMPTY_HEADER)

    try:
        token = chain[chain_index]
    except IndexError:
        return ChainResolution(None, chain, chain_index, CHAIN_TOO_SHORT)

    addr = parse_ip(token)
    if addr is None:
        return ChainResolution(None, chain, chain_index, UNPARSEABLE)
    return ChainResolution(addr, chain, chain_index, None)
