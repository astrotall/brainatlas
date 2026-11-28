import hashlib
import hmac
from ipaddress import IPv4Address, IPv6Address, IPv6Network, ip_address

IPV6_GROUP_PREFIX = 64
CLIENT_KEY_HEX_LENGTH = 32


class InvalidClientAddressError(ValueError):
    pass


def address_group(raw_address: str) -> str:
    try:
        address = ip_address(raw_address.strip())
    except ValueError as error:
        message = "the client address is not an IP address"
        raise InvalidClientAddressError(message) from error
    if isinstance(address, IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    if isinstance(address, IPv4Address):
        return f"v4:{address}"
    network = IPv6Network((address, IPV6_GROUP_PREFIX), strict=False)
    return f"v6:{network.network_address}"


def client_key(raw_address: str, secret: bytes) -> str:
    digest = hmac.new(secret, address_group(raw_address).encode(), hashlib.sha256).hexdigest()
    return digest[:CLIENT_KEY_HEX_LENGTH]
