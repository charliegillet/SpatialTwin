"""The phone side of NetworkGuard: which non-loopback requests a sign or proposal cookie may make.

``scoped_access(scope)`` is called by NetworkGuard (backend/app/main.py) only for a request that is neither loopback
nor carrying X-API-Token. It returns the scope that grants the request, or None (the guard then answers 403
``remote_access_denied`` as before). The allowlist is exact, per method, and evaluated on the decoded ASGI path that
routing and StaticFiles also use, so ``..``, ``%2F``, doubled slashes, trailing slashes and query strings cannot
widen it:

=========================================  ==========  ============================================================
path                                       methods     needs
=========================================  ==========  ============================================================
``/s/<token-shaped>``                      GET         nothing (the route verifies the token and sets the cookie)
``/sign.html``                             GET, HEAD   any valid sign or proposal cookie
``/assets/<name>.js|.css`` (one segment)   GET, HEAD   any valid sign or proposal cookie
``/api/public/signs/<venue>``              GET         sign:read cookie for that venue
``/api/public/signs/<venue>/events``       GET         sign:read cookie for that venue
``/api/public/hazard-proposals``           GET, POST   hazard:propose cookie
=========================================  ==========  ============================================================

Everything else (every operator route, /api/signs/*, websockets, the presenter app's HTML) stays 403 for phones.
The routes re-check the cookie themselves, so a mistake in the guard hook cannot widen what a phone can read.

``forwarded_from_remote(scope)`` is the Vite trap detector: a phone browsing ``vite --host`` reaches the backend
through Vite's proxy, so its peer address is loopback, but its browser still sends an Origin/Referer naming the
LAN host. The loopback-only sign routes refuse such requests; NetworkGuard may use the same check app-wide.
"""
from __future__ import annotations

import ipaddress
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional
from urllib.parse import urlsplit

from backend.app.signs.tokens import COOKIE_NAMES, SignClaims, TokenError, TokenSigner

SIGN_PAGE_PATH = "/sign.html"
PROPOSALS_PATH = "/api/public/hazard-proposals"
_ENTRY = re.compile(r"^/s/[A-Za-z0-9_.-]{1,256}$")
_ASSET = re.compile(r"^/assets/[A-Za-z0-9_-]{1,128}\.(?:js|css)$")
_SIGN_API = re.compile(r"^/api/public/signs/([a-z0-9-]{3,40})(?:/events)?$")
_MAX_COOKIE_VALUES = 4


def is_loopback_host(host: Optional[str]) -> bool:
    """127.0.0.0/8, ::1, IPv4-mapped loopback (same rule as main.is_loopback_client). Unparseable is not loopback."""
    try:
        address = ipaddress.ip_address((host or "").strip("[]"))
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_loopback


def _is_loopback_name(host: Optional[str]) -> bool:
    if not host:
        return False
    host = host.lower().rstrip(".")
    return host == "localhost" or host.endswith(".localhost") or is_loopback_host(host)


def _headers(scope: Mapping[str, Any], name: bytes) -> List[str]:
    return [value.decode("latin-1") for key, value in scope.get("headers", []) if key == name]


def forwarded_from_remote(scope: Mapping[str, Any]) -> bool:
    """True when a request's own headers say a non-loopback browser or proxy sent it.

    An Origin or Referer naming anything other than localhost/127.x/::1 (including ``null``), or any
    X-Forwarded-For / Forwarded header, means the loopback peer address is a proxy hop, not the operator's browser.
    Requests without these headers (curl, the smoke tool, server-side code) are unaffected.
    """
    for value in _headers(scope, b"origin") + _headers(scope, b"referer"):
        try:
            host = urlsplit(value.strip()).hostname
        except ValueError:
            return True
        if not _is_loopback_name(host):
            return True
    if _headers(scope, b"forwarded"):
        return True
    for value in _headers(scope, b"x-forwarded-for"):
        if any(not is_loopback_host(part.strip()) for part in value.split(",")):
            return True
    return False


def cookie_values(headers: Iterable[tuple], name: str) -> List[str]:
    """Every value of cookie ``name`` across Cookie headers (browsers may send duplicates), bounded."""
    found: List[str] = []
    for key, raw in headers:
        if key != b"cookie":
            continue
        for part in raw.decode("latin-1").split(";"):
            key_text, sep, value = part.strip().partition("=")
            if sep and key_text == name:
                found.append(value.strip().strip('"'))
                if len(found) >= _MAX_COOKIE_VALUES:
                    return found
    return found


def cookie_claims(headers: Iterable[tuple], signer: TokenSigner) -> Dict[str, SignClaims]:
    """Valid claims per scope from this request's cookies. A token in the wrong scope's cookie does not count."""
    headers = list(headers)
    result: Dict[str, SignClaims] = {}
    for scope_name, cookie in COOKIE_NAMES.items():
        for value in cookie_values(headers, cookie):
            try:
                result[scope_name] = signer.verify(value, scope_name)
                break
            except TokenError:
                continue
    return result


def scoped_access(scope: Mapping[str, Any], signer: Optional[TokenSigner] = None) -> Optional[str]:
    """The scope granting this non-loopback request ("sign:entry", "sign:read", "hazard:propose"), or None."""
    if scope.get("type") != "http":
        return None
    path = scope.get("path") or ""
    method = scope.get("method") or ""
    if method == "GET" and _ENTRY.match(path):
        return "sign:entry"
    static = method in ("GET", "HEAD") and (path == SIGN_PAGE_PATH or _ASSET.match(path) is not None)
    sign_api = _SIGN_API.match(path) if method == "GET" else None
    proposals = path == PROPOSALS_PATH and method in ("GET", "POST")
    if not (static or sign_api or proposals):
        return None  # decided without touching the cookie
    if signer is None:
        from backend.app.signs.service import default_service
        signer = default_service().signer
    claims = cookie_claims(scope.get("headers", []), signer)
    if static and claims:
        return "sign:read" if "sign:read" in claims else "hazard:propose"
    if sign_api is not None:
        read = claims.get("sign:read")
        return "sign:read" if read is not None and read.venue_id == sign_api.group(1) else None
    if proposals and "hazard:propose" in claims:
        return "hazard:propose"
    return None
