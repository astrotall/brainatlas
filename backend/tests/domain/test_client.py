import pytest

from neuroctivity.domain.client import InvalidClientAddressError, address_group, client_key

SECRET = b"k" * 32


@pytest.mark.parametrize(
    ("address", "group"),
    [
        ("203.0.113.7", "v4:203.0.113.7"),
        (" 203.0.113.7 ", "v4:203.0.113.7"),
        ("::ffff:203.0.113.7", "v4:203.0.113.7"),
        ("2001:db8:1:2:3:4:5:6", "v6:2001:db8:1:2::"),
        ("2001:db8:1:2:ffff:ffff:ffff:ffff", "v6:2001:db8:1:2::"),
        ("::1", "v6:::"),
    ],
)
def test_groups_an_address_the_way_the_limit_counts_it(address: str, group: str) -> None:
    assert address_group(address) == group


@pytest.mark.parametrize(
    "address", ["", "unknown", "testclient", "203.0.113", "203.0.113.7:443", "1.2.3.4, 5.6.7.8"]
)
def test_refuses_anything_that_is_not_one_ip_address(address: str) -> None:
    with pytest.raises(InvalidClientAddressError):
        address_group(address)


def test_the_key_is_stable_short_and_never_contains_the_address() -> None:
    key = client_key("203.0.113.7", SECRET)

    assert key == client_key("203.0.113.7", SECRET)
    assert len(key) == 32
    assert "203" not in key


def test_one_ipv6_network_shares_a_key_and_its_neighbour_does_not() -> None:
    same = client_key("2001:db8:1:2::1", SECRET) == client_key("2001:db8:1:2:abcd::9", SECRET)

    assert same
    assert client_key("2001:db8:1:2::1", SECRET) != client_key("2001:db8:1:3::1", SECRET)


def test_another_secret_gives_another_key() -> None:
    assert client_key("203.0.113.7", SECRET) != client_key("203.0.113.7", b"o" * 32)


def test_two_addresses_never_share_a_key() -> None:
    assert client_key("203.0.113.7", SECRET) != client_key("203.0.113.8", SECRET)
