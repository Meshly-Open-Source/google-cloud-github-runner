"""The decision function, and the table that must cover every route."""

import pytest

from ipfilter.chain import derive_client_ip
from ipfilter.policy import (
    EXEMPT,
    MATCHED,
    NOT_IN_SET,
    SET_EMPTY,
    SET_UNKNOWN,
    Decision,
    Policy,
    PolicyConfigError,
    evaluate,
)
from ipfilter.ranges import RangeResolver
from ipfilter.registry import RouteEntry, RoutePolicyRegistry, UnpolicedRouteError

PERMITTED = ["203.0.113.0/24", "2001:db8:aaaa::/48"]
RESOLVER = RangeResolver.from_mapping({"permitted": PERMITTED, "empty": []})
GUARDED = Policy(name="guarded", sets=("permitted",))


def resolve(header):
    return derive_client_ip(header, chain_index=-1)


# --- the decision function ---------------------------------------------------

def test_an_address_in_the_named_set_is_allowed_and_names_the_matching_set():
    outcome = evaluate(resolve("203.0.113.7"), GUARDED, RESOLVER)
    assert outcome.decision is Decision.ALLOW
    assert outcome.reason == MATCHED
    assert outcome.matched_set == "permitted"


def test_a_v6_address_in_the_named_set_is_allowed_too():
    assert evaluate(resolve("2001:db8:aaaa::1"), GUARDED, RESOLVER).decision is Decision.ALLOW


def test_an_address_outside_every_named_set_is_denied_as_not_in_set():
    outcome = evaluate(resolve("198.51.100.1"), GUARDED, RESOLVER)
    assert outcome.decision is Decision.DENY
    assert outcome.reason == NOT_IN_SET


def test_an_unresolvable_chain_is_unevaluable_and_carries_the_chain_reason():
    # NOT a deny. "I could not work out who this is" and "this is not a
    # permitted caller" have different fixes, and the collapse happens at the
    # enforcement edge, not here.
    outcome = evaluate(resolve(None), GUARDED, RESOLVER)
    assert outcome.decision is Decision.UNEVALUABLE
    assert outcome.reason == "no-forwarded-for-header"


def test_a_policy_naming_a_set_the_consumer_never_supplied_is_unevaluable():
    policy = Policy(name="stale", sets=("set-that-does-not-exist",))
    outcome = evaluate(resolve("203.0.113.7"), policy, RESOLVER)
    assert outcome.decision is Decision.UNEVALUABLE
    assert outcome.reason == SET_UNKNOWN
    assert outcome.matched_set == "set-that-does-not-exist"


def test_a_policy_naming_an_empty_set_is_unevaluable_not_a_deny():
    # "We have no list" must never be reported as "you are not on the list":
    # the first is our outage, the second is their problem.
    policy = Policy(name="empty", sets=("empty",))
    outcome = evaluate(resolve("203.0.113.7"), policy, RESOLVER)
    assert outcome.decision is Decision.UNEVALUABLE
    assert outcome.reason == SET_EMPTY


def test_one_empty_set_poisons_the_policy_even_when_another_would_have_matched():
    # Deliberate: a half-loaded policy must not silently become a narrower
    # policy that happens to pass. Every named set has to be present.
    policy = Policy(name="partial", sets=("permitted", "empty"))
    outcome = evaluate(resolve("203.0.113.7"), policy, RESOLVER)
    assert outcome.decision is Decision.UNEVALUABLE
    assert outcome.reason == SET_EMPTY


def test_an_exempt_policy_allows_without_consulting_any_set():
    policy = Policy.none("ephemeral-egress", "callers egress from per-VM ephemeral addresses")
    outcome = evaluate(resolve(None), policy, RESOLVER)
    assert outcome.decision is Decision.ALLOW
    assert outcome.reason == EXEMPT


def test_multiple_sets_are_tried_until_one_matches():
    resolver = RangeResolver.from_mapping({"a": ["203.0.113.0/24"], "b": ["198.51.100.0/24"]})
    policy = Policy(name="either", sets=("a", "b"))
    assert evaluate(resolve("198.51.100.5"), policy, resolver).matched_set == "b"


# --- policy construction -----------------------------------------------------

def test_a_policy_with_no_sets_and_no_exemption_is_rejected_at_construction():
    # It could never allow anything, so it is a typo, not a policy.
    with pytest.raises(PolicyConfigError):
        Policy(name="useless")


def test_an_exempt_policy_without_a_justification_is_rejected():
    # An exemption with no stated reason is indistinguishable from a route
    # somebody forgot, which is what the table exists to make impossible.
    with pytest.raises(PolicyConfigError) as excinfo:
        Policy(name="open", exempt=True, justification="   ")
    assert "justification" in str(excinfo.value)


def test_a_policy_that_is_both_exempt_and_names_sets_is_rejected():
    with pytest.raises(PolicyConfigError):
        Policy(name="confused", sets=("permitted",), exempt=True, justification="why")


def test_an_unnamed_policy_is_rejected_because_the_name_appears_in_every_record():
    with pytest.raises(PolicyConfigError):
        Policy(name="", sets=("permitted",))


# --- the route table ---------------------------------------------------------

TABLE = (
    RouteEntry("/webhook", False, GUARDED),
    RouteEntry("/setup/", True, Policy(name="setup", sets=("permitted",))),
    RouteEntry("/setup/health", False, Policy.none("setup-health", "unauthenticated liveness probe")),
)


def test_an_exact_entry_wins_over_a_prefix_entry_covering_the_same_path():
    registry = RoutePolicyRegistry(TABLE)
    assert registry.policy_for("/setup/health").name == "setup-health"
    assert registry.policy_for("/setup/secrets").name == "setup"


def test_a_prefix_entry_covers_paths_beneath_it():
    registry = RoutePolicyRegistry(TABLE)
    assert registry.policy_for("/setup/deep/nested/thing").name == "setup"


def test_a_prefix_cannot_match_a_sibling_whose_name_merely_starts_the_same():
    # '/setupfoo' must not be covered by a policy written for '/setup/'.
    registry = RoutePolicyRegistry(TABLE)
    assert registry.policy_for("/setupfoo") is None


def test_the_longest_matching_prefix_wins_deterministically():
    registry = RoutePolicyRegistry(
        (
            RouteEntry("/a/", True, Policy(name="outer", sets=("permitted",))),
            RouteEntry("/a/b/", True, Policy(name="inner", sets=("permitted",))),
        )
    )
    assert registry.policy_for("/a/b/c").name == "inner"
    assert registry.policy_for("/a/x").name == "outer"


def test_a_prefix_entry_not_ending_in_a_slash_is_rejected():
    with pytest.raises(PolicyConfigError):
        RouteEntry("/setup", True, GUARDED)


def test_a_route_not_starting_with_a_slash_is_rejected():
    with pytest.raises(PolicyConfigError):
        RouteEntry("setup/", True, GUARDED)


def test_a_duplicated_route_is_rejected_rather_than_resolved_by_ordering():
    with pytest.raises(PolicyConfigError) as excinfo:
        RoutePolicyRegistry((RouteEntry("/webhook", False, GUARDED), RouteEntry("/webhook", False, GUARDED)))
    assert "twice" in str(excinfo.value)


def test_an_empty_table_is_rejected_because_it_makes_coverage_vacuous():
    with pytest.raises(PolicyConfigError):
        RoutePolicyRegistry(())


def test_an_uncovered_route_fails_the_startup_assertion():
    # THE central guarantee. A table that covers what it knows about and lets
    # the rest through is an inclusion list, and it fails open on exactly the
    # route added next week by someone who never read it.
    registry = RoutePolicyRegistry(TABLE)
    with pytest.raises(UnpolicedRouteError) as excinfo:
        registry.assert_routes_covered(["/webhook", "/runner/preempted"])
    assert "/runner/preempted" in str(excinfo.value)
    assert "/webhook" not in str(excinfo.value), "only the uncovered route should be reported"


def test_a_fully_covered_route_set_passes_the_startup_assertion():
    registry = RoutePolicyRegistry(TABLE)
    registry.assert_routes_covered(["/webhook", "/setup/health", "/setup/secrets"])


def test_asserting_against_zero_routes_is_a_failure_not_a_pass():
    # What introspecting the wrong object returns. "Every one of zero routes is
    # covered" is the vacuous pass the whole module is arranged to avoid.
    registry = RoutePolicyRegistry(TABLE)
    with pytest.raises(UnpolicedRouteError) as excinfo:
        registry.assert_routes_covered([])
    assert "ZERO routes" in str(excinfo.value)


def test_uncovered_reports_every_missing_route_not_just_the_first():
    registry = RoutePolicyRegistry(TABLE)
    assert registry.uncovered(["/a", "/b", "/webhook"]) == ("/a", "/b")


def test_an_explicit_none_policy_counts_as_coverage():
    # This is how a route that genuinely takes no address check is declared,
    # and the difference from an omission is that it carries a reason.
    registry = RoutePolicyRegistry(
        (RouteEntry("/runner/preempted", False, Policy.none("preempted", "ephemeral per-VM egress; OIDC instead")),)
    )
    registry.assert_routes_covered(["/runner/preempted"])
    assert registry.policy_for("/runner/preempted").justification
