"""Scoped phone tokens: round trip, expiry, tampering, scope mismatch, revocation, secret handling, device derivation."""
import pytest

from backend.app.signs.tokens import (
    MAX_TTL_SECONDS, MIN_TTL_SECONDS, SECRET_ENV, TokenError, TokenSigner,
)
from tests.signs.conftest import Clock


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def signer(clock):
    return TokenSigner(secret=b"k" * 32, now=clock.time)


def code(signer, token, scope=None):
    with pytest.raises(TokenError) as error:
        signer.verify(token, scope)
    return error.value.code


def test_round_trip_keeps_every_claim(signer, clock):
    token, claims = signer.mint("sign:read", "building-v2", "E1", ttl_seconds=3600)
    assert token.startswith("v1.sign.building-v2.E1.") and len(token) < 140
    verified = signer.verify(token, "sign:read")
    assert verified == claims
    assert (verified.iat, verified.exp) == (int(clock.wall), int(clock.wall) + 3600)
    assert verified.parent is None and verified.invite_id == verified.jti


def test_propose_tokens_never_carry_an_exit(signer):
    token, claims = signer.mint("hazard:propose", "home-flat", "E1")
    assert claims.exit_id is None and ".prop.home-flat.-." in token


def test_ttl_is_clamped_to_the_short_window(signer):
    assert signer.mint("sign:read", "building-v2", ttl_seconds=10)[1].exp - signer.now() == MIN_TTL_SECONDS
    assert signer.mint("sign:read", "building-v2", ttl_seconds=10**9)[1].exp - signer.now() == MAX_TTL_SECONDS


def test_expiry_is_exact(signer, clock):
    token, claims = signer.mint("sign:read", "building-v2", "E1", ttl_seconds=600)
    clock.advance(599)
    assert signer.verify(token).jti == claims.jti
    clock.advance(1)
    assert code(signer, token) == "token_expired"


@pytest.mark.parametrize("field, value", [(1, "prop"), (2, "home-flat"), (3, "E2"), (3, "-"), (5, "9999999999"),
                                          (6, "000000000000"), (7, "000000000000")])
def test_any_changed_field_breaks_the_signature(signer, field, value):
    token, _ = signer.mint("sign:read", "building-v2", "E1")
    parts = token.split(".")
    assert parts[field] != value
    parts[field] = value
    assert code(signer, ".".join(parts)) == "token_bad_signature"


def test_forged_truncated_and_foreign_tokens_are_rejected(signer, clock):
    token, _ = signer.mint("sign:read", "building-v2", "E1")
    other = TokenSigner(secret=b"z" * 32, now=clock.time)
    assert code(other, token) == "token_bad_signature"
    assert code(signer, token[:-1]) == "token_bad_signature"
    assert code(signer, token.rsplit(".", 1)[0] + ".") == "token_bad_signature"
    # A forger who knows the format but not the key.
    assert code(signer, "v1.sign.building-v2.E1.1.99999999999.0123456789ab.-.AAAA") == "token_bad_signature"
    for bad in ["", "no dots", "v1.sign.building-v2.E1", "é" * 10, "a." * 200, None, "x" * 300, "v1.sign\n.x.y"]:
        assert code(signer, bad) in ("token_malformed", "token_bad_signature")


def test_scope_mismatch_is_rejected(signer):
    sign, _ = signer.mint("sign:read", "building-v2", "E1")
    propose, _ = signer.mint("hazard:propose", "building-v2")
    assert code(signer, sign, "hazard:propose") == "token_scope_mismatch"
    assert code(signer, propose, "sign:read") == "token_scope_mismatch"
    assert signer.verify(propose, "hazard:propose").scope == "hazard:propose"


def test_revoke_all_kills_issued_tokens_but_not_later_ones(signer, clock):
    before, _ = signer.mint("sign:read", "building-v2", "E1")
    signer.revoke_all()
    after, claims = signer.mint("sign:read", "building-v2", "E1")  # same second as the revocation
    assert code(signer, before) == "token_revoked"
    assert signer.verify(after).jti == claims.jti
    clock.advance(5)
    assert signer.verify(after).jti == claims.jti


def test_device_tokens_inherit_scope_and_expiry_and_never_extend(signer, clock):
    invite_token, invite = signer.mint("sign:read", "building-v2", "E2", ttl_seconds=600)
    clock.advance(100)
    device_token, device = signer.derive_device(invite)
    assert device_token != invite_token and device.jti != invite.jti
    assert (device.scope, device.venue_id, device.exit_id, device.exp) == (invite.scope, invite.venue_id, "E2", invite.exp)
    assert device.parent == invite.jti and device.invite_id == invite.jti and device.device_id == device.jti
    again = signer.derive_device(signer.verify(device_token))[1]
    assert again.parent == invite.jti  # re-redeeming a device token still points at the QR
    clock.advance(500)
    assert code(signer, device_token) == "token_expired"


def test_process_secret_dies_on_restart_and_env_secret_survives(monkeypatch):
    monkeypatch.delenv(SECRET_ENV, raising=False)
    first, second = TokenSigner(), TokenSigner()
    token, _ = first.mint("sign:read", "building-v2")
    assert first.secret_source == "process" and code(second, token) == "token_bad_signature"
    monkeypatch.setenv(SECRET_ENV, "x" * 40)
    first, second = TokenSigner(), TokenSigner()
    token, _ = first.mint("sign:read", "building-v2")
    assert first.secret_source == "env" and second.verify(token).venue_id == "building-v2"


def test_a_short_configured_secret_disables_signs_instead_of_using_a_weak_key(monkeypatch):
    monkeypatch.setenv(SECRET_ENV, "short")
    signer = TokenSigner()
    assert signer.disabled_reason == "sign_secret_too_short"
    with pytest.raises(TokenError, match="sign_secret_too_short"):
        signer.mint("sign:read", "building-v2")
    assert code(signer, "v1.sign.building-v2.-.1.2.0123456789ab.-.AAAA") == "sign_secret_too_short"
