"""Compile CIDR text into integer mask tables, and match addresses against them.

WHY NOT A TRIE, AND WHY NOT A DEPENDENCY
----------------------------------------
A patricia trie answers "which of these overlapping prefixes WINS" — a
routing-table question. This module answers "is this address in this set",
which is membership. The longest-prefix machinery buys nothing for membership,
so a C-extension dependency (pytricia and friends) would add a supply-chain
entry, a build step and an extension module in exchange for nothing.

What it costs instead: two integer operations per prefix, short-circuiting on
the first hit. The real sets are small — GitHub's `hooks` set is six prefixes.
If a policy ever names a set above roughly a thousand prefixes, swap the linear
scan for a sorted-interval bisect behind this same interface; that is a
one-function change and the tests do not move.

TWO FAMILIES, TWO TABLES, AND WHY THAT IS NOT A STYLE CHOICE
------------------------------------------------------------
`socket.inet_pton(AF_INET6, "1.2.3.4")` RAISES. The natural-looking
implementation — one parse path, v6-shaped, with a try/except around it — puts
every IPv4 caller into the except branch and returns "no match". Under
fail-closed that silently denies every v4 client, which is both a total outage
and invisible, because a deny looks like a quiet day. So: `ipaddress` at load
time, which parses both families uniformly and validates the configuration
while it is at it, and separate compiled tables keyed by version at match time.

LOAD TIME IS WHERE CONFIGURATION ERRORS BELONG
----------------------------------------------
`compile_ranges` is strict: a malformed prefix, or one with host bits set
(`192.30.252.1/22`), raises. A silently-corrected netmask is a policy that
does not mean what its author wrote. `collapse_addresses` then merges
overlapping and adjacent prefixes, which shrinks the scan and makes the
compiled form canonical for free.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Iterable, Mapping

IpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

# (network_int, netmask_int) — matching is `(addr & netmask) == network`.
MaskTable = tuple[tuple[int, int], ...]


class RangeConfigError(ValueError):
    """A named set could not be compiled. Raised at load, never at request time."""


@dataclass(frozen=True)
class CompiledRanges:
    """One named set of prefixes, compiled for matching.

    `is_empty` exists so a caller can tell "the set is present and this address
    is not in it" from "the set carries no prefixes". The second is not a deny,
    it is an unevaluable policy, and conflating them is how a misconfigured
    consumer gets reported as a hostile caller.
    """

    name: str
    v4: MaskTable
    v6: MaskTable
    source: str

    @property
    def is_empty(self) -> bool:
        return not self.v4 and not self.v6

    def __len__(self) -> int:
        return len(self.v4) + len(self.v6)

    def contains(self, addr: IpAddress) -> bool:
        table = self.v4 if addr.version == 4 else self.v6
        value = int(addr)
        for network, netmask in table:
            if (value & netmask) == network:
                return True
        return False


def compile_ranges(name: str, cidrs: Iterable[str], *, source: str = "inline") -> CompiledRanges:
    """Compile prefix strings into a matchable set.

    `source` is carried only so a deny record can say WHERE the set came from
    (a baked constant, a GCS object, an environment override). It is metadata
    for diagnosis and never affects a decision.
    """
    v4_nets: list[ipaddress.IPv4Network] = []
    v6_nets: list[ipaddress.IPv6Network] = []

    for raw in cidrs:
        text = (raw or "").strip()
        if not text:
            continue
        try:
            network = ipaddress.ip_network(text, strict=True)
        except ValueError as exc:
            raise RangeConfigError(
                f"set {name!r} (from {source}): {text!r} is not a valid CIDR prefix: {exc}. "
                "Host bits set in a prefix is the usual cause; a silently-corrected netmask "
                "would be a policy that does not mean what its author wrote."
            ) from exc
        if isinstance(network, ipaddress.IPv4Network):
            v4_nets.append(network)
        else:
            v6_nets.append(network)

    return CompiledRanges(
        name=name,
        v4=_to_table(ipaddress.collapse_addresses(v4_nets)),
        v6=_to_table(ipaddress.collapse_addresses(v6_nets)),
        source=source,
    )


def _to_table(networks: Iterable[ipaddress.IPv4Network | ipaddress.IPv6Network]) -> MaskTable:
    return tuple(sorted((int(net.network_address), int(net.netmask)) for net in networks))


class RangeResolver:
    """Resolves a set NAME to a compiled set.

    Policies name sets; they never carry prefixes. That indirection is the
    whole point: adding a consumer, or refreshing a published range list, never
    means pasting CIDRs into a second place.

    An unknown name is not an error here and not a deny here — it resolves to
    None, and the decision function turns that into UNEVALUABLE with a reason.
    Raising would make a single stale policy name a crash loop; denying
    silently would make it an outage nobody can see. A named, logged
    unevaluable is the only one of the three that is diagnosable.
    """

    def __init__(self, sets: Mapping[str, CompiledRanges]):
        self._sets = dict(sets)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Iterable[str]], *, source: str = "inline") -> "RangeResolver":
        return cls({name: compile_ranges(name, cidrs, source=source) for name, cidrs in raw.items()})

    def get(self, name: str) -> CompiledRanges | None:
        return self._sets.get(name)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._sets))

    def describe(self) -> dict[str, dict[str, object]]:
        """Inspection surface for a startup log line or a capability proof."""
        return {
            name: {"prefixes": len(rng), "v4": len(rng.v4), "v6": len(rng.v6), "source": rng.source}
            for name, rng in sorted(self._sets.items())
        }
