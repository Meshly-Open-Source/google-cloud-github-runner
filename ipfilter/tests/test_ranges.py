"""Matching, boundaries, and the v4/v6 split that a single parse path breaks."""

import ipaddress

import pytest

from ipfilter.ranges import RangeConfigError, RangeResolver, compile_ranges

# Documentation-reserved prefixes (RFC 5737 / RFC 3849). Deliberately NOT any
# real party's ranges: a test fixture that contains a live production prefix is
# one copy-paste away from becoming a policy.
V4_SET = ["203.0.113.0/24", "198.51.100.128/25"]
V6_SET = ["2001:db8:aaaa::/48"]


def addr(text):
    return ipaddress.ip_address(text)


def test_v4_and_v6_in_one_set_are_compiled_into_separate_tables():
    # The regression this exists for: one v6-shaped parse path puts every IPv4
    # caller into an except branch and returns "no match", which under
    # fail-closed denies every v4 client silently.
    compiled = compile_ranges("mixed", V4_SET + V6_SET)
    assert len(compiled.v4) == 2
    assert len(compiled.v6) == 1
    assert compiled.contains(addr("203.0.113.9")) is True
    assert compiled.contains(addr("2001:db8:aaaa::1")) is True


def test_a_v4_address_is_not_matched_by_a_v6_only_set_and_does_not_raise():
    compiled = compile_ranges("v6only", V6_SET)
    assert compiled.contains(addr("203.0.113.9")) is False


def test_a_v6_address_is_not_matched_by_a_v4_only_set_and_does_not_raise():
    compiled = compile_ranges("v4only", V4_SET)
    assert compiled.contains(addr("2001:db8:aaaa::1")) is False


@pytest.mark.parametrize(
    "candidate,expected",
    [
        ("203.0.113.0", True),    # first address of the /24
        ("203.0.113.255", True),  # last address of the /24
        ("203.0.112.255", False),  # one below the first
        ("203.0.114.0", False),   # one above the last
        ("198.51.100.128", True),   # first address of the /25
        ("198.51.100.255", True),   # last address of the /25
        ("198.51.100.127", False),  # one below -- the half of the /24 NOT covered
    ],
)
def test_v4_boundaries_are_inclusive_and_exact(candidate, expected):
    compiled = compile_ranges("v4", V4_SET)
    assert compiled.contains(addr(candidate)) is expected


@pytest.mark.parametrize(
    "candidate,expected",
    [
        ("2001:db8:aaaa::", True),
        ("2001:db8:aaaa:ffff:ffff:ffff:ffff:ffff", True),
        ("2001:db8:aaa9:ffff:ffff:ffff:ffff:ffff", False),
        ("2001:db8:aaab::", False),
    ],
)
def test_v6_boundaries_are_inclusive_and_exact(candidate, expected):
    compiled = compile_ranges("v6", V6_SET)
    assert compiled.contains(addr(candidate)) is expected


def test_a_single_host_prefix_matches_only_that_host():
    compiled = compile_ranges("host", ["203.0.113.7/32"])
    assert compiled.contains(addr("203.0.113.7")) is True
    assert compiled.contains(addr("203.0.113.8")) is False
    assert compiled.contains(addr("203.0.113.6")) is False


def test_adjacent_prefixes_collapse_without_changing_membership():
    compiled = compile_ranges("adjacent", ["203.0.113.0/25", "203.0.113.128/25"])
    assert len(compiled.v4) == 1, "two adjacent /25s should collapse to one /24"
    assert compiled.contains(addr("203.0.113.0")) is True
    assert compiled.contains(addr("203.0.113.255")) is True
    assert compiled.contains(addr("203.0.114.0")) is False


def test_overlapping_prefixes_collapse_to_the_wider_one():
    compiled = compile_ranges("overlap", ["203.0.113.0/24", "203.0.113.64/26"])
    assert len(compiled.v4) == 1
    assert compiled.contains(addr("203.0.113.70")) is True


def test_host_bits_set_in_a_prefix_is_a_load_time_error():
    # A silently-corrected netmask is a policy that does not mean what its
    # author wrote, so this must raise rather than normalise.
    with pytest.raises(RangeConfigError) as excinfo:
        compile_ranges("typo", ["203.0.113.1/24"])
    assert "203.0.113.1/24" in str(excinfo.value)


def test_garbage_is_a_load_time_error_not_a_skipped_entry():
    with pytest.raises(RangeConfigError):
        compile_ranges("garbage", ["203.0.113.0/24", "not-an-address"])


def test_blank_entries_are_ignored_so_a_trailing_newline_is_not_fatal():
    compiled = compile_ranges("blanks", ["203.0.113.0/24", "", "   "])
    assert len(compiled) == 1


def test_an_empty_set_is_empty_rather_than_matching_nothing_quietly():
    # is_empty is what lets the decision layer say "we have no list" instead of
    # "you are not on the list". Those have different fixes.
    compiled = compile_ranges("nothing", [])
    assert compiled.is_empty is True
    assert compiled.contains(addr("203.0.113.9")) is False


def test_a_populated_set_is_not_empty():
    assert compile_ranges("something", V4_SET).is_empty is False


def test_resolver_returns_none_for_an_unknown_set_rather_than_raising():
    resolver = RangeResolver.from_mapping({"known": V4_SET})
    assert resolver.get("known") is not None
    assert resolver.get("typo-in-policy") is None


def test_resolver_describes_itself_for_a_startup_log():
    resolver = RangeResolver.from_mapping({"mixed": V4_SET + V6_SET}, source="test")
    described = resolver.describe()
    assert described["mixed"]["v4"] == 2
    assert described["mixed"]["v6"] == 1
    assert described["mixed"]["source"] == "test"


def test_source_is_carried_through_for_diagnosis():
    compiled = compile_ranges("s", V4_SET, source="gs://bucket/net-ranges/cidrs.json")
    assert compiled.source == "gs://bucket/net-ranges/cidrs.json"


def test_the_package_ships_no_prefixes_of_its_own():
    """A library-level default range set would be an invisible default.

    Asserted structurally rather than by reading the source: any module-level
    string in the package that parses as a CIDR with a prefix length would be a
    baked range. The consumer supplies the data; this package only matches it.
    """
    import ipfilter
    import pkgutil

    offenders = []
    for module_info in pkgutil.iter_modules(ipfilter.__path__):
        module = __import__(f"ipfilter.{module_info.name}", fromlist=["_"])
        for name, value in vars(module).items():
            candidates = [value] if isinstance(value, str) else []
            if isinstance(value, (list, tuple, set)):
                candidates = [item for item in value if isinstance(item, str)]
            for candidate in candidates:
                if "/" not in candidate:
                    continue
                try:
                    ipaddress.ip_network(candidate, strict=False)
                except ValueError:
                    continue
                offenders.append(f"{module_info.name}.{name} = {candidate!r}")
    assert offenders == [], f"the package must ship no CIDRs of its own; found {offenders}"
