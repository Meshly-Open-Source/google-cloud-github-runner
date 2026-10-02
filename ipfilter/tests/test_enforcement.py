"""The fail mode, the shadow mode, and the record every decision emits."""

import json
import logging

import pytest

from ipfilter.enforcement import FilterConfig, enforce
from ipfilter.policy import NO_POLICY, Decision, Policy
from ipfilter.ranges import RangeResolver
from ipfilter.registry import RouteEntry, RoutePolicyRegistry

RESOLVER = RangeResolver.from_mapping({"permitted": ["203.0.113.0/24"], "empty": []})
TABLE = (
    RouteEntry("/webhook", False, Policy(name="webhook", sets=("permitted",))),
    RouteEntry("/stale", False, Policy(name="stale", sets=("set-never-supplied",))),
    RouteEntry("/empty", False, Policy(name="empty-set", sets=("empty",))),
    RouteEntry("/preempted", False, Policy.none("preempted", "ephemeral per-VM egress; OIDC instead")),
    RouteEntry("/shadow", False, Policy(name="shadow", sets=("permitted",), log_only=True)),
)
REGISTRY = RoutePolicyRegistry(TABLE)


def config(**overrides):
    base = dict(registry=REGISTRY, resolver=RESOLVER, chain_index=-1)
    base.update(overrides)
    return FilterConfig(**base)


def run(cfg, path="/webhook", header="203.0.113.7", method="POST", peer="198.51.100.1"):
    return enforce(cfg, path=path, method=method, header_value=header, peer=peer)


# --- the happy path ----------------------------------------------------------

def test_a_permitted_caller_is_allowed():
    outcome = run(config())
    assert outcome.allowed is True
    assert outcome.decision is Decision.ALLOW


def test_an_unpermitted_caller_is_blocked_with_the_configured_status():
    outcome = run(config(), header="198.51.100.9")
    assert outcome.allowed is False
    assert outcome.decision is Decision.DENY
    assert outcome.status == 403


def test_the_status_is_configurable():
    assert run(config(status=404), header="198.51.100.9").status == 404


# --- the fail mode -----------------------------------------------------------

def test_unevaluable_is_blocked_when_fail_closed():
    # "I could not tell" must not read as "allow".
    outcome = run(config(fail_closed=True), header=None)
    assert outcome.decision is Decision.UNEVALUABLE
    assert outcome.allowed is False


def test_unevaluable_is_allowed_but_recorded_when_fail_open():
    outcome = run(config(fail_closed=False), header=None)
    assert outcome.decision is Decision.UNEVALUABLE
    assert outcome.allowed is True
    assert outcome.record["reason"] == "no-forwarded-for-header"


def test_fail_closed_is_the_default():
    assert FilterConfig(registry=REGISTRY, resolver=RESOLVER, chain_index=-1).fail_closed is True


def test_a_real_deny_is_not_affected_by_the_fail_mode():
    # fail_closed governs UNEVALUABLE only. A caller that is genuinely not in
    # the set is blocked either way, otherwise fail_open would be an off switch
    # for the whole control rather than a commissioning aid.
    outcome = run(config(fail_closed=False), header="198.51.100.9")
    assert outcome.decision is Decision.DENY
    assert outcome.allowed is False


def test_a_missing_named_set_blocks_under_fail_closed_with_its_own_reason():
    outcome = run(config(), path="/stale")
    assert outcome.allowed is False
    assert outcome.record["reason"] == "named-set-not-supplied"


def test_an_empty_named_set_blocks_under_fail_closed_with_its_own_reason():
    outcome = run(config(), path="/empty")
    assert outcome.allowed is False
    assert outcome.record["reason"] == "named-set-is-empty"


def test_the_two_block_reasons_are_distinguishable_in_the_record():
    not_in_set = run(config(), header="198.51.100.9").record["reason"]
    no_list = run(config(), path="/stale").record["reason"]
    assert not_in_set != no_list, "a single 'denied' reason conflates their opposite fixes"


# --- shadow mode -------------------------------------------------------------

def test_global_log_only_lets_a_would_be_block_through_and_marks_it_unenforced():
    outcome = run(config(log_only=True), header="198.51.100.9")
    assert outcome.allowed is True
    assert outcome.decision is Decision.DENY
    assert outcome.record["enforced"] is False


def test_a_per_policy_log_only_shadows_just_that_route():
    cfg = config()
    shadowed = run(cfg, path="/shadow", header="198.51.100.9")
    enforced = run(cfg, path="/webhook", header="198.51.100.9")
    assert shadowed.allowed is True
    assert enforced.allowed is False


def test_an_enforced_block_is_marked_enforced():
    assert run(config(), header="198.51.100.9").record["enforced"] is True


def test_an_allow_is_never_marked_enforced():
    assert run(config()).record["enforced"] is False


# --- a path with no policy ---------------------------------------------------

def test_a_path_with_no_policy_is_blocked_under_fail_closed():
    outcome = run(config(), path="/definitely-not-a-route")
    assert outcome.allowed is False
    assert outcome.record["reason"] == NO_POLICY


def test_a_path_with_no_policy_has_its_own_reason_not_a_policy_denial():
    # Reaching here means a request for a path that is not a route -- a probe
    # or a typo -- because the startup assertion covers every real route. It
    # must never be indistinguishable from a policy denial.
    assert run(config(), path="/probe").record["policy"] == "<none>"


# --- the record --------------------------------------------------------------

def test_the_record_carries_the_full_chain_and_the_index_used():
    # Without these a wrong chain index is invisible: every record just says
    # "denied" and nothing shows which element was read.
    outcome = enforce(
        config(chain_index=-2),
        path="/webhook",
        method="POST",
        header_value="1.1.1.1, 203.0.113.7, 2.2.2.2",
        peer="198.51.100.1",
    )
    assert outcome.record["chain"] == ["1.1.1.1", "203.0.113.7", "2.2.2.2"]
    assert outcome.record["chain_index"] == -2
    assert outcome.record["chain_length"] == 3
    assert outcome.record["client_ip"] == "203.0.113.7"


def test_the_record_names_the_policy_the_route_and_the_method():
    record = run(config(), header="198.51.100.9").record
    assert record["policy"] == "webhook"
    assert record["route"] == "/webhook"
    assert record["method"] == "POST"


def test_the_record_carries_the_transport_peer_separately_from_the_client():
    record = run(config()).record
    assert record["peer"] == "198.51.100.1"
    assert record["client_ip"] == "203.0.113.7"
    assert record["peer"] != record["client_ip"]


def test_the_record_names_the_matched_set_on_an_allow():
    assert run(config()).record["matched_set"] == "permitted"


def test_a_long_chain_is_truncated_but_says_so_and_keeps_the_real_length():
    header = ", ".join(["203.0.113.7"] * 40)
    record = enforce(config(), path="/webhook", method="POST", header_value=header).record
    assert len(record["chain"]) == 16
    assert record["chain_length"] == 40
    assert record["chain_truncated"] is True


def test_a_short_chain_is_not_marked_truncated():
    assert "chain_truncated" not in run(config()).record


def test_the_record_serialises_to_one_json_line_even_with_a_hostile_chain():
    # Every value here is attacker-influenced. A forged newline would let a
    # caller write a second log line; json.dumps escapes it.
    injected = 'x", "decision": "allow\n2026-01-01 FAKE LOG LINE'
    record = enforce(config(), path="/webhook", method="POST", header_value=injected).record
    serialised = json.dumps(record, sort_keys=True, default=str)
    assert "\n" not in serialised
    assert json.loads(serialised)["decision"] != "allow"


def test_a_hostile_path_cannot_forge_a_log_line_either():
    record = enforce(config(), path="/x\n2026-01-01 FAKE", method="GET", header_value=None).record
    assert "\n" not in json.dumps(record, default=str)


# --- what gets logged, and at what level -------------------------------------

def test_an_enforced_block_logs_at_warning(caplog):
    logger = logging.getLogger("ipfilter.test.warn")
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        enforce(config(), path="/webhook", method="POST", header_value="198.51.100.9", logger=logger)
    levels = [record.levelno for record in caplog.records]
    assert logging.WARNING in levels


def test_a_shadow_block_logs_at_info_so_it_does_not_page_before_enforcing(caplog):
    logger = logging.getLogger("ipfilter.test.shadow")
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        enforce(config(log_only=True), path="/webhook", method="POST",
                header_value="198.51.100.9", logger=logger)
    assert [record.levelno for record in caplog.records] == [logging.INFO]


def test_an_allow_logs_at_debug_so_it_costs_nothing_at_a_normal_level(caplog):
    logger = logging.getLogger("ipfilter.test.allow")
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        enforce(config(), path="/webhook", method="POST", header_value="203.0.113.7", logger=logger)
    assert [record.levelno for record in caplog.records] == [logging.DEBUG]


def test_the_emitted_line_is_the_record(caplog):
    logger = logging.getLogger("ipfilter.test.body")
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        outcome = enforce(config(), path="/webhook", method="POST",
                          header_value="198.51.100.9", logger=logger)
    assert json.loads(caplog.records[0].getMessage()) == json.loads(
        json.dumps(outcome.record, sort_keys=True, default=str)
    )


# --- the exempt route --------------------------------------------------------

def test_an_exempt_route_allows_a_caller_with_no_forwarded_header_at_all():
    # The real case: callers egressing from per-VM ephemeral addresses, which
    # cannot be allowlisted and are authenticated by other means.
    outcome = run(config(), path="/preempted", header=None)
    assert outcome.allowed is True
    assert outcome.record["reason"] == "policy-exempt"


def test_an_exempt_route_allows_an_address_no_set_contains():
    outcome = run(config(), path="/preempted", header="136.111.117.105")
    assert outcome.allowed is True


def test_exemption_does_not_leak_to_the_neighbouring_route():
    assert run(config(), path="/webhook", header="136.111.117.105").allowed is False


# --- the configured header name ---------------------------------------------

def test_the_forwarded_header_name_is_configurable():
    cfg = config(forwarded_for_header="X-Envoy-External-Address")
    outcome = enforce(cfg, path="/webhook", method="POST", header_value="203.0.113.7")
    assert outcome.allowed is True


def test_chain_index_has_no_default_so_it_cannot_be_omitted_by_accident():
    # A default index would be correct for exactly one proxy topology and
    # silently wrong for every other, and silently wrong here denies everyone.
    with pytest.raises(TypeError):
        FilterConfig(registry=REGISTRY, resolver=RESOLVER)
