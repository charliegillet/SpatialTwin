"""HMAC-signed, scoped, short-lived tokens for phones (exit signs and hazard proposals).

Why: NetworkGuard rejects every non-loopback client that cannot send X-API-Token, and a phone's EventSource cannot
set headers. A phone instead presents a cookie holding one of these tokens, and the token only ever unlocks a short
allowlist of read-only sign paths or the proposal endpoint (``guard.py``). It never carries operator authority:
minting is loopback-only, and nothing a token unlocks changes the plan or the doors.

Wire format (ASCII, cookie- and URL-safe, short enough for a small QR)::

    v1.<scope>.<venue_id>.<exit_id or ->.<iat>.<exp>.<jti>.<parent jti or ->.<tag>

``scope`` is ``sign`` (sign:read) or ``prop`` (hazard:propose); ``iat``/``exp`` are Unix seconds; ``jti`` is 12 hex
digits; ``tag`` is base64url(HMAC-SHA256(key, "spatialtwin-sign-token\\n" + everything before the tag)). A QR token
has no parent; when a phone redeems it at ``/s/<token>`` the server derives a *device* token (fresh jti, same scope,
venue, exit and expiry, parent = the QR's jti) for the cookie, so rate limits and "my proposals" are per phone.

The key is ``SPATIALTWIN_SIGN_SECRET`` (at least 32 characters) or, when unset, 32 random bytes per process, so
every phone token dies on a restart. A configured secret that is too short disables signs (fail closed) instead of
silently using a weak key. ``revoke_all`` invalidates every token issued so far (in memory only: with a configured
secret, rotate the secret to revoke across restarts).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import time
from typing import Callable, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.app.venues.model import VENUE_ID_PATTERN

Scope = Literal["sign:read", "hazard:propose"]
SCOPES = ("sign:read", "hazard:propose")
SECRET_ENV = "SPATIALTWIN_SIGN_SECRET"
MIN_SECRET_LENGTH = 32
DEFAULT_TTL_SECONDS = 4 * 60 * 60
MIN_TTL_SECONDS = 60
MAX_TTL_SECONDS = 4 * 60 * 60
MAX_TOKEN_LENGTH = 256
EXIT_ID_PATTERN = r"^[A-Z0-9_]{1,32}$"
# One cookie per scope, so a phone can hold a sign and a proposal session at once.
COOKIE_NAMES: Dict[str, str] = {"sign:read": "st_sign", "hazard:propose": "st_propose"}

_WIRE_SCOPE = {"sign:read": "sign", "hazard:propose": "prop"}
_SCOPE_FROM_WIRE = {wire: scope for scope, wire in _WIRE_SCOPE.items()}
_MAC_DOMAIN = b"spatialtwin-sign-token\n"
_TOKEN_CHARSET = re.compile(r"^[A-Za-z0-9_.-]+$")
_VENUE = re.compile(VENUE_ID_PATTERN)
_EXIT = re.compile(EXIT_ID_PATTERN)
_JTI = re.compile(r"^[0-9a-f]{12}$")
_UINT = re.compile(r"^[0-9]{1,12}$")


class TokenError(Exception):
    """A token that must not be honoured. ``code`` is a short snake_case reason; never echo the token itself."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class SignClaims(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: Scope
    venue_id: str = Field(pattern=VENUE_ID_PATTERN)
    exit_id: Optional[str] = Field(default=None, pattern=EXIT_ID_PATTERN)
    iat: int = Field(ge=0)
    exp: int = Field(ge=0)
    jti: str = Field(pattern=r"^[0-9a-f]{12}$")
    parent: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{12}$")

    @property
    def device_id(self) -> str:
        """Who to rate-limit: the phone's own session (device tokens), else the QR token itself."""
        return self.jti

    @property
    def invite_id(self) -> str:
        """The QR this session came from (itself for a QR token)."""
        return self.parent or self.jti


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class TokenSigner:
    """Mints and verifies tokens. ``now`` is injectable so expiry is testable without sleeping."""

    def __init__(self, secret: Optional[bytes] = None, now: Callable[[], float] = time.time):
        self.now = now
        self.disabled_reason: Optional[str] = None
        if secret is not None:
            self.secret_source = "explicit"
        else:
            configured = os.environ.get(SECRET_ENV, "")
            if configured:
                self.secret_source = "env"
                if len(configured) < MIN_SECRET_LENGTH:
                    self.disabled_reason = "sign_secret_too_short"
                secret = configured.encode("utf-8")
            else:
                self.secret_source = "process"
                secret = secrets.token_bytes(32)
        # Derive the MAC key so the configured secret is never used directly (and could be shared with other uses).
        self._key = hmac.new(secret, b"spatialtwin-signs-v1", hashlib.sha256).digest()
        self.not_before = 0

    # -- mint ----------------------------------------------------------------------------------------------------

    def _tag(self, body: str) -> str:
        return _b64(hmac.new(self._key, _MAC_DOMAIN + body.encode("ascii"), hashlib.sha256).digest())

    def encode(self, claims: SignClaims) -> str:
        body = ".".join(("v1", _WIRE_SCOPE[claims.scope], claims.venue_id, claims.exit_id or "-", str(claims.iat),
                         str(claims.exp), claims.jti, claims.parent or "-"))
        return f"{body}.{self._tag(body)}"

    def mint(self, scope: str, venue_id: str, exit_id: Optional[str] = None,
             ttl_seconds: int = DEFAULT_TTL_SECONDS) -> tuple[str, SignClaims]:
        if self.disabled_reason:
            raise TokenError(self.disabled_reason)
        ttl = max(MIN_TTL_SECONDS, min(MAX_TTL_SECONDS, int(ttl_seconds)))
        # Never issue a token older than the last revocation, even within the same second.
        iat = max(int(self.now()), self.not_before)
        claims = SignClaims(scope=scope, venue_id=venue_id, exit_id=exit_id if scope == "sign:read" else None,
                            iat=iat, exp=iat + ttl, jti=secrets.token_hex(6))
        return self.encode(claims), claims

    def derive_device(self, invite: SignClaims) -> tuple[str, SignClaims]:
        """A per-phone session from a redeemed QR token. Same scope, venue, exit and expiry: it never extends a QR."""
        if self.disabled_reason:
            raise TokenError(self.disabled_reason)
        iat = max(int(self.now()), self.not_before)
        claims = invite.model_copy(update={"iat": iat, "jti": secrets.token_hex(6), "parent": invite.invite_id})
        return self.encode(claims), claims

    def revoke_all(self) -> int:
        """Every token issued so far stops verifying; tokens minted afterwards are unaffected."""
        self.not_before = int(self.now()) + 1
        return self.not_before

    # -- verify --------------------------------------------------------------------------------------------------

    def verify(self, token: Optional[str], scope: Optional[str] = None) -> SignClaims:
        """The token's claims, or TokenError. The MAC is checked before any field is trusted."""
        if self.disabled_reason:
            raise TokenError(self.disabled_reason)
        if not token or len(token) > MAX_TOKEN_LENGTH or not _TOKEN_CHARSET.match(token):
            raise TokenError("token_malformed")
        body, _, tag = token.rpartition(".")
        if not body or not hmac.compare_digest(self._tag(body), tag):
            raise TokenError("token_bad_signature")
        parts = body.split(".")
        if len(parts) != 8 or parts[0] != "v1":
            raise TokenError("token_malformed")
        _, wire_scope, venue_id, exit_id, iat, exp, jti, parent = parts
        claimed = _SCOPE_FROM_WIRE.get(wire_scope)
        if (claimed is None or not _VENUE.match(venue_id) or not (exit_id == "-" or _EXIT.match(exit_id))
                or not _UINT.match(iat) or not _UINT.match(exp) or not _JTI.match(jti)
                or not (parent == "-" or _JTI.match(parent))):
            raise TokenError("token_malformed")
        claims = SignClaims(scope=claimed, venue_id=venue_id, exit_id=None if exit_id == "-" else exit_id,
                            iat=int(iat), exp=int(exp), jti=jti, parent=None if parent == "-" else parent)
        if scope is not None and claims.scope != scope:
            raise TokenError("token_scope_mismatch")
        if self.now() >= claims.exp:
            raise TokenError("token_expired")
        if claims.iat < self.not_before:
            raise TokenError("token_revoked")
        return claims

    def remaining_seconds(self, claims: SignClaims) -> int:
        return max(0, int(claims.exp - self.now()))
