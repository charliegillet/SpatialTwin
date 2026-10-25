"""Which address a phone should use to reach this server, and whether the server is listening there.

Why: uvicorn binds 127.0.0.1 unless started with ``--host 0.0.0.0``, and a QR pointing at 127.0.0.1 or at an
interface the server does not listen on fails silently on the judge's phone. The mint response therefore carries
the chosen base URL, where it came from, and a ``listening_on_lan`` probe with a ready-made warning.

Order: an explicit ``base_url`` in the mint request (the presenter knows best), then ``SPATIALTWIN_SIGN_BASE_URL``,
then the address of the interface holding the default route, found with a UDP ``connect`` (which sends no packet),
then 127.0.0.1 with a warning. The probe is a TCP connect to our own LAN address: it proves the socket is bound
there, not that Wi-Fi client isolation or the macOS firewall lets phones in.
"""
from __future__ import annotations

import ipaddress
import os
import re
import socket
from typing import Optional, Tuple

BASE_URL_ENV = "SPATIALTWIN_SIGN_BASE_URL"
_BASE_URL = re.compile(r"^(https?)://([A-Za-z0-9.-]{1,253}|\[[0-9A-Fa-f:.]{2,45}\])(?::([0-9]{1,5}))?/?$")
DEFAULT_PORT = 8000


def parse_base_url(value: str) -> Optional[Tuple[str, str, Optional[int]]]:
    """(scheme, host, port) for ``http(s)://host[:port]`` with no path, query or credentials; None otherwise."""
    match = _BASE_URL.match(value.strip())
    if not match:
        return None
    port = int(match.group(3)) if match.group(3) else None
    if port is not None and not 1 <= port <= 65535:
        return None
    return match.group(1), match.group(2), port


def detect_lan_ip() -> Optional[str]:
    """The IPv4 address of the interface the OS would route outward through, or None (offline, no interface)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            # TEST-NET-1 (RFC 5737): never routed, and a UDP connect only selects the source address.
            probe.connect(("192.0.2.1", 9))
            address = probe.getsockname()[0]
    except Exception:  # noqa: BLE001 - any failure just means "unknown"; the caller warns
        return None
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return None
    if parsed.is_loopback or parsed.is_unspecified or parsed.is_link_local:
        return None
    return address


def probe_listening(host: str, port: int, timeout: float = 0.3) -> Optional[bool]:
    """True if a TCP connect to host:port succeeds, False if refused, None if it could not be decided."""
    try:
        with socket.create_connection((host.strip("[]"), port), timeout=timeout):
            return True
    except ConnectionRefusedError:
        return False
    except Exception:  # noqa: BLE001 - timeouts, unreachable networks, sandboxed tests
        return None


def env_base_url() -> Optional[str]:
    value = os.environ.get(BASE_URL_ENV, "").strip()
    return value or None
