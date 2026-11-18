"""Address check used by the outbound-fetch guard."""

import pytest

from reed.http import _is_public_ip


@pytest.mark.parametrize(
    "addr",
    [
        "8.8.8.8",
        "1.1.1.1",
        "2606:4700:4700::1111",
    ],
)
def test_global_addresses_allowed(addr):
    assert _is_public_ip(addr)


@pytest.mark.parametrize(
    "addr",
    [
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "127.0.0.1",
        "169.254.169.254",
        "100.64.0.1",  # carrier-grade NAT
        "100.127.255.254",
        "198.18.0.1",
        "192.0.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "::1",
        "fc00::1",
        "fe80::1",
        "::ffff:127.0.0.1",  # IPv4-mapped
        "::ffff:100.64.0.1",
        "2002:7f00:0001::",  # 6to4 of 127.0.0.1
        "64:ff9b::7f00:1",  # NAT64 of 127.0.0.1
        "64:ff9b::6440:1",  # NAT64 of 100.64.0.1
        "not-an-ip",
    ],
)
def test_non_global_addresses_rejected(addr):
    assert not _is_public_ip(addr)


def test_nat64_of_public_address_allowed():
    assert _is_public_ip("64:ff9b::808:808")  # 8.8.8.8
