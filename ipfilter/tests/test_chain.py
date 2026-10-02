"""Forwarded-for parsing, and the ways a chain fails to yield an address."""

import pytest

from ipfilter.chain import (
    CHAIN_TOO_SHORT,
    EMPTY_HEADER,
    NO_HEADER,
    UNPARSEABLE,
    derive_client_ip,
    normalise_ip_token,
)


@pytest.mark.parametrize(
    "token,expected",
    [
        ("203.0.113.7", "203.0.113.7"),
        ("  203.0.113.7  ", "203.0.113.7"),
        ("203.0.113.7:51234", "203.0.113.7"),
        ("[2001:db8::1]:443", "2001:db8::1"),
        ("[2001:db8::1]", "2001:db8::1"),
        # The trap: a bare v6 address is full of colons. Splitting on the last
        # one mangles it into nonsense, which then fails to parse, which under
        # fail-closed denies the caller.
        ("2001:db8::1", "2001:db8::1"),
        ("2001:db8:aaaa:bbbb:cccc:dddd:eeee:ffff", "2001:db8:aaaa:bbbb:cccc:dddd:eeee:ffff"),
    ],
)
def test_normalise_strips_only_unambiguous_decorations(token, expected):
    assert normalise_ip_token(token) == expected


@pytest.mark.parametrize("token", ["", "   ", "[", "[]", "[2001:db8::1", ":443"])
def test_normalise_returns_none_rather_than_a_half_parsed_string(token):
    assert normalise_ip_token(token) is None


def test_a_bare_v6_address_survives_the_round_trip_and_is_matchable():
    resolution = derive_client_ip("2001:db8::1", chain_index=-1)
    assert str(resolution.client_ip) == "2001:db8::1"


def test_bracketed_and_port_suffixed_v6_resolves_to_the_same_address():
    bracketed = derive_client_ip("[2001:db8::1]:443", chain_index=-1)
    bare = derive_client_ip("2001:db8::1", chain_index=-1)
    assert bracketed.client_ip == bare.client_ip


def test_index_minus_one_takes_the_rightmost_entry():
    resolution = derive_client_ip("1.1.1.1, 2.2.2.2, 3.3.3.3", chain_index=-1)
    assert str(resolution.client_ip) == "3.3.3.3"


def test_index_minus_two_takes_the_entry_before_the_rightmost():
    # Distinct values per position, so an off-by-one cannot pass: with three
    # different addresses, reading the wrong index gives the wrong answer.
    resolution = derive_client_ip("1.1.1.1, 2.2.2.2, 3.3.3.3", chain_index=-2)
    assert str(resolution.client_ip) == "2.2.2.2"


def test_index_zero_takes_the_leftmost_entry():
    resolution = derive_client_ip("1.1.1.1, 2.2.2.2, 3.3.3.3", chain_index=0)
    assert str(resolution.client_ip) == "1.1.1.1"


def test_the_full_chain_is_returned_so_a_wrong_index_is_visible_in_the_record():
    resolution = derive_client_ip("1.1.1.1, 2.2.2.2, 3.3.3.3", chain_index=-2)
    assert resolution.chain == ("1.1.1.1", "2.2.2.2", "3.3.3.3")
    assert resolution.index_used == -2


def test_a_chain_shorter_than_the_index_resolves_to_nothing_with_that_reason():
    # The single most important failure to NOT paper over: this is what a
    # wrong chain index looks like, and a fallback here would hide it.
    resolution = derive_client_ip("1.1.1.1", chain_index=-2)
    assert resolution.client_ip is None
    assert resolution.reason == CHAIN_TOO_SHORT
    assert resolution.chain == ("1.1.1.1",)


def test_an_out_of_range_positive_index_is_also_chain_too_short():
    resolution = derive_client_ip("1.1.1.1, 2.2.2.2", chain_index=5)
    assert resolution.client_ip is None
    assert resolution.reason == CHAIN_TOO_SHORT


def test_a_missing_header_is_distinguishable_from_an_empty_one():
    assert derive_client_ip(None, chain_index=-1).reason == NO_HEADER
    assert derive_client_ip("", chain_index=-1).reason == EMPTY_HEADER
    assert derive_client_ip("   ,  , ", chain_index=-1).reason == EMPTY_HEADER


def test_an_unparseable_entry_at_the_chosen_index_is_named_as_such():
    resolution = derive_client_ip("1.1.1.1, not-an-ip", chain_index=-1)
    assert resolution.client_ip is None
    assert resolution.reason == UNPARSEABLE


def test_an_unparseable_entry_elsewhere_in_the_chain_does_not_matter():
    # Only the configured position is trusted, so junk a caller injected to
    # the left of it must not affect the outcome.
    resolution = derive_client_ip("<script>, not-an-ip, 203.0.113.7", chain_index=-1)
    assert str(resolution.client_ip) == "203.0.113.7"


def test_whitespace_around_entries_is_tolerated():
    resolution = derive_client_ip("  1.1.1.1 ,  203.0.113.7  ", chain_index=-1)
    assert str(resolution.client_ip) == "203.0.113.7"


def test_a_caller_injected_prefix_stays_to_the_left_of_an_appended_real_value():
    # The spoofing shape this control has to survive on an append-style
    # platform: the caller sends its own chain, the frontend appends the real
    # peer. Reading from the right gets the real one; reading index 0 gets the
    # forgery, which is the classic implementation error.
    forged = "203.0.113.7, 203.0.113.7, 203.0.113.7"
    header = f"{forged}, 198.51.100.200"
    assert str(derive_client_ip(header, chain_index=-1).client_ip) == "198.51.100.200"
    assert str(derive_client_ip(header, chain_index=0).client_ip) == "203.0.113.7"


def test_resolved_is_the_single_predicate_callers_use():
    assert derive_client_ip("203.0.113.7", chain_index=-1).resolved is True
    assert derive_client_ip(None, chain_index=-1).resolved is False
