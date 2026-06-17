from __future__ import annotations

import ipaddress
import socket
import urllib.parse
from typing import Any


def local_ipv4_addresses() -> list[str]:
    """Return usable local IPv4 addresses, preferring the default route."""
    addresses: list[str] = []

    def add(value: str) -> None:
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            return
        if (
            address.version != 4
            or address.is_loopback
            or address.is_unspecified
            or address.is_multicast
        ):
            return
        normalized = str(address)
        if normalized not in addresses:
            addresses.append(normalized)

    # A UDP connect selects the preferred outbound interface without sending
    # application data. This normally identifies the useful LAN address.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            add(probe.getsockname()[0])
    except OSError:
        pass

    for hostname in (socket.gethostname(), socket.getfqdn()):
        try:
            entries = socket.getaddrinfo(
                hostname,
                None,
                socket.AF_INET,
                socket.SOCK_STREAM,
            )
        except OSError:
            continue
        for entry in entries:
            add(entry[4][0])
    return addresses


def request_address(host_header: str | None, port: int) -> str | None:
    raw = (host_header or "").strip()
    if not raw or any(character in raw for character in "\r\n/\\"):
        return None
    try:
        parsed = urllib.parse.urlsplit(f"//{raw}")
        hostname = parsed.hostname
        request_port = parsed.port or port
    except ValueError:
        return None
    if not hostname:
        return None
    if ":" in hostname:
        return f"[{hostname}]:{request_port}"
    return f"{hostname}:{request_port}"


def connection_status_payload(
    *,
    bind_host: str,
    port: int,
    remote_mode: bool,
    host_header: str | None,
) -> dict[str, Any]:
    current = request_address(host_header, port)
    addresses: list[str] = []

    def add(host: str) -> None:
        value = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
        if value not in addresses:
            addresses.append(value)

    if remote_mode:
        if bind_host not in {"0.0.0.0", "::"}:
            try:
                if not ipaddress.ip_address(bind_host).is_loopback:
                    add(bind_host)
            except ValueError:
                add(bind_host)
        for address in local_ipv4_addresses():
            add(address)

        # An address already used successfully by a remote client is the most
        # reliable choice for that client.
        if current:
            current_host = urllib.parse.urlsplit(f"//{current}").hostname
            try:
                is_loopback = bool(
                    current_host and ipaddress.ip_address(current_host).is_loopback
                )
            except ValueError:
                is_loopback = False
            if not is_loopback and current not in addresses:
                addresses.insert(0, current)
    elif current:
        addresses.append(current)

    fallback = current or f"127.0.0.1:{port}"
    return {
        "connection_address": addresses[0] if addresses else fallback,
        "network_addresses": addresses or [fallback],
    }
